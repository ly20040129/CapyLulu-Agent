"""管家团队：Agent 增删改、启停、路由重载；批次6 起含任务台账与手动委派测试。

- GET /team/agents：成员列表（含 capabilities / description / icon）；
- POST /team/agents · PUT /team/agents/{name} · PATCH .../enabled · DELETE ...：
  Agent CRUD（新增字段 capabilities / description / icon）；
- GET /team/tasks：任务台账列表 + 状态统计；
- POST /team/tasks：手动委派测试（走真实委派链路：能力路由 + 自动升级 + 台账）；
- POST /team/tasks/clear：清空任务台账。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capylulu import agents_store, team
from capylulu.agent.router import reload_routing
from capylulu.ui.common import agent

router = APIRouter(tags=["team"])


@router.get("/team/agents")
def list_agents() -> dict:
    return {"items": agents_store.list_agents()}


class AddAgentBody(BaseModel):
    name: str = ""
    role: str = ""
    prompt: str = ""
    keywords: str = ""
    tools: str = ""
    capabilities: str = ""
    description: str = ""
    icon: str = ""


@router.post("/team/agents")
def add_agent(body: AddAgentBody) -> dict:
    name = (body.name or "").strip()
    role = (body.role or "").strip()
    if not name or not role:
        raise HTTPException(status_code=400, detail="名称与职责不能为空")
    try:
        msg = agents_store.add_agent(
            name, role, (body.prompt or "").strip(),
            (body.keywords or "").strip(), (body.tools or "").strip(),
            (body.capabilities or "").strip(), (body.description or "").strip(),
            (body.icon or "").strip(),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    reload_routing()
    agent.reconfigure()
    return {"ok": True, "message": msg}


class UpdateAgentBody(BaseModel):
    role: str | None = None
    prompt: str | None = None
    keywords: str | None = None
    tools: str | None = None
    capabilities: str | None = None
    description: str | None = None
    icon: str | None = None


@router.put("/team/agents/{name}")
def update_agent(name: str, body: UpdateAgentBody) -> dict:
    try:
        msg = agents_store.update_agent(
            name,
            role=body.role,
            prompt=body.prompt,
            keywords=body.keywords,
            tools=body.tools,
            capabilities=body.capabilities,
            description=body.description,
            icon=body.icon,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    reload_routing()
    agent.reconfigure()
    return {"ok": True, "message": msg}


class ToggleBody(BaseModel):
    enabled: bool


@router.patch("/team/agents/{name}/enabled")
def toggle_agent(name: str, body: ToggleBody) -> dict:
    try:
        msg = agents_store.set_enabled(name, body.enabled)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    reload_routing()
    agent.reconfigure()
    return {"ok": True, "message": msg}


@router.delete("/team/agents/{name}")
def remove_agent(name: str) -> dict:
    try:
        msg = agents_store.remove_agent(name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    reload_routing()
    agent.reconfigure()
    return {"ok": True, "message": msg}


@router.post("/team/reconfigure")
def reconfigure() -> dict:
    reload_routing()
    agent.reconfigure()
    return {"ok": True, "message": "路由与 Agent 已重载"}


# ---------------- 批次6：任务台账 ----------------

@router.get("/team/tasks")
def list_tasks(limit: int = 200) -> dict:
    """任务台账列表（新 → 旧）+ 状态统计。"""
    if limit < 1 or limit > 500:
        limit = 200
    return {"items": team.recent(limit), "stats": team.stats()}


class DispatchTestBody(BaseModel):
    agent: str = ""   # 留空 = 自动能力匹配
    task: str = ""


@router.post("/team/tasks")
def dispatch_test(body: DispatchTestBody) -> dict:
    """手动委派测试：走真实委派链路（能力路由 → 执行 → 失败自动升级 → 台账）。

    返回最终执行者与状态（assigned / running / done / failed / escalated）。
    """
    task = (body.task or "").strip()
    if not task:
        raise HTTPException(status_code=400, detail="任务描述不能为空")
    who = (body.agent or "").strip()
    try:
        result, final_who, status = agent.leader.dispatch_with_escalation(who, task, agent.workers)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"委派执行异常：{exc}") from exc
    return {
        "ok": status in ("done", "escalated"),
        "status": status,
        "agent": final_who,
        "result": (result or "")[:500],
        "message": {
            "done": "委派成功",
            "escalated": "专员失败，已由 Leader 升级兜底完成",
            "failed": "委派失败",
            "running": "委派执行中",
            "assigned": "已派发",
        }.get(status, status),
    }


@router.post("/team/tasks/clear")
def clear_tasks() -> dict:
    n = team.clear()
    return {"ok": True, "message": f"已清理 {n} 条任务台账"}

