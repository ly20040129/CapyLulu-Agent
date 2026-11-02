"""交付物登记台账（P2：deliverables.py）。

存储 <data_dir>/deliverables.json，记录任务产出的交付物（文件路径 / 类型 / 备注 / 时间）。
- register_deliverable  登记一条交付物
- list_deliverables     按任务查询（缺省返回全部）
- unregister_deliverable 注销一条交付物
- 台账文件损坏时防御返回空，不抛错
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from loguru import logger

from .config import config


STORE = config.data_dir / "deliverables.json"


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global STORE
    STORE = config.data_dir / "deliverables.json"


def _load() -> list[dict]:
    """读取台账；不存在/损坏/结构非法时防御返回空。"""
    if not STORE.exists():
        return []
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"[Deliverables] 交付物台账损坏，按空处理：{STORE}（{exc}）")
        return []
    if not isinstance(data, list):
        logger.warning(f"[Deliverables] 交付物台账结构非法（非列表），按空处理：{STORE}")
        return []
    return [d for d in data if isinstance(d, dict)]


def _save(items: list[dict]) -> None:
    """写回台账。"""
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def register_deliverable(task_id: str, path: str, kind: str = "file", note: str = "") -> bool:
    """登记一条交付物；task_id+path 已存在时视为已登记（幂等），返回 True。

    kind 缺省 "file"；note 缺省空串；time 自动取当前时间。
    """
    task_id = str(task_id or "").strip()
    path = str(path or "").strip()
    if not task_id or not path:
        return False
    items = _load()
    for d in items:
        if d.get("task_id") == task_id and d.get("path") == path:
            return True
    items.append({
        "task_id": task_id,
        "path": path,
        "kind": kind or "file",
        "note": note or "",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    try:
        _save(items)
    except OSError as exc:
        logger.warning(f"[Deliverables] 台账写入失败：{STORE}（{exc}）")
        return False
    return True


def list_deliverables(task_id: str | None = None) -> list[dict]:
    """列出交付物；task_id 缺省返回全部条目。"""
    items = _load()
    if task_id is None:
        return items
    tid = str(task_id)
    return [d for d in items if d.get("task_id") == tid]


def unregister_deliverable(task_id: str, path: str) -> bool:
    """注销指定交付物（task_id+path 都匹配才移除）；返回是否真的移除。"""
    tid = str(task_id or "").strip()
    p = str(path or "").strip()
    items = _load()
    remain = [d for d in items if not (d.get("task_id") == tid and d.get("path") == p)]
    if len(remain) == len(items):
        return False
    try:
        _save(remain)
    except OSError as exc:
        logger.warning(f"[Deliverables] 台账写入失败：{STORE}（{exc}）")
        return False
    return True
