"""日程 / 提醒类工具：让对话里一句话就能建定时任务。

复用 capylulu/tasks.py 的自然语言解析（每天 / 每周五 / 今天 / 18:40 / 18：40 / 18点半），
任务落盘到 <data_dir>/tasks.json，由 scheduler 线程到点弹通知 + 生成便签。
"""
from __future__ import annotations

from .. import tasks as taskstore
from .registry import LOW, tool


@tool(
    "create_reminder",
    "创建定时提醒/自动任务。当用户说“每天18:40提醒我下班”“每周五17点提醒我开例会”"
    "“今天9:30记个便签”时调用。text 必须保留用户原句中的时间与事项原文。",
    {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "提醒内容原句，需包含触发时间，例如：每天18:40提醒我下班",
            },
        },
        "required": ["text"],
    },
)
def create_reminder(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "提醒内容为空，没建成。"
    parsed = taskstore.parse_task(text)
    if not parsed:
        return (
            f"没识别出时间，暂时按普通清单记下了：「{text}」。"
            "想定时请带上时间，例如「每天18:40提醒我下班」。"
        )
    taskstore.add(text)
    items = [i for i in taskstore.load() if i.get("text") == text]
    nxt = items[0].get("next") if items else ""
    kind = {"daily": "每天", "weekly": "每周", "once": "一次性", "manual": "仅清单"}.get(
        parsed.get("kind"), parsed.get("kind")
    )
    return f"已建好：{kind} {parsed['time']} · {text}\n下次触发：{nxt or '未排期'}"


@tool(
    "list_reminders",
    "列出已创建的定时提醒/自动任务（含类型、下次触发时间、启停状态）。",
    {"type": "object", "properties": {}},
)
def list_reminders() -> str:
    items = taskstore.load()
    if not items:
        return "还没有定时提醒。可以说「每天18:40提醒我下班」来建一个。"
    lines = []
    for i in items:
        flag = "" if i.get("enabled", True) else "（已停用）"
        lines.append(f"- {i.get('text', '')} · 下次 {i.get('next') or '未排期'}{flag}")
    return "\n".join(lines)


@tool(
    "delete_reminder",
    "按原句删除一条定时提醒/自动任务。",
    {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "要删除的任务原句"}},
        "required": ["text"],
    },
)
def delete_reminder(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return "没说删哪条。"
    before = len(taskstore.load())
    taskstore.remove_by_text(text)
    after = len(taskstore.load())
    if after < before:
        return f"已删除：{text}"
    return f"没找到这条任务：{text}"
