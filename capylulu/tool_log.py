"""工具调用记录持久化：<data_dir>/tool_logs.json（追加式，上限 500 条）。

工具记录页从本文件读取，不依赖内存态 agent.tool_history，
避免 Agent 重建 / 内存清理导致页面加载为空或报错。
新记录带 owner / tokens 字段（身份归属 + 用量计量）；旧数据（纯字符串）读取时兼容。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from loguru import logger

from . import auth
from .config import config

STORE = config.data_dir / "tool_logs.json"  # 工具调用记录文件
MAX_ENTRIES = 500  # 记录上限，超出丢弃最旧
DEFAULT_OWNER = "default"  # 未登录默认身份


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global STORE
    STORE = config.data_dir / "tool_logs.json"


def _now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _normalize(entry) -> dict:
    """存储条目归一化为 dict：旧字符串补 default/0，新 dict 补缺省字段。"""
    if isinstance(entry, dict):
        text = entry.get("text")
        return {
            "text": "" if text is None else str(text),
            "owner": str(entry.get("owner") or DEFAULT_OWNER),
            "tokens": max(0, int(entry.get("tokens") or 0)),
            "time": str(entry.get("time") or ""),
        }
    text = "" if entry is None else str(entry)
    return {"text": text, "owner": DEFAULT_OWNER, "tokens": 0, "time": ""}


def _load() -> list[dict]:
    if not STORE.exists():
        return []
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"[ToolLog] 日志文件损坏，返回空记录：{STORE}")
        return []
    if not isinstance(data, list):
        return []
    return [_normalize(x) for x in data if x is not None]


def _save(entries: list[dict]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_owner(owner: str) -> str:
    """owner 为空时取当前登录用户 uid，未登录为 default。"""
    if owner:
        return str(owner).strip() or DEFAULT_OWNER
    user = auth.current_user()
    return str(user.get("uid")) if user and user.get("uid") else DEFAULT_OWNER


def append(text: str, owner: str = "", tokens: int = 0) -> None:
    """追加一条记录（可选 owner / tokens，owner 留空自动取登录用户）；非字符串一律防御转字符串。"""
    try:
        text = "" if text is None else str(text)
    except Exception:
        text = repr(text)
    entry = {
        "text": text,
        "owner": _resolve_owner(owner),
        "tokens": max(0, int(tokens or 0)),
        "time": _now_str(),
    }
    entries = _load()
    entries.append(entry)
    _save(entries[-MAX_ENTRIES:])
    logger.info(f"[ToolLog] 已记录工具调用：{text[:60]}")


def load() -> list[str]:
    """全部记录（字符串列表，兼容旧前端展示）。"""
    return [x["text"] for x in _load()]


def load_raw() -> list[dict]:
    """带 owner / tokens 的结构化记录列表。"""
    return _load()


def tail(n: int = 240) -> list[str]:
    """取最近 n 条（旧 → 新顺序展示）。"""
    return [x["text"] for x in _load()[-n:]]


def clear() -> None:
    _save([])
    logger.info("[ToolLog] 已清空工具调用记录")
