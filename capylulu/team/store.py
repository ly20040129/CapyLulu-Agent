"""任务台账存储：<data_dir>/team_tasks.json。

批次6「多智能体团队升级」：每次委派（含失败自动升级）都会在此记录一条台账，
字段：ts（时间）/ task（任务描述）/ agent（负责 Agent）/ status / result（结果摘要）/
duration_ms（耗时）。状态机：assigned（已派发）→ running（执行中）→ done / failed /
escalated（升级兜底）。

用途：
- Web「管家团队」页「任务台账」面板（列表 + 状态统计）；
- 复盘与记忆蒸馏来源：latest_summary() 输出最近台账摘要，可接入 memory3 情景记忆；
- 数据目录迁移（config.data_dir 变化）后调用 refresh_paths() 对齐路径。
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from ..config import config

STORE = config.data_dir / "team_tasks.json"
MAX_RECORDS = 500  # 最多保留条数，超出丢弃最旧
STATUSES = ("assigned", "running", "done", "failed", "escalated")


def refresh_paths() -> None:
    """数据目录迁移后调用：重新对齐台账文件路径。"""
    global STORE
    STORE = config.data_dir / "team_tasks.json"


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _load() -> list[dict]:
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
    STORE.parent.mkdir(parents=True, exist_ok=True)
    # 原子写：先写临时文件再替换，避免进程中断损坏台账
    tmp = STORE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STORE)


def record(agent: str, task: str, status: str = "assigned", result: str = "",
           duration_ms: int | None = None, ts: str | None = None) -> dict:
    """新增一条委派台账记录。status 非法时回退 assigned。

    agent/task 会自动截断展示长度；result 摘要截断为 500 字。
    """
    if status not in STATUSES:
        status = "assigned"
    item = {
        "id": uuid.uuid4().hex[:12],
        "ts": ts or now_str(),
        "task": (task or "")[:300],
        "agent": (agent or "总代理")[:50],
        "status": status,
        "result": (result or "")[:500],
        "duration_ms": duration_ms,
    }
    items = _load()
    items.append(item)
    if len(items) > MAX_RECORDS:
        items = items[-MAX_RECORDS:]
    _save(items)
    return item


def load_tasks() -> list[dict]:
    """返回全部台账（按写入顺序，旧 → 新）。"""
    return _load()


def recent(limit: int = 100) -> list[dict]:
    """返回最近 limit 条台账（新 → 旧）。"""
    items = _load()
    return list(reversed(items[-limit:]))


def stats() -> dict:
    """状态统计：总数 + 各状态计数（assigned/running/done/failed/escalated）。"""
    items = _load()
    by_status = {s: 0 for s in STATUSES}
    for it in items:
        s = it.get("status", "assigned")
        if s in by_status:
            by_status[s] += 1
    return {"total": len(items), "by_status": by_status}


def clear() -> int:
    """清空任务台账，返回删除条数。"""
    n = len(_load())
    _save([])
    return n


def latest_summary(limit: int = 10) -> str:
    """最近台账摘要（复盘 / 记忆蒸馏来源）：逐条 时间 | Agent | 状态 | 任务。"""
    rows = recent(limit)
    if not rows:
        return "（暂无任务台账）"
    lines = []
    for it in rows:
        lines.append(
            f"{it.get('ts', '?')} | {it.get('agent', '?')} | {it.get('status', '?')} | {it.get('task', '?')}"
        )
    return "\n".join(lines)
