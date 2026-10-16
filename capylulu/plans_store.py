"""规划日志存储：<data_dir>/plans.json。

记录规划引擎（PlannerEngine）每次规划的决策 JSON、步骤数、耗时与执行结果，
供「规划过程可观测」使用。读写风格与 skills_store.py 保持一致：
- STORE 由 config.data_dir 驱动，与 skills.json / agents.json 同级；
- 数据目录迁移后调用 refresh_paths() 刷新路径常量。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .config import config

STORE = config.data_dir / "plans.json"

MAX_RECORDS = 200  # 日志上限，超出丢弃最旧记录，避免无限膨胀


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global STORE
    STORE = config.data_dir / "plans.json"


def _load() -> list[dict]:
    """读取全部规划记录；文件不存在或损坏时返回空列表。"""
    if not STORE.exists():
        return []
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _save(items: list[dict]) -> None:
    """原子落盘：先写临时文件再替换，避免写入中断损坏日志。"""
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STORE)


def append_plan(record: dict) -> None:
    """追加一条规划记录（决策 JSON / 步骤数 / 耗时 / 执行结果）。

    record 至少含 ts / input / mode；缺失字段由调用方补全，此处只做兜底。
    超过 MAX_RECORDS 时丢弃最旧记录。
    """
    if not isinstance(record, dict):
        return
    items = _load()
    items.append(record)
    if len(items) > MAX_RECORDS:
        items = items[-MAX_RECORDS:]
    _save(items)


def load_plans() -> list[dict]:
    """读取全部规划记录（新的在后，用于展示/排查）。"""
    return _load()


def recent(n: int = 20) -> list[dict]:
    """取最近 n 条规划记录，新的在前。"""
    items = _load()
    return list(reversed(items[-n:])) if n > 0 else []
