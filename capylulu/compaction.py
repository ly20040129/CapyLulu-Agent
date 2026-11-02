"""上下文压缩：从 BaseAgent._compress 抽离增强，独立成可复用模块。

compress_messages 与旧 BaseAgent._compress 行为完全等价：
- 超阈值（len(messages) > threshold）时把更早消息经 LLM 摘要压缩为
  [system, 历史摘要system, recent]；
- 摘要消息加 "历史摘要（供上下文参考）：" 前缀；
- LLM 摘要失败回退 "（旧对话已省略，仅保留最近上下文）"；
- 触发压缩且事件日志开启（config.agent.event_log）时，向 history_events
  写入 compress 事件（summary=摘要），由本模块内部完成、调用方无需重复写。
阈值：config.agent.compaction_threshold 优先，缺省沿用传入的 max_history。
"""
from __future__ import annotations

from loguru import logger

from .config import config
from .history_events import append_event

DEFAULT_PROMPT = (
    "请把对话历史压缩成中文要点摘要，必须保留以下信息：\n"
    "1) 用户的原始请求和核心意图（尽量保留原话关键词）；\n"
    "2) 已执行的操作与结果，尤其是文件路径、数字、结论、网址等关键事实；\n"
    "3) 未完成事项 / 待办 / 用户后续追问；\n"
    "4) 用户偏好、语气、已确认的约束条件。\n"
    "按时间顺序输出，控制在 12 句以内，不要省略重要事实。"
)

SUMMARY_PREFIX = "历史摘要（供上下文参考）："
FALLBACK_SUMMARY = "（旧对话已省略，仅保留最近上下文）"


def _threshold(max_history: int) -> int:
    """压缩阈值：config.agent.compaction_threshold 优先，缺省沿用 max_history。"""
    try:
        v = int(config.agent.get("compaction_threshold") or max_history)
    except (TypeError, ValueError):
        v = max_history
    return max(v, 2)  # 至少保留最近 2 条（保证切片有意义）


def compress_messages(messages: list[dict], llm, max_history: int,
                      prompt: str | None = None,
                      sess_id: str | None = None) -> list[dict]:
    """把旧消息经 LLM 摘要压缩为 [system, 历史摘要system, recent]。

    参数：
        messages: 完整消息列表（首条为 system prompt）。
        llm: 支持 chat(messages, tools=None) -> {"content": str} 的客户端。
        max_history: 压缩阈值基数（config.agent.compaction_threshold 可覆盖）。
        prompt: 摘要指令；None 时用默认摘要指令。
        sess_id: 会话事件日志 id；触发压缩且事件日志开启时写 compress 事件
                 （None 时不写事件）。
    返回：
        压缩后的新消息列表；未超阈值时原样返回。
    行为与旧 BaseAgent._compress 完全等价（摘要前缀、失败回退文案一致）。
    """
    threshold = _threshold(max_history)
    if len(messages) <= threshold:
        return messages
    old, recent = messages[: -threshold + 2], messages[-threshold + 2:]
    blob = "\n".join(f"{m['role']}: {m['content'][:400]}" for m in old)
    try:
        resp = llm.chat([
            {"role": "system", "content": prompt or DEFAULT_PROMPT},
            {"role": "user", "content": blob[:8000]},
        ], tools=None)
        summary = resp.get("content") or ""
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[Compaction] LLM 摘要失败，回退省略策略：{e}")
        summary = FALLBACK_SUMMARY
    if sess_id:
        append_event(sess_id, {"type": "compress", "summary": summary})
    return (
        [messages[0]]
        + [{"role": "system", "content": SUMMARY_PREFIX + summary}]
        + recent
    )
