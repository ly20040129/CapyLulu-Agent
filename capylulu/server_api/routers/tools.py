"""工具记录：日志尾部、清空。

- GET  /tools/logs：工具调用日志尾部；
- POST /tools/clear：清空工具调用日志。
"""
from __future__ import annotations

from fastapi import APIRouter

from capylulu import tool_log

router = APIRouter(tags=["tools"])


@router.get("/tools/logs")
def tool_logs(n: int = 240) -> dict:
    """返回最近 n 条工具调用日志。"""
    return {"items": tool_log.tail(n)}


@router.post("/tools/clear")
def clear_logs() -> dict:
    """清空全部工具调用日志。"""
    tool_log.clear()
    return {"ok": True}
