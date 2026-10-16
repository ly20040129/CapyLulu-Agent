"""模型 / 配色 / 数据目录设置。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capylulu.config import config
from capylulu.ui.common import agent, _llm_ready, _model_status_text
from capylulu.ui.palette import PALETTES, PALETTE_NAMES

router = APIRouter(tags=["settings"])

PROVIDERS = ["zhipu", "deepseek"]


@router.get("/settings")
def get_settings() -> dict:
    return {
        "provider": config.llm_provider,
        "palette": config.palette,
        "palettes": PALETTE_NAMES,
        "providers": PROVIDERS,
        "llm_ready": _llm_ready(),
        "model_status": _model_status_text(),
        "data_dir": str(config.data_dir),
    }


class LlmBody(BaseModel):
    provider: str = "zhipu"
    api_key: str = ""
    model: str = ""
    base_url: str = ""


@router.post("/settings/llm")
def save_llm(body: LlmBody) -> dict:
    try:
        msg = config.update_llm(body.provider, body.api_key.strip(), body.model.strip(), body.base_url.strip())
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    agent.reconfigure()
    return {"ok": True, "message": msg, "model_status": _model_status_text()}


class PaletteBody(BaseModel):
    name: str


@router.post("/settings/palette")
def save_palette(body: PaletteBody) -> dict:
    if body.name not in PALETTES:
        raise HTTPException(status_code=400, detail="未知配色")
    config.set_palette(body.name)
    return {"ok": True, "palette": body.name}
