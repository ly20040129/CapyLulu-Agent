"""capylulu Vue 前端配套 API 入口。

技术栈：FastAPI + Vue 3 + Vite。
保留原有业务模块（agent / history / agents_store / skills_store / scheduler / memory / tool_log / config / pet），
仅将 Gradio UI 层替换为 REST API + 静态托管。
启动方式（开发）：
    python -m uvicorn capylulu.server_api.main:app --host 0.0.0.0 --port 6661
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routers import chat, evolve, im, kb, mcp, memory, misc, settings, skills, tasks, team, tools

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

app = FastAPI(title="capylulu API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (misc.router, chat.router, team.router, skills.router,
          tasks.router, memory.router, tools.router, settings.router,
          mcp.router, kb.router, evolve.router, im.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "name": "capylulu-vue", "api": "2.0.0"}


# 生产模式：托管 Vue 构建产物（须放在所有 API 路由之后，避免吞掉 /api/*）
dist = PROJECT_ROOT / "web" / "dist"
if dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        target = dist / full_path
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(dist / "index.html")
