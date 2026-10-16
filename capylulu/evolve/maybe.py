"""maybe_evolve：按间隔或新增任务数自动触发反思 + 改进。

批次7「自主进化」的触发层：维护 <data_dir>/evolve/.last_evolve.json
（记录上次触发时间戳与当时的台账条数），满足任一条件即联动执行：

- 距上次触发超过 interval_seconds（默认 3600）；
- 距上次触发后新增任务数 >= min_new_tasks（默认 3）。

不引入调度框架，与 memory3 的 maybe_auto_dream 同风格（纯时间戳 + 计数判断）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from ..config import config
from .. import team
from . import improve, reflect

LAST_EVOLVE_FILE = config.data_dir / "evolve" / ".last_evolve.json"
DEFAULT_INTERVAL = 3600
DEFAULT_MIN_TASKS = 3


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global LAST_EVOLVE_FILE
    LAST_EVOLVE_FILE = config.data_dir / "evolve" / ".last_evolve.json"


def _last_state() -> dict:
    try:
        data = json.loads(LAST_EVOLVE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _mark_state() -> None:
    LAST_EVOLVE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_EVOLVE_FILE.write_text(
        json.dumps({"ts": time.time(), "task_count": len(team.load_tasks())},
                   ensure_ascii=False),
        encoding="utf-8",
    )


def status() -> dict:
    """上次触发状态（供前端展示）。"""
    last = _last_state()
    ts = float(last.get("ts") or 0)
    return {
        "last_ts": ts,
        "last_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else None,
        "last_task_count": last.get("task_count", 0),
        "current_task_count": len(team.load_tasks()),
        "lesson_count": 0,   # 由路由层用 lessons.stats() 覆盖
        "log_count": 0,
    }


def maybe_evolve(interval_seconds: int = DEFAULT_INTERVAL,
                 min_new_tasks: int = DEFAULT_MIN_TASKS,
                 limit: int = 20,
                 max_auto: int = improve.DEFAULT_MAX_AUTO,
                 force: bool = False) -> dict:
    """按间隔 / 新增任务数触发「反思 + 改进」；force=True 无条件执行。

    返回结构：
    {"triggered": bool, "reason": str, "reflect": {...}, "improve": {...}}
    """
    if interval_seconds < 60:
        interval_seconds = DEFAULT_INTERVAL
    if min_new_tasks < 1:
        min_new_tasks = DEFAULT_MIN_TASKS

    if force:
        r = reflect.reflect(limit=limit, force=True)
        i = improve.improve(max_auto=max_auto, force=True)
        _mark_state()
        return {"triggered": True, "reason": "force", "reflect": r, "improve": i}

    last = _last_state()
    now = time.time()
    elapsed = now - float(last.get("ts") or 0)
    last_count = int(last.get("task_count", 0))
    new_tasks = max(0, len(team.load_tasks()) - last_count)

    if elapsed >= interval_seconds and new_tasks >= min_new_tasks:
        r = reflect.reflect(limit=limit, force=True)
        i = improve.improve(max_auto=max_auto, force=True)
        _mark_state()
        return {"triggered": True, "reason": "interval_and_tasks", "reflect": r, "improve": i}

    # 未触发：给出原因（供前端 / 工具返回可读信息）
    reasons = []
    if elapsed < interval_seconds:
        remain = int(interval_seconds - elapsed)
        reasons.append(f"距上次触发 {int(elapsed)}s，还需 {remain}s 到达间隔 {interval_seconds}s")
    if new_tasks < min_new_tasks:
        reasons.append(f"新增任务 {new_tasks} 条，未达到 {min_new_tasks} 条阈值")
    if not reasons:
        reasons.append("间隔与任务数均满足，但首次运行以计数为准")
    return {
        "triggered": False,
        "reason": "；".join(reasons),
        "reflect": {"reflected": 0, "added": 0, "message": "未触发反思"},
        "improve": {"considered": 0, "applied": 0, "message": "未触发改进"},
    }
