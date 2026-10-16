"""MCP 接入工具：把「能力中心」接入的 MCP Server 变成 LLM 可调度的工具。

LLM 先调 mcp_tool_list 查看已接入服务与工具清单，再调 mcp_call_tool 执行具体工具。
"""
from __future__ import annotations

import json

from ..mcp import client as mcp_client
from ..mcp import store as mcp_store
from .registry import tool


def _server_tools_text() -> str:
    """当前已启用 MCP 服务的工具清单（供 LLM 决策）。"""
    servers = mcp_store.enabled_servers()
    if not servers:
        return "当前没有已接入并启用的 MCP 服务。可在「能力中心/MCP」页添加（stdio/sse/http）。"
    lines = []
    for s in servers:
        caches = s.get("tools_cache") or []
        if caches:
            tool_lines = ", ".join(f"{t.get('name')}({t.get('description', '')[:60]})" for t in caches)
        else:
            tool_lines = "（未获取工具清单，可先调用一次测试/刷新）"
        lines.append(f"[{s.get('name')}] type={s.get('type')} tools: {tool_lines}")
    return "\n".join(lines)


@tool(
    name="mcp_tool_list",
    description=(
        "MCP 接入清单：返回当前已启用 MCP 服务及其可用工具列表。"
        "调用任意 mcp_call_tool 前建议先查看本清单确认服务名与工具名。"
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
    risk="low",
)
def mcp_tool_list() -> str:
    return _server_tools_text()


@tool(
    name="mcp_call_tool",
    description=(
        "MCP 工具调用：执行已接入 MCP 服务提供的工具（服务名与工具名见 mcp_tool_list）。"
        "server 为服务名，tool 为服务内工具名，arguments 为 JSON 对象字符串。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "server": {"type": "string", "description": "已接入的 MCP 服务名（见 mcp_tool_list）"},
            "tool": {"type": "string", "description": "该服务提供的工具名（见 mcp_tool_list）"},
            "arguments": {"type": "string", "description": "JSON 对象字符串形式的工具参数，如 {\"query\": \"天气\"}"},
        },
        "required": ["server", "tool"],
    },
    risk="medium",
)
def mcp_call_tool(server: str, tool: str, arguments: str = "") -> str:
    name = (server or "").strip()
    item = mcp_store.get_mcp(name)
    if not item:
        return f"MCP 服务不存在: {name}（可用服务见 mcp_tool_list）"
    if not item.get("enabled"):
        return f"MCP 服务 {name} 未启用，先在能力中心启用再调用"
    if not item.get("config"):
        return f"MCP 服务 {name} 缺少 config"
    try:
        args = json.loads(arguments) if arguments and arguments.strip() else {}
    except json.JSONDecodeError:
        return "arguments 不是合法的 JSON 对象"
    if not isinstance(args, dict):
        return "arguments 必须是 JSON 对象"
    return mcp_client.call_tool(item, tool, args)
