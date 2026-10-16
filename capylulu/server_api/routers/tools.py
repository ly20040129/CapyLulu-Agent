"""工具记录：日志尾部、清空。"""
from __future__ import annotations

from fastapi import APIRouter

from capylulu import tool_log

router = APIRouter(tags=["tools"])


@router.get("/tools/logs")
def tool_logs(n: int = 240) -> dict:
    return {"items": tool_log.tail(n)}


@router.post("/tools/clear")
def clear_logs() -> dict:
    tool_log.clear()
    return {"ok": True}
