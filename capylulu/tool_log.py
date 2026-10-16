"""工具调用记录持久化：<data_dir>/tool_logs.json（追加式，上限 500 条）。

工具记录页从本文件读取，不依赖内存态 agent.tool_history，
避免 Agent 重建 / 内存清理导致页面加载为空或报错。
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import config

STORE = config.data_dir / "tool_logs.json"
MAX_ENTRIES = 500


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global STORE
    STORE = config.data_dir / "tool_logs.json"


def _load() -> list[str]:
    if not STORE.exists():
        return []
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data if x is not None]


def _save(entries: list[str]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def append(text: str) -> None:
    """追加一条记录；非字符串一律防御转字符串，避免渲染页崩溃。"""
    try:
        text = "" if text is None else str(text)
    except Exception:
        text = repr(text)
    entries = _load()
    entries.append(text)
    _save(entries[-MAX_ENTRIES:])


def load() -> list[str]:
    return _load()


def tail(n: int = 240) -> list[str]:
    """取最近 n 条（旧 → 新顺序展示）。"""
    return _load()[-n:]


def clear() -> None:
    _save([])
