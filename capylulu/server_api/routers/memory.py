"""用户记忆：列表、读取、创建、保存、删除；三级记忆与 Deep Dream 蒸馏（批次4）。

- GET /memories：用户记忆列表；
- GET/POST /memories/{name}：读取 / 保存指定记忆；
- POST /memories：创建记忆；
- DELETE /memories/{name}：删除记忆；
- GET /memories/tiers：三级记忆总览；
- POST /memories/tiers/working|episodic：写入工作 / 情景记忆；
- GET /memories/last-dream：上次蒸馏状态；
- GET /memories/query：三级记忆合并检索；
- POST /memories/deep-dream：手动触发蒸馏。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capylulu import memory
from capylulu.memory3 import dream, query as m3_query
from capylulu.memory3 import store as m3_store

router = APIRouter(tags=["memory"])


@router.get("/memories")
def list_memories() -> dict:
    """用户记忆条目列表。"""
    return {"items": memory.list_memories()}


# ---------------- 三级记忆 + 深度蒸馏（批次4） ----------------
# 注意：以下新端点必须定义在 /memories/{name} 之前，避免被路径参数吞掉。


@router.get("/memories/tiers")
def memory_tiers() -> dict:
    """三级记忆总览：working / episodic / semantic 各自条目列表。"""
    return {
        "working": m3_store.list_tier("working"),
        "episodic": m3_store.list_tier("episodic"),
        "semantic": m3_store.list_tier("semantic"),
    }


@router.get("/memories/last-dream")
def memory_last_dream() -> dict:
    """上次蒸馏状态（时间戳 / 各层级数量）。"""
    return dream.last_dream_status()


@router.get("/memories/query")
def memory_query(q: str = "", limit: int = 10) -> dict:
    """三级记忆合并检索（语义>情景>工作 + 时间衰减）。"""
    return {"items": m3_query.query(keyword=q, limit=limit)}


class WorkingBody(BaseModel):
    session: str = "default"
    content: str = ""


class EpisodicBody(BaseModel):
    task: str = ""
    action: str = ""
    result: str = ""
    agents: str = ""
    time: str = ""


class DreamBody(BaseModel):
    force: bool = False
    limit: int = 50


@router.post("/memories/tiers/working")
def memory_log_working(body: WorkingBody) -> dict:
    """写入/追加一条工作记忆（会话级上下文）。"""
    if not (body.content or "").strip():
        raise HTTPException(status_code=400, detail="工作记忆内容不能为空")
    return m3_store.log_working(session=body.session, content=body.content)


@router.post("/memories/tiers/episodic")
def memory_log_episodic(body: EpisodicBody) -> dict:
    """记录一条情景事件（时间/任务/动作/结果/参与Agent）。"""
    return m3_store.log_episodic(task=body.task, action=body.action,
                                 result=body.result, agents=body.agents,
                                 event_time=body.time)


@router.post("/memories/deep-dream")
def memory_deep_dream(body: DreamBody) -> dict:
    """手动触发 Deep Dream 蒸馏（LLM，不可用则规则降级）。"""
    return dream.deep_dream(limit=body.limit, force=body.force)


@router.get("/memories/{name}")
def read_memory(name: str) -> dict:
    """按名称读取用户记忆内容。"""
    try:
        content = memory.read_memory(name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"name": name, "content": content}


class MemoryBody(BaseModel):
    name: str = ""
    content: str = ""


@router.post("/memories")
def create_memory(body: MemoryBody) -> dict:
    """创建一条用户记忆。"""
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="名称不能为空")
    try:
        msg = memory.create_memory(name, body.content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": msg}


@router.put("/memories/{name}")
def save_memory(name: str, body: MemoryBody) -> dict:
    """保存指定用户记忆内容。"""
    try:
        msg = memory.save_memory(name, body.content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "message": msg}


@router.delete("/memories/{name}")
def delete_memory(name: str) -> dict:
    """删除指定用户记忆。"""
    try:
        msg = memory.delete_memory(name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "message": msg}
