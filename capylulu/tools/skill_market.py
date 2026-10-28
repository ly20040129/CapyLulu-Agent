"""SkillHub（Cow Skill Hub）技能市场接入：skill_market_search / skill_market_detail / skill_market_install。

对接 https://skills.cowagent.ai 的公开 API：
- GET  /api/skills?q=&category=&provider=&tag=&page=&limit=   技能列表/搜索
- GET  /api/skills/<name>                                     技能详情
- GET  /api/skills/<name>/files                               技能文件（SKILL.md + 附属脚本/文档）
- POST /api/skills/<name>/download                            下载直链（zip / SKILL.md URL）
- POST /api/skills/<name>/install                             安装日志上报（尽力而为）

安装策略（两级降级）：
1. 优先 GET /files 直接落盘（含 SKILL.md + scripts/references 等文本文件）；
2. files 缺失或没有 SKILL.md 时，POST /download 拿 download_url / source_url，
   下载 zip 解压（或 SKILL.md 文本直链）后落盘。

产物写入 <data_dir>/skills/<name>/ 子目录（SKILL.md + 附属文件），并同步注册到
skills.json（source=hub），随后 LLM 可通过 run_skill 调度执行。等同 CowAgent 的
`/skill install <name>` 能力。
"""
from __future__ import annotations

import io
import json
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from .. import skills_store
from ..skills.runtime import SKILLS_DIR, get_skill, save_skill_dir
from .registry import registered_names, tool

HUB_BASE = "https://skills.cowagent.ai"
_UA = {"User-Agent": "capylulu-skill-hub-client/1.0"}
_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,127}$")
_MAX_TOOLS_SCAN = 8  # 从正文自动补 tools 时的上限


def _api_json(path: str, method: str = "GET", body: dict | None = None) -> dict:
    """请求 SkillHub API 并解析 JSON；网络/HTTP 错误抛 RuntimeError。"""
    url = HUB_BASE + path
    data = None
    headers = dict(_UA)
    if method == "POST":
        data = json.dumps(body or {}).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"SkillHub 请求失败：{exc}") from exc


def _fetch_bytes(url: str, timeout: int = 30) -> bytes:
    """下载远端二进制内容。"""
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _fmt_platforms(platforms: list | None) -> str:
    if not platforms:
        return "通用"
    names = {"darwin": "macOS", "linux": "Linux", "windows": "Windows"}
    return ",".join(names.get(x, x) for x in platforms)


def _fmt_list(items: list | None, empty: str = "无") -> str:
    return ",".join(str(x) for x in items) if items else empty


def _files_from_download(source_url: str) -> list[dict]:
    """从 download 直链解析文件列表 [{path, content, size}]。

    - .zip → 解压读取全部文本可解码文件（二进制文件跳过，如 png/exe）；
    - 其它 URL → 当作单个 SKILL.md 文本拉取。
    统一把顶层目录前缀剥掉，保证 SKILL.md 在根。
    """
    if not source_url:
        return []
    raw = _fetch_bytes(source_url)
    if source_url.endswith(".zip") or raw[:2] == b"PK":
        out: list[dict] = []
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                names = zf.namelist()
                # 顶层目录前缀（如 tencent-docs/）剥掉
                prefix = ""
                if names:
                    top = names[0].split("/", 1)[0]
                    if top and all(n == top or n.startswith(top + "/") for n in names):
                        prefix = top + "/"
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    rel = info.filename[len(prefix):] if prefix and info.filename.startswith(prefix) else info.filename
                    if not rel:
                        continue
                    try:
                        content = zf.read(info).decode("utf-8")
                    except UnicodeDecodeError:
                        continue  # 二进制资源跳过
                    out.append({"path": rel, "content": content, "size": len(content)})
        except zipfile.BadZipFile:
            return []
        return out
    # 非 zip：当作 SKILL.md 文本
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
    return [{"path": "SKILL.md", "content": text, "size": len(text)}]


def _auto_tools(md_content: str) -> list[str]:
    """从 SKILL.md front-matter 的 tools 字段或正文中提取已注册工具名（过滤掉未注册的）。"""
    registered = set(registered_names())
    tools: list[str] = []
    fm_tools = _parse_md_text(md_content).tools
    for t in fm_tools:
        if t in registered and t not in tools:
            tools.append(t)
    if tools:
        return tools
    # 正文扫描：按出现顺序取前 N 个已注册工具
    hits: list[str] = []
    for t in registered:
        if t in md_content and t not in hits:
            hits.append(t)
    return hits[:_MAX_TOOLS_SCAN]


def _parse_md_text(text: str):
    """解析内存中的 SKILL.md front-matter 关键字段（name/description/tools/trigger）。"""
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    meta: dict = {}
    if m:
        try:
            import yaml
            meta = yaml.safe_load(m.group(1)) or {}
        except Exception:  # noqa: BLE001
            meta = {}
    if not isinstance(meta, dict):
        meta = {}
    name = str(meta.get("name") or "").strip()
    desc = str(meta.get("description") or "").strip()
    tools_raw = meta.get("tools") or []
    if isinstance(tools_raw, str):
        tools_raw = [x.strip() for x in tools_raw.split(",") if x.strip()]
    trigger = str(meta.get("trigger") or meta.get("triggers") or "").strip()
    return type("_Fm", (), {
        "name": name,
        "description": desc,
        "tools": [str(t).strip() for t in tools_raw if str(t).strip()],
        "trigger": trigger,
    })()


@tool(
    name="skill_market_search",
    description=(
        "技能市场-搜索：从 Cow SkillHub（skills.cowagent.ai 开源技能市场）搜索可安装的技能，"
        "返回技能名/显示名/说明/版本/作者/分类/平台/所需环境变量。"
        "用户想安装/寻找新技能时使用；得到 name 后可用 skill_market_install 安装。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "搜索关键词（如：搜索、文档、翻译），可留空列出推荐技能"},
            "limit": {"type": "integer", "description": "返回条数，默认 10，最大 20"},
        },
        "required": ["query"],
    },
    risk="low",
)
def skill_market_search(query: str = "", limit: int = 10) -> str:
    """搜索 SkillHub 技能市场。"""
    query = (query or "").strip()
    limit = max(1, min(int(limit or 10), 20))
    q = urllib.parse.quote(query)
    path = f"/api/skills?q={q}&limit={limit}" if query else f"/api/skills?limit={limit}"
    data = _api_json(path)
    skills = data.get("skills") or []
    if not skills:
        return f"SkillHub 未找到与「{query or '全部'}」匹配的技能"
    rows = []
    for s in skills:
        rows.append(
            f"- {s.get('name')}｜{s.get('display_name') or ''}｜{(s.get('description') or '')[:80]}"
            f"｜v{s.get('version') or '?'}｜{s.get('author') or ''}｜分类:{s.get('category') or 'all'}"
            f"｜平台:{_fmt_platforms(s.get('platforms'))}｜环境变量:{_fmt_list(s.get('requires_env'))}"
        )
    total = data.get("total") or len(skills)
    return f"SkillHub 共 {total} 个技能，当前显示 {len(skills)} 个（可用 skill_market_install <name> 安装）：\n" + "\n".join(rows)


@tool(
    name="skill_market_detail",
    description=(
        "技能市场-查看详情：查看 SkillHub 上指定技能的详情与文件清单（含 SKILL.md 全文预览）。"
        "安装前用此工具确认技能内容、所需环境变量与平台兼容性。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名（skill_market_search 返回的 name 字段）"},
        },
        "required": ["name"],
    },
    risk="low",
)
def skill_market_detail(name: str) -> str:
    """查看 SkillHub 技能详情与文件内容。"""
    name = (name or "").strip()
    if not name:
        return "技能名不能为空"
    data = _api_json(f"/api/skills/{name}")
    skill = data.get("skill") or {}
    if not skill:
        return f"SkillHub 未找到技能：{name}"
    files_data = _api_json(f"/api/skills/{name}/files")
    files = files_data.get("files") or []
    lines = [
        f"技能：{skill.get('name')}（{skill.get('display_name') or ''}）",
        f"说明：{skill.get('description') or ''}",
        f"版本：v{skill.get('version') or '?'}｜作者：{skill.get('author') or ''}｜分类：{skill.get('category') or 'all'}",
        f"平台：{_fmt_platforms(skill.get('platforms'))}｜环境变量：{_fmt_list(skill.get('requires_env'))}｜"
        f"需要二进制：{_fmt_list(skill.get('requires_bins'))}",
        f"来源：{skill.get('source_provider') or ''}｜主页：{skill.get('homepage') or ''}",
        "",
        f"文件清单（{len(files)} 个）：",
    ]
    lines += [f"- {f.get('path')}（{f.get('size') or 0}B）" for f in files]
    md = next((f.get("content") for f in files if str(f.get("path", "")).endswith("SKILL.md")), "")
    if md:
        lines += ["", "===== SKILL.md 内容预览 =====", md[:2000]]
    return "\n".join(lines)


@tool(
    name="skill_market_install",
    description=(
        "技能市场-安装：从 Cow SkillHub 安装指定技能到本地 skills 目录"
        "（data/skills/<name>/SKILL.md + 附属文件），并注册到技能库 skills.json，"
        "安装后 LLM 可自动调度该技能。等同 `/skill install <name>`。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "技能名（skill_market_search 返回的 name 字段，如 baidu-search）"},
        },
        "required": ["name"],
    },
    risk="medium",
)
def skill_market_install(name: str) -> str:
    """从 SkillHub 安装技能：files 直取 → 降级 download zip → 落盘 + 注册。"""
    name = (name or "").strip()
    if not name or not _SAFE_NAME.match(name):
        return f"非法技能名：{name}（仅允许字母/数字/下划线/连字符，且不能以符号开头）"
    if get_skill(name) is not None:
        return f"技能「{name}」已安装：{get_skill(name).path}（如需覆盖请先删除）"

    # 1) 详情（校验存在 + 元数据）
    data = _api_json(f"/api/skills/{name}")
    skill = data.get("skill") or {}
    if not skill:
        return f"SkillHub 未找到技能：{name}"

    # 2) 优先 files 接口直接落盘
    files_data = _api_json(f"/api/skills/{name}/files")
    files = files_data.get("files") or []
    has_skill_md = any(str(f.get("path", "")).endswith("SKILL.md") for f in files)
    if not has_skill_md:
        # 3) 降级：download 端点拿直链
        dl = _api_json(f"/api/skills/{name}/download", method="POST", body={})
        source_url = dl.get("download_url") or dl.get("source_url") or ""
        if not source_url:
            return f"技能「{name}」无可下载文件（{dl.get('message') or 'unsupported provider'}）"
        files = _files_from_download(source_url)
        if not any(str(f.get("path", "")).endswith("SKILL.md") for f in files):
            return f"技能「{name}」下载内容中未找到 SKILL.md，已中止（共 {len(files)} 个文件）"

    # 4) 落盘子目录
    file_map = {str(f.get("path")): str(f.get("content") or "") for f in files}
    written = save_skill_dir(name, file_map)
    if not written:
        return f"技能「{name}」文件写入失败（路径非法或为空），已中止"

    # 5) 解析适配 + 注册 skills.json
    md_content = next((str(f.get("content") or "") for f in files if str(f.get("path", "")).endswith("SKILL.md")), "")
    fm = _parse_md_text(md_content)
    tools = _auto_tools(md_content)
    desc = (fm.description or skill.get("description") or name).strip()
    err = skills_store.add_skill(name, "skill", desc, source="hub")
    if err:
        return f"文件已落盘但注册失败：{err}\n路径：{', '.join(written)}"
    _update_store_meta(name, tools, fm.trigger)

    # 6) 安装日志上报（尽力而为，失败不影响安装结果）
    try:
        _api_json(f"/api/skills/{name}/install", method="POST", body={"cow_version": ""})
    except RuntimeError:
        pass

    if root_md:
        tool_desc = ", ".join(tools) if tools else "（无显式限定，LLM 按正文自由调度）"
        desc_line = desc
        reg_line = f"注册技能：{registered_disp[0] if registered_disp else name}"
    else:
        tool_desc = "（技能包：各子技能按自身 SKILL.md 独立调度）"
        desc_line = str(skill.get("description") or name)
        reg_line = f"注册子技能（{len(registered_disp)} 个）：{', '.join(registered_disp) if registered_disp else '无'}"

    return (
        f"技能「{name}」安装成功（来源：SkillHub/{skill.get('source_provider') or 'hub'}）\n"
        f"说明：{desc_line}\n"
        f"落盘目录：{SKILLS_DIR / name}\n"
        f"文件：{len(files)} 个（SKILL.md + 附属文件）\n"
        f"{reg_line}\n"
        f"限定工具：{tool_desc}\n"
        f"环境变量：{_fmt_list(skill.get('requires_env'), empty='无')}\n"
        f"现在可以直接说「用 {name} 技能做...」来触发。"
    )


def _update_store_meta(name: str, tools: list[str], trigger: str) -> None:
    """往 skills.json 对应记录补齐 tool/trigger/runtime 元数据。"""
    try:
        items = skills_store._load()
        for x in items:
            if x.get("name") == name:
                if tools:
                    x["tool"] = tools[0]
                if trigger:
                    x["trigger"] = trigger
                x["runtime"] = "hub"
                break
        skills_store._save(items)
    except Exception:  # noqa: BLE001
        pass
