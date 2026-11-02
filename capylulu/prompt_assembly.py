"""提示词动态组装：片段注册表 + 按 agent/工具集准入拼装。

SECTIONS 为「片段名 -> 文本」的注册表；模块 / 插件可 register_section 追加片段。
compose_prompt 拼装规则（保持现有人设文本一字不改）：
    base = SECTIONS["persona"] + SECTIONS[agent_key]
    tool_names 非空（非 None 且非空列表）时追加 SECTIONS["TOOL_GUIDE"] 与
    SECTIONS["OFFLINE_HINT"]（兼容原 prompt 结构）。
片段缺失时抛出明确 KeyError（不静默回退空串，便于及早发现漏注册）；
调用方可用 get_section 预检或捕获 KeyError 降级。
"""
from __future__ import annotations

SECTIONS: dict[str, str] = {}


def register_section(name: str, text: str) -> bool:
    """注册 prompt 片段；同名拒绝（返回 False）。"""
    if not name or not isinstance(text, str) or name in SECTIONS:
        return False
    SECTIONS[name] = text
    return True


def unregister_section(name: str) -> bool:
    """注销 prompt 片段；返回是否真的移除。"""
    return SECTIONS.pop(name, None) is not None


def get_section(name: str) -> str:
    """取片段文本；未注册时抛 KeyError（含片段名，便于定位）。"""
    if name not in SECTIONS:
        raise KeyError(f"prompt 片段未注册：{name}")
    return SECTIONS[name]


def compose_prompt(agent_key: str, tool_names: list[str] | None = None) -> str:
    """按 agent_key 与工具集拼装 system prompt。

    - base = SECTIONS["persona"] + SECTIONS[agent_key]；
    - tool_names 非空时追加 TOOL_GUIDE 与 OFFLINE_HINT；
    - 任一所需片段缺失均抛 KeyError（明确失败，不回退空串）。
    """
    base = get_section("persona") + get_section(agent_key)
    if tool_names:
        base += get_section("TOOL_GUIDE") + get_section("OFFLINE_HINT")
    return base
