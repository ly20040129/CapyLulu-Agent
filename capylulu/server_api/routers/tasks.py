"""自动任务：任务管理 + 执行日志。"""
from __future__ import annotations

import shutil
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel

from capylulu import task_engine
from capylulu import tasks

router = APIRouter(tags=["tasks"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"  # 任务附件上传目录

# 白名单函数按目标分组：web / win / other，供前端弹窗选择动作
WIN_MODULES = {"desktop", "window_ops", "process_ops", "input_ops", "gui_ops"}


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


class UpdateTaskBody(BaseModel):
    text: str = ""


@router.put("/tasks/{text}")
def update_task(text: str, body: UpdateTaskBody) -> dict:
    """按原文本更新提醒/便签任务（供前端编辑入口使用）。"""
    new_text = (body.text or "").strip()
    if not new_text:
        raise HTTPException(status_code=400, detail="任务描述不能为空")
    try:
        msg = tasks.update_by_text(text, new_text)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "message": msg}


@router.get("/tasks/logs")
def task_logs() -> dict:
    return {"items": tasks.load_logs()}


class AutoTaskBody(BaseModel):
    name: str = ""
    cron: str = ""
    module: str = ""
    func: str = ""
    params: dict = {}
    steps: list = []
    desc: str = ""


@router.post("/tasks/auto")
def add_auto_task(body: AutoTaskBody) -> dict:
    """新增/更新自动任务（按 name 去重）。支持单步(module/func/params)与多步(steps)两种形态。"""
    item = {
        "name": (body.name or "").strip(),
        "cron": (body.cron or "").strip(),
        "module": (body.module or "").strip(),
        "func": (body.func or "").strip(),
        "params": body.params or {},
        "steps": body.steps or [],
        "desc": (body.desc or "").strip(),
    }
    msg = task_engine.save_auto_task(item)
    if msg.startswith("错误："):
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.delete("/tasks/auto/{name}")
def remove_auto_task(name: str) -> dict:
    """按 name 删除自动任务。"""
    msg = task_engine.remove_auto_task(name)
    if msg.startswith("错误："):
        raise HTTPException(status_code=404, detail=msg)
    return {"ok": True, "message": msg}


@router.patch("/tasks/auto/{name}/enabled")
def toggle_auto_task(name: str, body: ToggleTaskBody) -> dict:
    """启停自动任务。"""
    msg = task_engine.set_auto_enabled(name, body.enabled)
    if msg.startswith("错误："):
        raise HTTPException(status_code=404, detail=msg)
    return {"ok": True, "message": msg}


class ParseBody(BaseModel):
    text: str = ""


@router.post("/tasks/parse")
def parse_task_text(body: ParseBody) -> dict:
    """自然语言拆解为自动任务建议（不落盘，供前端确认）。"""
    return task_engine.parse_nl(body.text or "")


# ---------------- 自动任务选项 / 附件上传 ----------------

@router.get("/tasks/auto/options")
def auto_options() -> dict:
    """白名单函数按模块分组（browser_ops→web；desktop/window/process/input/gui→win；其余→other）。"""
    groups: dict[str, list[dict]] = {"web": [], "win": [], "other": []}
    for full in sorted(task_engine.ALLOWED_FUNCS):
        module, _, func = full.rpartition(".")
        mod = module.rsplit(".", 1)[-1]
        if mod == "browser_ops":
            group = "web"
        elif mod in WIN_MODULES:
            group = "win"
        else:
            group = "other"
        groups[group].append({"module": module, "func": func, "full": full})
    return {"groups": groups, "total": len(task_engine.ALLOWED_FUNCS)}


@router.get("/tasks/auto/status")
def auto_status() -> dict:
    """当前正在运行的自动任务列表（前端轮询展示“运行中”标记）。"""
    return {"running": task_engine.running_status()}


@router.post("/tasks/upload")
async def upload_task_file(file: UploadFile) -> dict:
    """上传任务附件到 data/uploads/，保留原文件名，返回 {path, url}。"""
    name = (file.filename or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    safe = Path(name).name  # 防路径穿越：只取文件名部分
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    target = UPLOADS_DIR / safe
    if target.exists():  # 重名时追加时间戳后缀，避免覆盖
        stem, suffix = target.stem, target.suffix
        target = UPLOADS_DIR / f"{stem}_{int(time.time())}{suffix}"
    try:
        with target.open("wb") as f:
            shutil.copyfileobj(file.file, f)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"保存失败：{exc}") from exc
    finally:
        await file.close()
    url = f"/api/files/download?path={quote(str(target.resolve()))}"
    return {"ok": True, "path": str(target), "url": url}
