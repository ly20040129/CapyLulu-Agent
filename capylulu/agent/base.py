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
        else:
            use_tools = None if self.tools is None else get_tool_schemas(self.tools)

        for _ in range(self.max_iterations):
            resp = self.llm.chat(self.messages, tools=use_tools)
            content = resp.get("content")
            tool_calls = resp.get("tool_calls")
            if not tool_calls:
                reply = content or "(噜噜沉默了)"
                self.messages.append({"role": "assistant", "content": reply})
                return reply

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
                self.tool_history.append(f"  → {result[:240]}")
                tool_log.append(f"  → {result[:240]}")
                self.messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result})

        return "(超过最大循环，停下来吃零食了)"
