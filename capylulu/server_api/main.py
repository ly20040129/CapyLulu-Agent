"""capylulu Vue 前端配套 API 入口。

技术栈：FastAPI + Vue 3 + Vite。
保留原有业务模块（agent / history / agents_store / skills_store / scheduler / memory / tool_log / config / pet），
仅将 Gradio UI 层替换为 REST API + 静态托管。
启动方式（开发）：
    python -m uvicorn capylulu.server_api.main:app --host 0.0.0.0 --port 6661
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from capylulu import scheduler
from .routers import auth, chat, evolve, im, kb, mcp, memory, misc, settings, skills, tasks, team, tools

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

app = FastAPI(title="capylulu API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, misc.router, chat.router, team.router, skills.router,
          tasks.router, memory.router, tools.router, settings.router,
          mcp.router, kb.router, evolve.router, im.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "name": "capylulu-vue", "api": "2.0.0"}


@app.on_event("startup")
def _start_scheduler_on_boot() -> None:
    """后端启动时自动拉起自动任务调度器，避免重启后任务静默失效。"""
    try:
        scheduler.start()
    except Exception as exc:  # noqa: BLE001
        scheduler.logger.error(f"[Scheduler] 启动时自动拉起失败：{exc}")

    # 点火1：启动时刷新已启用 MCP 的动态工具注册（mcp_<server>_<tool>）
    try:
        from capylulu.mcp import dynamic_registry
        dynamic_registry.refresh_enabled_mcp_tools()
    except Exception as exc:  # noqa: BLE001
        scheduler.logger.error(f"[Startup] MCP 动态工具刷新失败：{exc}")

    # 点火3：后台自动进化（daemon 线程周期检查，满足间隔/新增任务数条件时触发）
    try:
        import threading
        import time
        from capylulu.evolve import maybe as evolve_maybe

        def _evolve_loop() -> None:
            while True:
                try:
                    evolve_maybe.maybe_evolve()
                except Exception as exc:  # noqa: BLE001
                    scheduler.logger.error(f"[Evolve] 后台进化检查异常：{exc}")
                time.sleep(600)  # 每 10 分钟检查一次

        threading.Thread(target=_evolve_loop, daemon=True, name="capylulu-evolve").start()
    except Exception as exc:  # noqa: BLE001
        scheduler.logger.error(f"[Startup] 后台进化线程启动失败：{exc}")

    # 点火3-深度蒸馏：Deep Dream 后台定时蒸馏（情景记忆 → 语义记忆）
    try:
        import threading
        import time
        from capylulu.memory3 import dream as dream_module

        def _dream_loop() -> None:
            while True:
                try:
                    dream_module.maybe_auto_dream(interval_seconds=3600)
                except Exception as exc:  # noqa: BLE001
                    scheduler.logger.error(f"[Dream] 后台语义蒸馏异常：{exc}")
                time.sleep(900)  # 每 15 分钟检查一次

        threading.Thread(target=_dream_loop, daemon=True, name="capylulu-dream").start()
    except Exception as exc:  # noqa: BLE001
        scheduler.logger.error(f"[Startup] 后台语义蒸馏线程启动失败：{exc}")

    # 点火4-用户记忆自进化：Self-Evolution 会话空闲检查（idle+轮次阈值 → review 写记忆）
    try:
        import threading
        import time
        from capylulu import self_evolve as self_evolve_module

        def _self_evolve_loop() -> None:
            while True:
                try:
                    self_evolve_module.maybe_review()
                except Exception as exc:  # noqa: BLE001
                    scheduler.logger.error(f"[SelfEvolve] 后台记忆自进化异常：{exc}")
                time.sleep(self_evolve_module.CHECK_INTERVAL)  # 每 60 秒检查一次

        threading.Thread(target=_self_evolve_loop, daemon=True, name="capylulu-self-evolve").start()
    except Exception as exc:  # noqa: BLE001
        scheduler.logger.error(f"[Startup] 后台自进化线程启动失败：{exc}")


# 噜噜形象资源：统一放在 web/public/images/（images/lulu、images/capy 两个子目录），前端通过 /images/*.png 访问
images_dir = PROJECT_ROOT / "web" / "public" / "images"
if images_dir.is_dir():
    app.mount("/images", StaticFiles(directory=str(images_dir), check_dir=False), name="images")


# 文件发送目录：静态托管 data/send_files，供 send_file 工具生成的 /files/ 下载链接访问。
# 须在 SPA fallback 之前注册，避免被吞；目录不存在时自动创建（check_dir=False 兜底容错）。
send_dir = PROJECT_ROOT / "data" / "send_files"
send_dir.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(send_dir), check_dir=False), name="files")


# 通用下载路由：把聊天回复中的磁盘绝对路径（如 E:\capylulu\data\downloads\xxx.txt）
# 映射为可点击下载链接。安全约束：仅允许 data/ 与 workspace/ 目录内的文件，防止任意文件泄露。
_DOWNLOAD_ROOTS = ((PROJECT_ROOT / "data").resolve(), (PROJECT_ROOT / "workspace").resolve())


def _strip_tail_punct(path: str) -> str:
    """去掉路径尾部常见标点与空白（聊天回复常带句号/逗号等，避免 404）。"""
    return (path or "").strip().rstrip("。，；！？,.!?;: \t\r\n")


@app.get("/api/files/download")
def download_file(path: str = Query(...)) -> FileResponse:
    target = Path(_strip_tail_punct(path)).expanduser().resolve()
    if not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    for root in _DOWNLOAD_ROOTS:
        try:
            target.relative_to(root)
        except ValueError:
            continue
        return FileResponse(target, filename=target.name)
    raise HTTPException(status_code=403, detail="仅允许访问 data 或 workspace 目录下的文件")


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
