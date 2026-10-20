"""BaseAgent：每个 Agent 独立的 system prompt 与上下文管理（多 Agent 架构基础）。"""
import json

from .. import tool_log
from ..tools.registry import get_tool_schemas, call_tool

COMPRESS_PROMPT = (
    "请把对话历史压缩成中文要点摘要，必须保留以下信息：\n"
    "1) 用户的原始请求和核心意图（尽量保留原话关键词）；\n"
    "2) 已执行的操作与结果，尤其是文件路径、数字、结论、网址等关键事实；\n"
    "3) 未完成事项 / 待办 / 用户后续追问；\n"
    "4) 用户偏好、语气、已确认的约束条件。\n"
    "按时间顺序输出，控制在 12 句以内，不要省略重要事实。"
)


class BaseAgent:
    """工作 Agent 基类：独立上下文（messages）+ 工具循环 + 历史压缩。

    每个 Agent 实例维护自己的 messages 轮次，上下文互不共享；
    tools 为 None 表示不提供工具（纯聊天），否则限定为所属工具集。
    """

    def __init__(self, name: str, system_prompt: str, tools: list[str] | None,
                 llm, max_iterations: int = 10, max_history: int = 32,
                 tool_history: list[str] | None = None):
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.llm = llm
        self.max_iterations = max_iterations
        self.max_history = max_history
        self.tool_history = tool_history if tool_history is not None else []
        self.messages: list[dict] = [{"role": "system", "content": system_prompt}]

    def reset(self) -> None:
        """清空独立上下文（保留 system prompt）。"""
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def seed_history(self, chat_history: list | None) -> None:
        """首次运行时用外部全局历史初始化独立上下文（仅当尚无对话轮次）。"""
        if chat_history and len(self.messages) == 1:
            for m in chat_history:
                role, content = m.get("role"), m.get("content")
                if role in ("user", "assistant") and isinstance(content, str) and content.strip():
                    self.messages.append({"role": role, "content": content})

    def _compress(self) -> None:
        """超出 max_history 时，把更早的对话压成摘要（保留意图与关键事实）。"""
        if len(self.messages) <= self.max_history:
            return
        old, recent = self.messages[: -self.max_history + 2], self.messages[-self.max_history + 2:]
        blob = "\n".join(f"{m['role']}: {m['content'][:400]}" for m in old)
        try:
            resp = self.llm.chat([
                {"role": "system", "content": COMPRESS_PROMPT},
                {"role": "user", "content": blob[:8000]},
            ], tools=None)
            summary = resp.get("content") or ""
        except Exception:
            summary = "（旧对话已省略，仅保留最近上下文）"
        self.messages = (
            [self.messages[0]]
            + [{"role": "system", "content": "历史摘要（供上下文参考）：" + summary}]
            + recent
        )

    def run_task(self, user_input: str, use_all_tools: bool = False) -> str:
        """执行一次任务：独立上下文 + 工具循环，返回最终回复。

        use_all_tools=True 时使用全量工具（Leader 兜底场景）。
        """
        self.messages.append({"role": "user", "content": user_input})
        self._compress()

        if use_all_tools:
            use_tools = get_tool_schemas()
            self.messages.append({
                "role": "user",
                "content": (
                    "（你有全量工具可用，请先真实调用合适的工具完成任务，"
                    "再基于工具返回结果总结；禁止不调用工具直接给出结论。）"
                ),
            })
        else:
            use_tools = None if self.tools is None else get_tool_schemas(self.tools)

        # 防幻觉：任务要求工具时，若模型从头到尾没调用任何工具就声称完成，
        # 追加提示强制其真实调用工具（最多 2 次），仍不调用则给回复打上警示标记。
        tool_used = 0
        no_tool_tries = 0
        # 同类失败熔断：同一工具连续失败 >= 2 次时注入停止提示；已熔断工具再次被调用则中止任务
        blocked_tools: set[str] = set()
        blocked_reason: dict[str, str] = {}
        last_fail_tool: str | None = None
        fail_streak = 0
        # 最后一次工具调用是否失败（用于收尾时强制如实标记失败，防"工具失败后总结编造成功"）
        last_tool_failed = False
        last_fail_info = ""
        # 连续调用工具名记录：连续 ≥4 次同一工具且无进展时强制打断，防死循环
        recent_tools: list[str] = []
        forced_breaks = 0

        for _ in range(self.max_iterations):
            if len(recent_tools) >= 4 and all(t == recent_tools[-1] for t in recent_tools[-4:]):
                name = recent_tools[-1]
                forced_breaks += 1
                if forced_breaks >= 2:
                    return (f"（{self.name} 任务未完成：连续多次调用同一工具 {name} 无进展，"
                            f"已终止；最近结果：{last_fail_info or '无'}）")
                # 第一次打断：强制基于已有数据直接汇报，禁止再调用工具
                self.messages.append({
                    "role": "user",
                    "content": (
                        f"你已连续 {len(recent_tools[-4:])} 次调用同一工具 {name} 且结果无进展。"
                        "立即停止调用任何工具，基于对话中已有的真实数据直接给出最终汇报；"
                        "若已有数据不足以完成任务，如实说明缺失并结束任务。"
                    ),
                })
                recent_tools.clear()
                continue
            resp = self.llm.chat(self.messages, tools=use_tools)
            content = resp.get("content")
            tool_calls = resp.get("tool_calls")
            if not tool_calls:
                reply = content or "(噜噜沉默了)"
                if use_tools and tool_used == 0 and no_tool_tries < 2:
                    no_tool_tries += 1
                    self.messages.append({
                        "role": "user",
                        "content": "注意：你尚未调用任何工具。请立即调用合适的工具真实执行本任务，"
                                   "再基于工具返回结果给出总结；不要直接回复臆测的结果，也不要反问用户。",
                    })
                    continue
                self.messages.append({"role": "assistant", "content": reply})
                if last_tool_failed:
                    return (f"（{self.name} 最后调用的工具执行失败，任务未完成；"
                            f"失败信息：{last_fail_info}）")
                if use_tools and tool_used == 0:
                    # 已注入前置步骤真实结果的任务（planner 依赖步骤），
                    # 若仅需基于已有数据整理/挑选，可直接完成无需调用工具；
                    # 但任务仍要求真实动作（打开/关闭/保存/写入/点击/下载/提取等）时，
                    # 不调用工具直接回复即视为编造，必须标记未执行。
                    if "前置步骤的真实执行结果" not in user_input or any(
                        w in user_input for w in ("打开", "关闭", "保存", "写入", "点击",
                                                  "下载", "提取", "搜索", "移动", "删除",
                                                  "重启", "设置", "输入", "填写", "启动",
                                                  "打开网址", "跳转", "按键", "截图")
                    ):
                        return f"（未实际调用任何工具，以下回复未经真实执行，请人工核实：）\n{reply}"
                return reply

            tool_used += 1

            assistant_msg = {"role": "assistant", "content": content or ""}
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": tc["function"]["arguments"],
                    },
                }
                for tc in tool_calls
            ]
            self.messages.append(assistant_msg)
            for tc in tool_calls:
                name = tc["function"]["name"]
                if name in blocked_tools:
                    return (f"（工具 {name} 已因连续失败被熔断，任务中止；"
                            f"最近失败原因：{blocked_reason.get(name, '')[:200]}）")
                # LLM 对无参工具常返回空串/None/"null"/"[]"，必须容错解析，
                # 否则 json.loads(None) 抛 TypeError 或解析出 None 导致 call_tool 崩溃
                raw = tc["function"].get("arguments")
                try:
                    args = json.loads(raw) if isinstance(raw, str) and raw else {}
                except (json.JSONDecodeError, TypeError):
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                self.tool_history.append(f"🔧 {self.name} · {name}({args})")
                tool_log.append(f"🔧 {self.name} · {name}({args})")
                result = call_tool(name, args)
                recent_tools.append(name)
                self.tool_history.append(f"  → {result[:240]}")
                tool_log.append(f"  → {result[:240]}")
                self.messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
                # 同类失败熔断检测
                is_fail = "失败" in result[:60]
                last_tool_failed = is_fail
                if is_fail:
                    last_fail_info = result[:200]
                if is_fail and name == last_fail_tool:
                    fail_streak += 1
                elif is_fail:
                    last_fail_tool, fail_streak = name, 1
                else:
                    last_fail_tool, fail_streak = None, 0
                if is_fail and fail_streak >= 2 and name not in blocked_tools:
                    blocked_tools.add(name)
                    blocked_reason[name] = result[:200]
                    self.messages.append({
                        "role": "user",
                        "content": f"你连续调用 {name} 至少 2 次均失败。立即停止继续调用 {name}，"
                                   "改用其他方式完成目标，或如实向用户汇报失败原因并结束任务。",
                    })
                    self.messages.append({
                        "role": "assistant",
                        "content": f"（{name} 连续失败，停止尝试，转入其他方案或如实汇报）",
                    })

        return "(超过最大循环，停下来吃零食了)"
