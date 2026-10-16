"""多智能体团队协作包：任务台账（team_tasks.json）等团队级能力。

- store.py：委派任务台账，记录每次委派的时间 / 任务 / 负责 Agent / 状态 /
  结果摘要 / 耗时，落盘 <data_dir>/team_tasks.json，作为复盘与记忆蒸馏来源。
"""
from .store import (
    refresh_paths,
    record,
    load_tasks,
    recent,
    stats,
    clear,
    latest_summary,
)

__all__ = [
    "refresh_paths",
    "record",
    "load_tasks",
    "recent",
    "stats",
    "clear",
    "latest_summary",
]
