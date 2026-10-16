"""SKILL.md 对话式创建工具：skill_create / skill_detail / skill_list_files。

- skill_create：用 LLM 生成 SKILL.md（无 Key 或失败时降级为本地模板），写入
  <data_dir>/skills/<name>.md 并同步注册到 skills.json（skills_store.add_skill）。
- skill_detail：读取某个 SKILL.md 的全文；
- skill_list_files：列出技能目录下全部 SKILL.md 清单。
"""
from __future__ import annotations

from .. import skills_store
from ..config import config
from ..llm import create_llm
from ..skills.runtime import (
    SKILLS_DIR,
    build_skill_md,
    get_skill,
    list_skills,
    parse_skill_md,
    save_skill_md,
)
from .registry import tool

_GEN_PROMPT = (
    "你是技能文档生成器。根据用户给出的技能名称、描述与步骤提示，生成一份符合以下约定的 "
    "SKILL.md 文件内容（Markdown，UTF-8，直接输出文件全文，不要额外解释）：\n"
    "1. 开头为 --- 包裹的 YAML front-matter，字段：name（技能名）、description（一句话说明）、"
    "tools（可调用工具名列表，YAML 列表格式）、trigger（逗号分隔触发词）、runtime: custom；\n"
    "2. 正文以中文撰写：## 目标（说明技能做什么）→ ## 执行步骤（可执行的分步指令，尽量具体）"
    "→ ## 注意（边界与禁忌）；\n"
    "3. 步骤要能被 LLM 直接执行，涉及工具调用时写明工具名与关键参数。"
)


def _llm_ready() -> bool:
    """是否已配置 API Key（避免冒烟时消耗真实 API）。"""
    return bool(config.llm_config.get("api_key"))


def _generate_md_with_llm(name: str, description: str, step_hint: str) -> str:
    """用 LLM 生成 SKILL.md 全文；失败抛异常由调用方降级。"""
    llm = create_llm()
    user = (
        f"技能名称：{name}\n技能描述：{description}\n"
        f"步骤提示：{step_hint or '（无，请按技能目标自行设计合理步骤）'}\n"
        "请输出 SKILL.md 全文。"
    )
    resp = llm.chat(
        [
            {"role": "system", "content": _GEN_PROMPT},
            {"role": "user", "content": user},
        ],
        tools=None,
    )
    content = (resp.get("content") or "").strip()
    if not content:
        raise RuntimeError("LLM 未返回内容")
    # 容忍 markdown 代码块包裹
    if content.startswith("```"):
        lines = content.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content


def _fallback_md(name: str, description: str, step_hint: str) -> str:
    """本地模板降级：无 API Key 或 LLM 失败时生成可用的 SKILL.md。"""
    steps = step_hint or ""
    if steps and not steps.startswith("##"):
        steps = "## 执行步骤\n" + steps
    elif not steps:
        steps = (
            "## 执行步骤\n"
            "1. 理解用户任务与技能目标；\n"
            "2. 按需调用 tools 字段列出的工具完成操作；\n"
            "3. 整理执行结果并汇报给用户。"
        )
    return build_skill_md(name, description, tools=[], steps=steps, runtime="custom")


def _register_to_store(name: str, description: str, tools: list[str]) -> str:
    """同步注册到 skills.json；返回错误信息（空串表示成功）。"""
    err = skills_store.add_skill(name, "skill", description, source="manual")
    if err:
        return err
    # 成功后再把首个工具名补充进元数据，便于技能广场展示「已接入」标识
    if tools:
        items = skills_store._load()
        for x in items:
            if x.get("name") == name:
                x["tool"] = tools[0]
                break
        skills_store._save(items)
    return ""


@tool(
    name="skill_create",
    description=(
        "技能-对话式创建：根据名称/描述/步骤提示生成一份 SKILL.md 技能文件，写入 "
        "data/skills/<name>.md 并同步注册到技能库 skills.json。已存在同名技能时返回错误，"
        "不覆盖。适合用户说「建一个 XX 技能」的场景。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名称（必填，唯一）"},
            "description": {"type": "string", "description": "技能一句话说明（必填）"},
            "step_hint": {"type": "string", "description": "可选：执行步骤提示，供 LLM 生成更贴合需求的步骤"},
        },
        "required": ["name", "description"],
    },
    risk="low",
)
def skill_create(name: str, description: str = "", step_hint: str = "") -> str:
    """对话式创建技能：LLM 生成 SKILL.md → 落盘 → 注册 skills.json。"""
    name = (name or "").strip()
    description = (description or "").strip()
    if not name:
        return "技能名称不能为空"
    if not description:
        return "技能描述不能为空"

    # 重复名称检查：skills.json 或 SKILL.md 文件任一存在即拒绝
    if any(x.get("name") == name for x in skills_store.load_skills()):
        return f"已存在同名技能：{name}"
    if get_skill(name) is not None:
        return f"已存在同名 SKILL.md：{name}"

    # 生成 SKILL.md：优先 LLM（需已配置 Key），失败自动降级本地模板，避免空转
    md = ""
    if _llm_ready():
        try:
            md = _generate_md_with_llm(name, description, step_hint)
        except Exception:  # noqa: BLE001
            md = ""
    if not md:
        md = _fallback_md(name, description, step_hint)

    try:
        parsed = parse_skill_md(save_skill_md(name, md))
    except ValueError as exc:
        return f"生成的 SKILL.md 格式非法，已中止：{exc}"
    tools = parsed.tools

    err = _register_to_store(name, parsed.description or description, tools)
    if err:
        # 注册失败时回滚已写文件，保持一致性
        try:
            (SKILLS_DIR / f"{name}.md").unlink()
        except OSError:
            pass
        return err
    return (
        f"技能「{name}」创建成功：{parsed.path}\n"
        f"描述：{parsed.description}\n"
        f"可用工具：{', '.join(tools) if tools else '（无，可后续在 SKILL.md 补充）'}"
    )


@tool(
    name="skill_detail",
    description="技能-查看详情：读取指定 SKILL.md 技能文件的完整内容（front-matter + 正文指令）。",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名称（如：文件整理）"},
        },
        "required": ["name"],
    },
    risk="low",
)
def skill_detail(name: str) -> str:
    """读取某个 SKILL.md 的全文。"""
    skill = get_skill(name or "")
    if skill is None:
        return f"未找到技能 SKILL.md：{name}"
    return f"路径：{skill.path}\n\n{skill.body}"


@tool(
    name="skill_list_files",
    description="技能-列出技能文件：列出技能目录（data/skills/）下全部 SKILL.md 文件清单（名称/描述/工具/路径）。",
    parameters={"type": "object", "properties": {}, "required": []},
    risk="low",
)
def skill_list_files() -> str:
    """列出技能目录下全部 SKILL.md 清单。"""
    items = list_skills()
    if not items:
        return f"技能目录（{SKILLS_DIR}）下还没有 SKILL.md 文件"
    rows = [f"- {x['name']}｜{x['description']}｜工具: {', '.join(x['tools']) or '无'}｜{x['path']}" for x in items]
    return f"共 {len(items)} 个 SKILL.md：\n" + "\n".join(rows)
