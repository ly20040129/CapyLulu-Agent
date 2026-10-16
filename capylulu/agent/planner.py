"""规划引擎（Planner Engine）：Leader 的调度大脑。

PlannerEngine 把 run_orchestrated 从「Leader 内嵌简易决策」升级为独立规划引擎：
- 计划决策：调用 LLM 输出 JSON（复用/增强 prompts.LEADER_PLANNER_PROMPT 语义），
  支持 chat / direct / plan 三种模式；
- plan 模式：支持多步骤、步骤依赖（depends）、每步独立派发与结果收集、
  单步失败自动重试 1 次、全部失败则降级（Leader 全量工具兜底）；
- 规划过程可观测：每次规划的决策 JSON、步骤数、耗时、执行结果写入
  <data_dir>/plans.json 规划日志（capylulu.plans_store）；
- 资源感知：决策提示中列出技能库内置技能（capylulu.skills_store.load_skills
  的技能名与 tool 字段）与已启用 MCP 工具（capylulu.mcp.store.enabled_servers）；
  direct / plan 的 agent 也可以是「技能库 / MCP」等虚拟资源名，
  由 Leader 全量工具兜底处理。
"""
from __future__ import annotations

import json
import re
import time

from .. import plans_store
from ..skills_store import load_skills
from ..mcp import store as mcp_store
from .prompts import LEADER_PLANNER_PROMPT

# 单步执行失败时自动重试的次数（1 次 = 首跑失败后再试一次）
RETRY_TIMES = 1


class PlannerEngine:
    """规划引擎：负责 chat / direct / plan 三模式决策与执行，并写规划日志。

    用法（由 LeaderAgent 持有）：
        planner = PlannerEngine(llm=leader.llm, max_history=leader.max_history,
                                tool_history=leader.tool_history)
        reply = planner.run(user_input, workers, leader_tools=leader)
    """

    def __init__(self, llm, max_history: int = 32, tool_history: list[str] | None = None):
        self.llm = llm
        self.max_history = max_history
        self.tool_history = tool_history if tool_history is not None else []
        self.last_direct = "总代理"

    # ---------------- 决策 ----------------

    def _resource_summary(self) -> str:
        """构建当前可调度资源清单（技能库 + MCP），注入决策提示。

        技能库取 skills_store.load_skills 的内置技能名与 tool 字段；
        MCP 取 mcp.store.enabled_servers 的启用服务与其 tools_cache 工具名。
        任一部分异常时降级为提示「不可用」，不阻塞决策。
        """
        lines = []
        try:
            skills = load_skills()
            names = [
                f"{s.get('name')}({s.get('tool')})"
                for s in skills if s.get("name") and s.get("tool")
            ]
            if names:
                lines.append("技能库可调度资源：" + "、".join(names))
            else:
                lines.append("技能库可调度资源：（无）")
        except Exception:
            lines.append("技能库可调度资源：（技能库不可用）")
        try:
            servers = mcp_store.enabled_servers()
            if servers:
                descs = []
                for srv in servers:
                    tools = [t.get("name", "") for t in (srv.get("tools_cache") or [])]
                    descs.append(f"{srv.get('name')}" + (f"({','.join(tools)})" if tools else ""))
                lines.append("MCP 可调度资源：" + "、".join(descs))
            else:
                lines.append("MCP 可调度资源：（无启用服务）")
        except Exception:
            lines.append("MCP 可调度资源：（MCP 不可用）")
        return "\n".join(lines)

    def _decide(self, user_input: str, workers: dict) -> dict:
        """调用 LLM 输出调度决策 JSON（chat / direct / plan）。

        容错：容忍 markdown 代码块包裹；JSON 解析失败或格式非法时返回空 dict，
        由 run() 走 Leader 全量工具兜底。
        """
        team = "、".join(workers.keys()) if workers else "（无工作专员）"
        resources = self._resource_summary()
        messages = [
            {"role": "system", "content": LEADER_PLANNER_PROMPT},
            {"role": "user", "content": f"当前团队专员：{team}\n{resources}\n用户需求：{user_input}"},
        ]
        try:
            resp = self.llm.chat(messages, tools=None)
            raw = (resp.get("content") or "").strip()
            raw = re.sub(r"^```(?:json)?\s*|```\s*$", "", raw, flags=re.M).strip()
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("mode") in ("chat", "direct", "plan"):
                return data
        except Exception:
            pass
        return {}

    # ---------------- 执行 ----------------

    def run(self, user_input: str, workers: dict, leader_tools) -> str:
        """规划引擎入口：决策 → 执行 → 写规划日志 → 返回最终回复。

        - workers: {专员名: 工作 Agent}，direct/plan 派发对象；
        - leader_tools: Leader 实例（提供 chat_only / run_task(use_all_tools=True)
          / summarize / summarize_multi 兜底能力）。
        """
        t0 = time.time()
        decision = self._decide(user_input, workers)
        mode = decision.get("mode")
        fallback = False
        results: list[dict] = []

        if mode == "chat":
            reply = (decision.get("reply") or "").strip()
            if not reply:
                reply = leader_tools.chat_only(user_input)
            results = [{"agent": "总代理", "ok": True, "reply": reply}]

        elif mode == "direct":
            who = (decision.get("agent") or "").strip()
            task = (decision.get("task") or user_input).strip()
            result, ok, final_who = self._dispatch(who, task, workers, leader_tools)
            if ok:
                self.last_direct = final_who
                reply = leader_tools.summarize(final_who, result)
            else:
                fallback = True
                reply = self._fallback(user_input, leader_tools)
            results = [{"agent": final_who, "ok": ok, "reply": result}]

        elif mode == "plan":
            steps = decision.get("steps")
            if isinstance(steps, list) and steps:
                plan_reply, results, fallback = self._execute_plan(
                    user_input, steps, workers, leader_tools
                )
                reply = plan_reply
            else:
                fallback = True
                reply = self._fallback(user_input, leader_tools)
                results = []

        else:
            # 决策失败 / 模式不合法：退化为 Leader 全量工具直接处理
            fallback = True
            reply = self._fallback(user_input, leader_tools)
            results = []

        # 规划过程可观测：写 <data_dir>/plans.json
        plans_store.append_plan({
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "input": user_input,
            "mode": mode if mode else "fallback",
            "decision": decision,
            "steps": len(decision.get("steps", [])) if isinstance(decision.get("steps"), list) else 0,
            "duration_ms": int((time.time() - t0) * 1000),
            "fallback": fallback,
            "results": results,
        })
        return reply

    def _dispatch(self, who: str, task: str, workers: dict, leader_tools) -> tuple[str, bool, str]:
        """派发单个子任务：优先工作 Agent，找不到（含虚拟资源名）由 Leader 兜底。

        返回 (结果文本, 是否成功, 最终执行者名)。

        批次6：若 Leader 具备 dispatch_with_escalation（能力匹配路由 + 失败自动升级 +
        任务台账），优先走新链路——单步失败自动重试与升级转交由 Leader 内部承担；
        无该能力时回退旧逻辑（重试 RETRY_TIMES 次，失败即返回）。
        """
        if hasattr(leader_tools, "dispatch_with_escalation"):
            result, final_who, status = leader_tools.dispatch_with_escalation(who, task, workers)
            return result, status in ("done", "escalated"), final_who

        # 旧逻辑（兼容无升级能力的 Leader / 独立测试）
        worker = workers.get(who) if workers else None
        for _ in range(RETRY_TIMES + 1):
            try:
                if worker is None:
                    result = leader_tools.run_task(task, use_all_tools=True)
                else:
                    result = worker.run_task(task)
                if result and result != "(超过最大循环，停下来吃零食了)":
                    return result, True, who
            except Exception:
                pass
        return "（该步骤执行失败，已自动重试）", False, who

    def _execute_plan(self, user_input: str, steps: list, workers: dict,
                      leader_tools) -> tuple[str, list[dict], bool]:
        """plan 模式：按序派发步骤，depends 控制依赖，失败重试，全部失败降级。

        返回 (最终回复, 步骤结果明细, 是否降级)。
        """
        results: list[dict] = []
        completed: set[int] = set()
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            who = str(step.get("agent") or "").strip() or f"步骤{i + 1}"
            task = str(step.get("task") or "").strip()
            if not task:
                task = f"（步骤 {i + 1}）{user_input}"
            deps = step.get("depends") or []
            if isinstance(deps, (int, str)):
                deps = [deps]
            deps = [int(d) for d in deps if isinstance(d, (int, str)) and str(d).isdigit()]
            # 依赖语义：前置步骤未成功完成 → 本步骤跳过并标注「依赖未满足」
            if any(d not in completed for d in deps):
                results.append({
                    "step": i, "agent": who, "ok": False, "skipped": True,
                    "reason": "依赖未满足", "reply": "",
                })
                continue
            result, ok, final_who = self._dispatch(who, task, workers, leader_tools)
            if ok:
                completed.add(i)
            results.append({"step": i, "agent": final_who, "ok": ok, "skipped": False, "reply": result})

        done = [(r["agent"], r["reply"]) for r in results if r.get("ok")]
        if not done:
            # 全部失败（或被依赖跳过）→ 降级：Leader 全量工具兜底整个需求
            fallback_reply = self._fallback(user_input, leader_tools)
            return fallback_reply, results, True
        return leader_tools.summarize_multi(user_input, done), results, False

    def _fallback(self, user_input: str, leader_tools) -> str:
        """降级兜底：Leader 使用全量工具直接处理整个用户需求并汇总。"""
        result = leader_tools.run_task(user_input, use_all_tools=True)
        return leader_tools.summarize("总代理", result)
