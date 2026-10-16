"""经验库：<data_dir>/evolve/lessons.json。

批次7「自主进化」的经验沉淀层：反思引擎（reflect）提炼的经验统一落在这里，
自我改进（improve）从这里取建议应用，Web「自主进化」页可增删查。

条目字段：
- id：唯一标识
- trigger：触发条件（什么场景适用这条经验）
- advice：建议内容（做什么 / 不做什么）
- task_ref：来源任务引用（任务台账摘要，可多个，逗号分隔）
- confidence：置信度（0~1）
- applied：已应用次数
- created_at：创建时间
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from ..config import config

LESSONS_FILE = config.data_dir / "evolve" / "lessons.json"
MAX_LESSONS = 500  # 经验库上限，超出丢弃最旧


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global LESSONS_FILE
    LESSONS_FILE = config.data_dir / "evolve" / "lessons.json"


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _load() -> list[dict]:
    if not LESSONS_FILE.exists():
        return []
    try:
        data = json.loads(LESSONS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _save(items: list[dict]) -> None:
    LESSONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = LESSONS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LESSONS_FILE)


def _normalize_confidence(confidence: float) -> float:
    try:
        c = float(confidence)
    except (TypeError, ValueError):
        c = 0.5
    return max(0.0, min(1.0, round(c, 2)))


def add_lesson(trigger: str, advice: str, task_ref: str = "",
               confidence: float = 0.5) -> dict:
    """新增一条经验；trigger + advice 完全相同的重复条目会被跳过（返回 duplicate）。

    返回：{"lesson": {...}, "duplicate": bool}
    """
    trigger = (trigger or "").strip()
    advice = (advice or "").strip()
    if not trigger or not advice:
        return {"lesson": None, "duplicate": False, "error": "trigger 与 advice 不能为空"}

    items = _load()
    for it in items:
        if it.get("trigger") == trigger and it.get("advice") == advice:
            return {"lesson": it, "duplicate": True}

    lesson = {
        "id": uuid.uuid4().hex[:8],
        "trigger": trigger[:200],
        "advice": advice[:500],
        "task_ref": (task_ref or "")[:300],
        "confidence": _normalize_confidence(confidence),
        "applied": 0,
        "created_at": now_str(),
    }
    items.append(lesson)
    if len(items) > MAX_LESSONS:
        items = items[-MAX_LESSONS:]
    _save(items)
    return {"lesson": lesson, "duplicate": False}


def list_lessons(limit: int = 200) -> list[dict]:
    """经验库列表（新 → 旧），limit 超界时用默认。"""
    if limit < 1 or limit > 1000:
        limit = 200
    items = _load()
    return list(reversed(items[-limit:]))


def get_lesson(lesson_id: str) -> dict | None:
    for it in _load():
        if it.get("id") == lesson_id:
            return it
    return None


def remove_lesson(lesson_id: str) -> bool:
    """删除指定经验；找到并删除返回 True。"""
    items = _load()
    kept = [it for it in items if it.get("id") != lesson_id]
    if len(kept) == len(items):
        return False
    _save(kept)
    return True


def mark_applied(lesson_id: str) -> dict | None:
    """经验被实际应用后计数 +1，返回更新后的条目。"""
    items = _load()
    for it in items:
        if it.get("id") == lesson_id:
            it["applied"] = int(it.get("applied", 0)) + 1
            _save(items)
            return it
    return None


def stats() -> dict:
    """经验库统计：总数 / 已应用总次数 / 平均置信度 / 未应用条数。"""
    items = _load()
    if not items:
        return {"total": 0, "applied_total": 0, "avg_confidence": 0.0, "unapplied": 0}
    applied_total = sum(int(it.get("applied", 0)) for it in items)
    avg = sum(float(it.get("confidence", 0.5)) for it in items) / len(items)
    return {
        "total": len(items),
        "applied_total": applied_total,
        "avg_confidence": round(avg, 2),
        "unapplied": sum(1 for it in items if not int(it.get("applied", 0))),
    }
