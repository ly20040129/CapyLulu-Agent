"""系统状态 / 桌宠 / 调度器。

- GET  /status：系统状态（LLM / 调度器 / 配色）；
- POST /mascot/start：启动桌宠；
- POST /scheduler/start：启动调度器；
- POST /scheduler/stop：停止调度器。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter

from capylulu import scheduler
from capylulu.config import config
from capylulu.ui.common import _llm_ready, _model_status_text

router = APIRouter(tags=["misc"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PET_PY = PROJECT_ROOT / "capylulu" / "pet.py"  # 桌宠入口脚本


@router.get("/status")
def status() -> dict:
    """返回 LLM 就绪状态、调度器运行状态与当前配色。"""
    return {
        "llm_ready": _llm_ready(),
        "model_status": _model_status_text(),
        "scheduler_running": scheduler.is_running(),
        "scheduler_status": scheduler.status_text(),
        "palette": config.palette,
    }


@router.post("/mascot/start")
def mascot_start() -> dict:
    """以独立进程启动桌宠。"""
    try:
        subprocess.Popen(
            [sys.executable, str(PET_PY)],
            cwd=str(PROJECT_ROOT),
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"桌宠启动失败：{exc}"}
    return {"ok": True, "message": "🦫 桌宠已打开（拖动移动，双击或 Esc 关闭）"}


@router.post("/scheduler/start")
def scheduler_start() -> dict:
    """启动自动任务调度器。"""
    return {"message": scheduler.start()}


@router.post("/scheduler/stop")
def scheduler_stop() -> dict:
    """停止自动任务调度器。"""
    return {"message": scheduler.stop()}
