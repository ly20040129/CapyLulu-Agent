"""管家团队持久化存储：<data_dir>/agents.json。

支持查看 / 启停 / 增删改 Agent，字段：name, role, prompt, keywords, tools,
capabilities, description, icon, enabled, builtin。
builtin=True 的内置 Agent 不可删除（但可停用 / 改名? 改名会破坏
prompts 映射，因此内置 Agent 允许停用与编辑 prompt/role，不允许删除，也不允许改名）。

批次6 扩展：capabilities（能力标签列表，供 Leader 能力匹配路由）、
description（一句话职责，供前端卡片展示）、icon（前端展示用图片路径）。
存量 agents.json 缺失这些字段时自动补默认，保证兼容。
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .config import config

STORE = config.data_dir / "agents.json"


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global STORE
    STORE = config.data_dir / "agents.json"

# 默认关键词与工具（内置 Agent 的初始配置；prompt 延迟从 prompts.py 取，避免循环导入）
# 批次6 新增 capabilities（能力标签，Leader 能力匹配路由用）/ description（一句话职责）/ icon（前端图标）
_DEFAULTS = [
    {
        "name": "总代理",
        "role": "团队指挥官：闲聊问答、任务规划、带队拆解与结果汇总",
        "description": "团队指挥官：闲聊问答、任务规划、带队拆解与结果汇总",
        "capabilities": ["规划", "调度", "汇总", "问答", "拆解"],
        "icon": "/lulu/1.png",
        "keywords": [],
        "tools": [],
        "enabled": True,
        "builtin": True,
        "leader": True,
    },
    {
        "name": "文件管家",
        "role": "读写搜索整理文件、列目录、桌面文件",
        "description": "读写搜索整理文件、列目录、桌面文件",
        "capabilities": ["文件", "目录", "文件夹", "读取", "写入", "搜索", "整理", "文档", "桌面文件"],
        "icon": "/lulu/6.png",
        "keywords": [
            "文件", "目录", "文件夹", "readme", "config", "配置文件", "写入",
            "读一下", "读文件", "写文件", "读取", "搜索文件", "找文件", "移动",
            "重命名", "整理桌面", "桌面有什么", "打开这个文件", "看看这个",
            "脚本", "代码", "pdf", "docx", "txt",
        ],
        "tools": [
            "read_file", "write_file", "append_file", "list_dir",
            "search_files", "search_text", "move_file", "list_desktop",
            "send_file",
        ],
        "enabled": True,
        "builtin": True,
    },
    {
        "name": "电脑管家",
        "role": "系统信息、磁盘、时间、系统设置、桌面、打开本地路径",
        "description": "系统信息、磁盘、时间、系统设置、桌面、打开本地路径",
        "capabilities": ["系统", "电脑", "磁盘", "内存", "设置", "硬件", "时间", "配置"],
        "icon": "/lulu/7.png",
        "keywords": [
            "系统", "电脑", "配置", "磁盘", "内存", "设置", "硬件", "时间",
            "几点", "主机名", "桌面路径", "打开设置", "剩余空间", "容量",
            "打开路径", "打开文件夹", "打开目录",
        ],
        "tools": [
            "system_info", "now_datetime", "disk_usage", "open_settings",
            "list_desktop", "open_path",
        ],
        "enabled": True,
        "builtin": True,
    },
    {
        "name": "浏览器专员",
        "role": "打开网页、抓取网页摘要",
        "description": "打开网页、抓取网页摘要",
        "capabilities": ["网页", "浏览器", "网址", "上网", "网站", "摘要"],
        "icon": "/lulu/4.png",
        "keywords": [
            "网页", "浏览器", "http", "https", "网址", "打开qq", "邮箱网页",
            "上网", "网站", "网页摘要",
        ],
        "tools": ["open_url", "fetch_page"],
        "enabled": True,
        "builtin": True,
    },
    {
        "name": "软件管家",
        "role": "启动本机常见应用（记事本/计算器/画图/资源管理器）",
        "description": "启动本机常见应用（记事本/计算器/画图/资源管理器）",
        "capabilities": ["应用", "启动", "软件", "记事本", "计算器", "画图"],
        "icon": "/lulu/3.png",
        "keywords": [
            "记事本", "计算器", "画图", "启动", "打开软件", "打开应用", "运行",
            "软件管家",
        ],
        "tools": ["launch_app", "open_path", "open_url"],
        "enabled": True,
        "builtin": True,
    },
]

# 内置 prompt 映射（延迟导入避免与 prompts.py 循环依赖）
_PROMPT_KEYS = {
    "总代理": "LEADER_PROMPT",
    "文件管家": "FILE_AGENT_PROMPT",
    "电脑管家": "COMPUTER_AGENT_PROMPT",
    "浏览器专员": "BROWSER_AGENT_PROMPT",
    "软件管家": "APP_AGENT_PROMPT",
}


def _default_prompt(name: str) -> str:
    try:
        from .prompts import (  # noqa: PLC0415 延迟导入
            LEADER_PROMPT, FILE_AGENT_PROMPT, COMPUTER_AGENT_PROMPT,
            BROWSER_AGENT_PROMPT, APP_AGENT_PROMPT,
        )
        _map = {
            "总代理": LEADER_PROMPT,
            "文件管家": FILE_AGENT_PROMPT,
            "电脑管家": COMPUTER_AGENT_PROMPT,
            "浏览器专员": BROWSER_AGENT_PROMPT,
            "软件管家": APP_AGENT_PROMPT,
        }
        return _map.get(name, "")
    except Exception:
        return ""


def _defaults() -> list[dict]:
    """构造默认清单：补上 prompt 字段。"""
    out = []
    for d in _DEFAULTS:
        item = dict(d)
        item["prompt"] = _default_prompt(item["name"])
        out.append(item)
    return out


def _leader_default() -> dict:
    """总代理默认条目（迁移存量 agents.json 时补位）。"""
    item = dict(next(d for d in _DEFAULTS if d["name"] == "总代理"))
    item["prompt"] = _default_prompt("总代理")
    return item


def _ensure_leader(agents: list[dict]) -> list[dict]:
    """确保团队清单包含总代理：存量 agents.json 迁移时自动补在最前面。"""
    if any(a.get("name") == "总代理" for a in agents):
        return agents
    return [_leader_default()] + agents


# 内置 Agent 的批次6 扩展字段默认值（供存量数据补位）
_DEFAULT_CAPS = {d["name"]: d.get("capabilities") or [] for d in _DEFAULTS}
_DEFAULT_DESC = {d["name"]: d.get("description") or "" for d in _DEFAULTS}
_DEFAULT_ICON = {d["name"]: d.get("icon") or "" for d in _DEFAULTS}


def _ensure_fields(agents: list[dict]) -> list[dict]:
    """兼容存量 agents.json：缺失 capabilities / description / icon 时自动补默认。

    内置 Agent 补内置默认值；自定义 Agent 的 capabilities 兜底为 []，
    description 兜底为 role，icon 兜底为通用图标。
    """
    for a in agents:
        name = a.get("name") or ""
        if "capabilities" not in a:
            a["capabilities"] = list(_DEFAULT_CAPS.get(name, []))
        if not isinstance(a.get("capabilities"), list):
            a["capabilities"] = [str(c).strip() for c in (a.get("capabilities") or "").split(",") if str(c).strip()]
        if "description" not in a:
            a["description"] = _DEFAULT_DESC.get(name) or (a.get("role") or "")
        if "icon" not in a:
            a["icon"] = _DEFAULT_ICON.get(name) or "/lulu/1.png"
        # 内置 Agent 的 prompt 为空（存量 agents.json 常缺）时回退到 prompts.py 默认，
        # 避免文件管家等专员拿空 system prompt 导致 LLM 不调用工具、编造"无权限"话术。
        if name in _PROMPT_KEYS and not (a.get("prompt") or "").strip():
            a["prompt"] = _default_prompt(name)
    return agents


def _load() -> list[dict]:
    if not STORE.exists():
        return _ensure_fields(_ensure_leader(_defaults()))
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return _ensure_fields(_ensure_leader(data))
    except (json.JSONDecodeError, TypeError):
        pass
    return _ensure_fields(_ensure_leader(_defaults()))


def _save(agents: list[dict]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(agents, ensure_ascii=False, indent=2), encoding="utf-8")


def list_agents() -> list[dict]:
    return _load()


def get_agent(name: str) -> dict | None:
    for a in _load():
        if a.get("name") == name:
            return a
    return None


def enabled_names() -> list[str]:
    """启用的工作 Agent 名（不含总代理），用于侧栏「当前管家」下拉。"""
    return [a["name"] for a in _load() if a.get("enabled", True) and a.get("name") != "总代理"]


def all_names() -> list[str]:
    return [a["name"] for a in _load()]


def _split_list(value: str) -> list[str]:
    """把逗号分隔字符串拆成标签列表（兼容中文逗号）。"""
    return [x.strip() for x in (value or "").replace("，", ",").split(",") if x.strip()]


def add_agent(name: str, role: str, prompt: str, keywords: str = "", tools: str = "",
              capabilities: str = "", description: str = "", icon: str = "") -> str:
    """新增 Agent。返回空串表示成功，否则返回错误提示。"""
    name = (name or "").strip()
    if not name:
        return "Agent 名称不能为空"
    agents = _load()
    if any(a.get("name") == name for a in agents):
        return f"已存在同名 Agent：{name}"
    kw = _split_list(keywords)
    tl = _split_list(tools)
    caps = _split_list(capabilities)
    agents.append({
        "name": name,
        "role": (role or "").strip(),
        "prompt": (prompt or "").strip(),
        "keywords": kw,
        "tools": tl,
        "capabilities": caps,
        "description": (description or "").strip() or (role or "").strip(),
        "icon": (icon or "").strip() or "/lulu/1.png",
        "enabled": True,
        "builtin": False,
        "created": time.strftime("%Y-%m-%d %H:%M"),
    })
    _save(agents)
    return ""


def update_agent(name: str, *, role: str = None, prompt: str = None,
                 keywords: str = None, tools: str = None,
                 capabilities: str = None, description: str = None,
                 icon: str = None) -> str:
    """编辑已有 Agent 的字段。返回空串表示成功，否则错误提示。"""
    agents = _load()
    for a in agents:
        if a.get("name") == name:
            if role is not None:
                a["role"] = (role or "").strip()
            if prompt is not None:
                a["prompt"] = (prompt or "").strip()
            if keywords is not None:
                a["keywords"] = _split_list(keywords)
            if tools is not None:
                a["tools"] = _split_list(tools)
            if capabilities is not None:
                a["capabilities"] = _split_list(capabilities)
            if description is not None:
                a["description"] = (description or "").strip() or (a.get("role") or "").strip()
            if icon is not None:
                a["icon"] = (icon or "").strip() or "/lulu/1.png"
            _save(agents)
            return ""
    return f"未找到 Agent：{name}"


def set_enabled(name: str, enabled: bool) -> str:
    if name == "总代理":
        return "「总代理」是核心 Agent，不能停用"
    agents = _load()
    for a in agents:
        if a.get("name") == name:
            a["enabled"] = bool(enabled)
            _save(agents)
            return ""
    return f"未找到 Agent：{name}"


def remove_agent(name: str) -> str:
    """删除 Agent。内置 Agent 不可删除。"""
    if name == "总代理":
        return "「总代理」是核心 Agent，不能删除"
    agents = _load()
    for a in agents:
        if a.get("name") == name:
            if a.get("builtin"):
                return f"「{name}」是内置 Agent，不能删除，可停用或编辑"
            agents.remove(a)
            _save(agents)
            return ""
    return f"未找到 Agent：{name}"
