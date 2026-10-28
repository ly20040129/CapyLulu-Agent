"""自主进化（批次7）：经验库 / 反思 / 改进 / 进化日志 REST 端点。

- GET  /api/evolve/lessons：经验库列表 + 统计；
- POST /api/evolve/lessons：新增经验；
- DELETE /api/evolve/lessons/{lesson_id}：删除经验；
- POST /api/evolve/reflect：触发反思（force 默认 true 直接执行；false 走 maybe 判定）；
- POST /api/evolve/improve：触发改进（force 默认 true 直接执行；false 走 maybe 判定）；
- GET  /api/evolve/log：进化日志列表 + 统计；
- GET  /api/evolve/status：上次触发状态（时间 / 台账 / 经验库 / 日志计数）。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capylulu.evolve import improve, lessons, maybe, reflect

router = APIRouter(tags=["evolve"])


# ---------------- 经验库 ----------------

@router.get("/evolve/lessons")
def list_lessons(limit: int = 200) -> dict:
    """经验库列表 + 统计。"""
    return {"items": lessons.list_lessons(limit), "stats": lessons.stats()}


class AddLessonBody(BaseModel):
    trigger: str = ""
    advice: str = ""
    task_ref: str = ""
    confidence: float = 0.5


@router.post("/evolve/lessons")
def add_lesson(body: AddLessonBody) -> dict:
    """新增经验条目（同 trigger+advice 自动去重）。"""
    trigger = (body.trigger or "").strip()
    advice = (body.advice or "").strip()
    if not trigger or not advice:
        raise HTTPException(status_code=400, detail="trigger 与 advice 不能为空")
    r = lessons.add_lesson(trigger, advice, (body.task_ref or "").strip(), body.confidence)
    if r.get("duplicate"):
        return {"ok": True, "duplicate": True, "lesson": r["lesson"],
                "message": "已存在相同经验，跳过以避免重复条目"}
    if not r.get("lesson"):
        raise HTTPException(status_code=400, detail=r.get("error", "新增失败"))
    return {"ok": True, "duplicate": False, "lesson": r["lesson"], "message": "经验已入库"}


@router.delete("/evolve/lessons/{lesson_id}")
def remove_lesson(lesson_id: str) -> dict:
    """删除经验条目。"""
    ok = lessons.remove_lesson(lesson_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"未找到经验：{lesson_id}")
    return {"ok": True, "message": f"已删除经验 {lesson_id}"}


# ---------------- 反思 / 改进 / 日志 ----------------

class ReflectBody(BaseModel):
    force: bool = True
    limit: int = 20
    interval_seconds: int = 3600
    min_new_tasks: int = 3


@router.post("/evolve/reflect")
def run_reflect(body: ReflectBody) -> dict:
    """触发反思：force 直接执行，否则按间隔/最小新任务数判定。"""
    try:
        if body.force:
            return {"ok": True, "triggered": True, **reflect.reflect(limit=body.limit, force=True)}
        r = maybe.maybe_evolve(
            interval_seconds=body.interval_seconds,
            min_new_tasks=body.min_new_tasks,
            limit=body.limit,
            force=False,
        )
        return {"ok": r.get("triggered"), "triggered": r.get("triggered"),
                "reason": r.get("reason", ""),
                "reflect": r.get("reflect", {}), "improve": r.get("improve", {})}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"反思执行异常：{exc}") from exc


class ImproveBody(BaseModel):
    force: bool = True
    max_auto: int = 3
    interval_seconds: int = 3600
    min_new_tasks: int = 3


@router.post("/evolve/improve")
def run_improve(body: ImproveBody) -> dict:
    """触发改进：force 直接执行，否则按间隔/最小新任务数判定。"""
    try:
        if body.force:
            return {"ok": True, "triggered": True, **improve.improve(max_auto=body.max_auto, force=True)}
        r = maybe.maybe_evolve(
            interval_seconds=body.interval_seconds,
            min_new_tasks=body.min_new_tasks,
            max_auto=body.max_auto,
            force=False,
        )
        return {"ok": r.get("triggered"), "triggered": r.get("triggered"),
                "reason": r.get("reason", ""),
                "reflect": r.get("reflect", {}), "improve": r.get("improve", {})}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"改进执行异常：{exc}") from exc


@router.get("/evolve/log")
def list_log(limit: int = 100) -> dict:
    """进化日志列表 + 统计。"""
    return {"items": improve.list_log(limit), "stats": improve.log_stats()}


@router.get("/evolve/status")
def evolve_status() -> dict:
    """上次触发状态：时间 / 台账 / 经验库 / 日志计数。"""
    st = maybe.status()
    st["lesson_count"] = lessons.stats().get("total", 0)
    st["applied_total"] = lessons.stats().get("applied_total", 0)
    st["log_count"] = improve.log_stats().get("total", 0)
    return st
