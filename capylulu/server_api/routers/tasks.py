"""自动任务：任务管理 + 执行日志。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capylulu import tasks

router = APIRouter(tags=["tasks"])


@router.get("/tasks")
def list_tasks() -> dict:
    return {"items": tasks.load(), "rows": tasks.rows()}


class AddTaskBody(BaseModel):
    text: str = ""


@router.post("/tasks")
def add_task(body: AddTaskBody) -> dict:
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="任务描述不能为空")
    try:
        msg = tasks.add(text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": msg}


class ToggleTaskBody(BaseModel):
    enabled: bool


@router.patch("/tasks/{text}/enabled")
def toggle_task(text: str, body: ToggleTaskBody) -> dict:
    try:
        msg = tasks.set_enabled(text, body.enabled)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "message": msg}


@router.delete("/tasks/{text}")
def remove_task(text: str) -> dict:
    try:
        msg = tasks.remove_by_text(text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "message": msg}


@router.get("/tasks/logs")
def task_logs() -> dict:
    return {"items": tasks.load_logs()}
