"""LeaderAgent：总代理。负责闲聊、意图识别（路由）、任务派发、复杂任务规划编排与结果汇总。

规划编排自 v2 起委托给独立规划引擎 PlannerEngine（agent/planner.py）：
- LeaderAgent 持有 self.planner，run_orchestrated 只做「决策 → 执行 → 汇总」的门面转发；
- 规划过程（决策 JSON / 步骤数 / 耗时 / 结果）由 PlannerEngine 写入 data/plans.json；
- 本文件保留 summarize / summarize_multi 供 PlannerEngine 调用。

批次6「多智能体团队升级」：
- 委派前按 capabilities 能力标签做关键字匹配路由（能力优先，无命中回退名称路由）；
- 委派失败自动升级：按能力转交其他工作 Agent，仍失败由 Leader 全量工具兜底；
- 每次委派（含升级链路）写入任务台账 <data_dir>/team_tasks.json（capylulu.team.store）。
"""
import json
import re
import time

from .base import BaseAgent
from .planner import PlannerEngine
from .prompts import LEADER_PROMPT, LEADER_PLANNER_PROMPT

# 单步执行失败时自动重试的次数（与 planner.RETRY_TIMES 对齐：1 次 = 首跑失败后再试一次）
_RETRY_TIMES = 1


def match_by_capability(task: str, worker_names: list[str],
                        agents: list[dict] | None = None) -> str | None:
    """能力匹配路由（纯逻辑，可独立测试）：任务文本命中某 Agent 的 capabilities
    标签（子串包含）时返回该 Agent 名；无命中返回 None。

    - 只考虑启用的、非总代理的、且在当前 worker 集合中的 Agent；
    - 按配置顺序优先（先文件管家再电脑管家…），同一任务命中多个时取配置靠前者。
    """
    if not worker_names:
        return None
    if agents is None:
        from .. import agents_store
        agents = agents_store.list_agents()
    for a in agents:
        name = a.get("name") or ""
        if name == "总代理" or name not in worker_names:
            continue
        if not a.get("enabled", True):
            continue
        caps = a.get("capabilities") or []
        if any((c or "").strip() and c.strip() in (task or "") for c in caps):
            return name
    return None


class LeaderAgent(BaseAgent):
    """总代理：不亲手干重活；识别意图后派发给对应工作 Agent，复杂任务先拆解再带队执行，并把结果汇总成回复。"""

    def __init__(self, llm, max_iterations: int, max_history: int, tool_history: list[str]):
        super().__init__(
            name="总代理",
            system_prompt=LEADER_PROMPT,
            tools=None,  # Leader 默认不带工具，闲聊/汇总直接答；兜底场景由 run_task(use_all_tools=True)
            llm=llm,
            max_iterations=max_iterations,
            max_history=max_history,
            tool_history=tool_history,
        )
        # 规划引擎：负责 chat / direct / plan 三模式决策与执行，并写规划日志
        self.planner = PlannerEngine(
            llm=self.llm,
            max_history=self.max_history,
            tool_history=self.tool_history,
        )

    def chat_only(self, user_input: str) -> str:
        """纯闲聊：不带工具，直接答（不派发任务）。"""
        self.messages.append({"role": "user", "content": user_input})
        self._compress()
        resp = self.llm.chat(self.messages, tools=None)
        content = resp.get("content") or "(噜噜沉默了)"
        self.messages.append({"role": "assistant", "content": content})
        return content

    def summarize(self, who: str, worker_reply: str) -> str:
        """工作 Agent 执行结果回传 Leader 后，汇总成给用户的回复（保持佛系语气）。"""
        messages = [
            {"role": "system", "content": LEADER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"任务已由「{who}」完成，它的汇报如下：\n{worker_reply}\n"
                    "请用噜噜的语气把结果简短转述给用户：保留关键事实（路径/数字/结论），"
                    "不要编造新事实，不要罗列工具调用细节。"
                ),
            },
        ]
        try:
            resp = self.llm.chat(messages, tools=None)
            reply = (resp.get("content") or "").strip()
        except Exception:
            reply = ""
        return reply or worker_reply

    # ---------------- 带队型调度（run_orchestrated） ----------------

    # ---------------- 批次6：能力路由 + 失败自动升级 + 任务台账 ----------------

    def route_agent(self, who: str, task: str, workers: dict) -> str | None:
        """委派前路由：capabilities 能力标签关键字匹配优先，无命中回退原名称路由。

        返回最终执行者名；若 workers 为空或目标不可用返回 None（表示 Leader 兜底）。
        """
        if not workers:
            return None
        worker_names = list(workers.keys())
        hit = match_by_capability(task, worker_names)
        if hit:
            return hit
        # 无能力命中：回退现有名称路由（校验 who 在当前 worker 集合中）
        return who if who in workers else None

    def dispatch_with_escalation(self, who: str, task: str, workers: dict) -> tuple[str, str, str]:
        """派发单任务（含任务台账与自动升级），返回 (结果文本, 最终执行者, 状态)。

        链路：
        1. route_agent 能力匹配优先选定执行者（无命中回退 who / Leader 兜底）；
        2. 首选候选执行失败自动重试 _RETRY_TIMES 次；
        3. 仍失败 → 自动升级：按能力依次转交其他未尝试的工作 Agent（各试 1 次）；
        4. 全部工作 Agent 失败 → Leader 全量工具兜底（状态 escalated）；
        5. 兜底也失败 → 标记 failed。

        每次委派写入任务台账 <data_dir>/team_tasks.json：
        时间 / 任务 / 负责 Agent / 状态[assigned|running|done|failed|escalated] /
        结果摘要 / 耗时。升级转交的每一次尝试都会追加 running 记录。
        """
        from .. import team  # 延迟导入避免循环

        final_agent = self.route_agent(who, task, workers)
        if final_agent is None:
            final_agent = "总代理"
        t0 = time.time()
        team.record(final_agent, task, status="running")

        def _done(agent: str, result: str) -> tuple[str, str, str]:
            team.record(agent, task, status="done",
                        result=result, duration_ms=int((time.time() - t0) * 1000))
            return result, agent, "done"

        def _escalated(result: str) -> tuple[str, str, str]:
            team.record("总代理", task, status="escalated",
                        result=result, duration_ms=int((time.time() - t0) * 1000))
            return result, "总代理", "escalated"

        def _failed(reason: str) -> tuple[str, str, str]:
            team.record(final_agent, task, status="failed",
                        result=reason, duration_ms=int((time.time() - t0) * 1000))
            return f"（任务委派失败：{reason}）", final_agent, "failed"

        def _run(agent: str | None, use_all: bool) -> str | None:
            """执行一次：成功返回结果文本，失败/异常返回 None。"""
            try:
                if use_all:
                    result = self.run_task(task, use_all_tools=True)
                elif agent is not None:
                    result = workers[agent].run_task(task)
                else:
                    return None
                if result and result != "(超过最大循环，停下来吃零食了)":
                    return result
            except Exception:
                pass
            return None

        tried: list[str] = []

        # 首选候选：能力路由命中（或名称路由命中）的工作 Agent，失败自动重试
        if final_agent in workers:
            for _ in range(_RETRY_TIMES + 1):
                result = _run(final_agent, use_all=False)
                if result is not None:
                    return _done(final_agent, result)
            tried.append(final_agent)
            team.record(final_agent, task, status="running", result="首选失败，尝试自动升级")
        else:
            # 无可用工作 Agent（如虚拟资源名）：直接 Leader 兜底
            result = _run(None, use_all=True)
            if result is not None:
                return _escalated(result)
            return _failed("无可用专员且 Leader 兜底失败")

        # 自动升级：按能力匹配依次转交其他未尝试的工作 Agent（各试 1 次）
        worker_names = list(workers.keys())
        for name in worker_names:
            if name == final_agent or name in tried:
                continue
            cap_hit = match_by_capability(task, [name])
            if not cap_hit:
                continue
            tried.append(name)
            team.record(name, task, status="running", result="自动升级转交")
            result = _run(name, use_all=False)
            if result is not None:
                return _done(name, result)

        # 仍失败：Leader 全量工具兜底
        result = _run(None, use_all=True)
        if result is not None:
            return _escalated(result)
        return _failed("全部专员与 Leader 兜底均失败")

    def _decide(self, user_input: str, worker_names: list[str]) -> dict:
        """调度决策：chat / direct / plan。JSON 解析失败或格式非法时返回空 dict。

        兼容保留：v2 起决策已由 PlannerEngine._decide 接管（增强资源感知与重试语义），
        此处仅供外部显式调用 / 旧引用兜底。
        """
        team = "、".join(worker_names)
        messages = [
            {"role": "system", "content": LEADER_PLANNER_PROMPT},
            {"role": "user", "content": f"当前团队专员：{team}\n用户需求：{user_input}"},
        ]
        try:
            resp = self.llm.chat(messages, tools=None)
            raw = (resp.get("content") or "").strip()
            # 容忍 markdown 代码块包裹
            raw = re.sub(r"^```(?:json)?\s*|```\s*$", "", raw, flags=re.M).strip()
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("mode") in ("chat", "direct", "plan"):
                return data
        except Exception:
            pass
        return {}

    def run_orchestrated(self, user_input: str, workers: dict) -> str:
        """带队型调度：委托规划引擎决策 → chat / direct / plan 执行并汇总。

        自 v2 起由 self.planner（PlannerEngine）接管决策与执行，
        规划过程写入 data/plans.json；此处保持原签名，兼容 chat_only / run_task 路由。
        """
        self.messages.append({"role": "user", "content": user_input})
        self._compress()
        return self.planner.run(user_input, workers, leader_tools=self)

    def _execute_plan(self, user_input: str, steps: list, workers: dict) -> str:
        """按步骤依次派发，收集各专员结果后统一汇总。

        兼容保留：v2 起 plan 执行已由 PlannerEngine._execute_plan 接管
        （支持 depends 依赖、失败重试与全失败降级），此处仅供旧引用兜底。
        """
        results: list[tuple[str, str]] = []
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            who = str(step.get("agent") or "").strip() or f"步骤{i + 1}"
            task = str(step.get("task") or "").strip()
            if not task:
                task = f"（步骤 {i + 1}）{user_input}"
            worker = workers.get(who)
            if worker is None:
                result = self.run_task(task, use_all_tools=True)
            else:
                result = worker.run_task(task)
            results.append((who, result))
        if not results:
            results = [("总代理", self.run_task(user_input, use_all_tools=True))]
        return self.summarize_multi(user_input, results)

    def summarize_multi(self, user_input: str, results: list[tuple[str, str]]) -> str:
        """多个专员执行结果统一汇总成给用户的回复（按任务逻辑整合，不编造）。"""
        blocks = [f"【{who}】\n{reply}" for who, reply in results]
        messages = [
            {"role": "system", "content": LEADER_PROMPT},
            {
                "role": "user",
                "content": (
                    f"用户需求：{user_input}\n\n"
                    f"已派「{'、'.join(w for w, _ in results)}」协作完成，各专员汇报如下：\n"
                    + "\n\n".join(blocks)
                    + "\n请以噜噜语气整合成一份完整结果给用户：保留关键事实（路径/数字/结论），"
                      "不要编造新事实，不要罗列工具调用细节，按任务逻辑组织。"
                ),
            },
        ]
        try:
            resp = self.llm.chat(messages, tools=None)
            reply = (resp.get("content") or "").strip()
        except Exception:
            reply = ""
        return reply or "\n\n".join(blocks)
