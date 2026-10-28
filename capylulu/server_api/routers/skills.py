"""技能广场：技能列表、添加、删除 + SKILL.md 技能运行时文件管理。

- GET /skills：技能列表；
- POST /skills：新增技能；
- DELETE /skills/{name}：删除技能；
- GET /skills/files：SKILL.md 清单；
- POST /skills/create：对话式创建 SKILL.md 技能。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capylulu import skills_store
from capylulu.skills.runtime import (
    build_skill_md,
    get_skill,
    list_skills,
    save_skill_md,
)

router = APIRouter(tags=["skills"])


@router.get("/skills")
def list_skill_store() -> dict:
    """技能列表。

    注意：不能命名为 list_skills —— 会遮蔽上方 from capylulu.skills.runtime import list_skills，
    导致 /skills/files 里调用到本函数（返回 {"items": [...]} dict），
    前端 (.items || []).map 报 not a function。
    """
    return {"items": skills_store.load_skills()}


class AddSkillBody(BaseModel):
    name: str = ""
    skill_type: str = "command"
    desc: str = ""
    source: str = "manual"


@router.post("/skills")
def add_skill(body: AddSkillBody) -> dict:
    """新增一条技能记录。"""
    name = (body.name or "").strip()
    desc = (body.desc or "").strip()
    if not name or not desc:
        raise HTTPException(status_code=400, detail="名称与描述不能为空")
    try:
        msg = skills_store.add_skill(name, body.skill_type.strip(), desc, body.source)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "message": msg}


@router.delete("/skills/{name}")
def remove_skill(name: str) -> dict:
    """删除技能记录。"""
    try:
        msg = skills_store.remove_skill(name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "message": msg}


# ---------------- SKILL.md 技能运行时 ----------------

@router.get("/skills/files")
def skill_md_files() -> dict:
    """列出技能目录下全部 SKILL.md（清单 + 详情：front-matter 与正文全文）。"""
    return {"items": list_skills()}


class CreateSkillBody(BaseModel):
    name: str = ""
    desc: str = ""
    tools: list[str] = []
    steps: str = ""


@router.post("/skills/create")
def create_skill_md(body: CreateSkillBody) -> dict:
    """对话式创建技能：直接落 SKILL.md 文件 + 同步注册到 skills.json。

    与工具 skill_create 不同，此端点不调用 LLM，body 中的 name/desc/steps 由前端表单提供，
    便于在不消耗 API 的情况下快速建技能。
    """
    name = (body.name or "").strip()
    desc = (body.desc or "").strip()
    if not name or not desc:
        raise HTTPException(status_code=400, detail="名称与描述不能为空")
    if any(x.get("name") == name for x in skills_store.load_skills()):
        raise HTTPException(status_code=400, detail=f"已存在同名技能：{name}")
    if get_skill(name) is not None:
        raise HTTPException(status_code=400, detail=f"已存在同名 SKILL.md：{name}")

    tools = [t.strip() for t in (body.tools or []) if str(t).strip()]
    steps = (body.steps or "").strip()
    md = build_skill_md(name, desc, tools, steps=steps, runtime="custom")
    try:
        path = save_skill_md(name, md)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"写入 SKILL.md 失败：{exc}") from exc

    err = skills_store.add_skill(name, "skill", desc, source="manual")
    if err:
        raise HTTPException(status_code=400, detail=err)
    if tools:
        items = skills_store._load()
        for x in items:
            if x.get("name") == name:
                x["tool"] = tools[0]
                break
        skills_store._save(items)
    return {"ok": True, "message": f"技能「{name}」创建成功", "path": str(path)}


# ---------------- SkillHub 技能市场 ----------------

@router.get("/skills/hub/search")
def hub_search(q: str = "", limit: int = 10) -> dict:
    """搜索 SkillHub 技能市场（skills.cowagent.ai）。"""
    from capylulu.tools.skill_market import skill_market_search
    return {"result": skill_market_search(query=q, limit=limit)}


@router.get("/skills/hub/detail")
def hub_detail(name: str = "") -> dict:
    """查看 SkillHub 技能详情与文件清单。"""
    from capylulu.tools.skill_market import skill_market_detail
    return {"result": skill_market_detail(name=name)}


class HubInstallBody(BaseModel):
    name: str = ""


@router.post("/skills/hub/install")
def hub_install(body: HubInstallBody) -> dict:
    """从 SkillHub 安装技能到本地（等同 /skill install <name>）。"""
    from capylulu.tools.skill_market import skill_market_install
    return {"result": skill_market_install(name=body.name or "")}
