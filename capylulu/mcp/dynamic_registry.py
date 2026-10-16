"""MCP 工具动态注册：把已接入且启用的 MCP server 工具注册进主工具注册表。

命名规则：mcp_<server>_<tool>（server / tool 中的非字母数字下划线替换为 _），
注册后 Leader 与各 Agent 可像本地工具一样通过 registry 直接调用；
调用代理会把参数转发到 mcp/client.py 的 call_tool 执行真实 MCP 调用。
"""
from __future__ import annotations

import re

from . import client as mcp_client
from . import store as mcp_store
from ..tools.registry import clear_dynamic, register_dynamic, unregister_dynamic

PREFIX = "mcp_"
RISK = "medium"  # MCP 远端工具默认中风险：执行时记录调用日志


def _sanitize(s: str) -> str:
    """只保留字母数字下划线，其余替换为 _。"""
    return re.sub(r"[^A-Za-z0-9_]", "_", str(s or "")).strip("_") or "_"


def _full_name(server: str, tool: str) -> str:
    return f"{PREFIX}{_sanitize(server)}_{_sanitize(tool)}"


def _schema_to_parameters(input_schema) -> dict:
    """MCP inputSchema（JSON Schema）转 registry 的 parameters 结构。"""
    if not isinstance(input_schema, dict):
        return {"type": "object", "properties": {}}
    params = {"type": "object", "properties": input_schema.get("properties") or {}}
    required = input_schema.get("required")
    if isinstance(required, list) and required:
        params["required"] = required
    return params


def _make_proxy(server_item: dict, tool_name: str):
    """生成调用代理：接收 **kwargs 转发到 mcp/client.py 执行真实调用。"""
    def proxy(**kwargs):
        return mcp_client.call_tool(server_item, tool_name, kwargs or {})
    return proxy


def register_server_tools(server_item: dict) -> tuple[int, list[str]]:
    """注册单个 server 的 tools_cache；返回 (成功数, 错误列表)。"""
    ok, errs = 0, []
    server_name = server_item.get("name", "")
    for t in server_item.get("tools_cache") or []:
        tname = t.get("name") or ""
        if not tname:
            errs.append(f"{server_name}: 工具缺少 name，跳过")
            continue
        full = _full_name(server_name, tname)
        desc = t.get("description") or f"{server_name} 的 {tname} 工具（MCP 动态注册）"
        register_dynamic(
            full,
            desc,
            _schema_to_parameters(t.get("inputSchema")),
            _make_proxy(server_item, tname),
            risk=RISK,
        )
        ok += 1
    return ok, errs


def refresh_enabled_mcp_tools() -> dict:
    """清空旧 mcp_* 动态注册，重刷所有已启用且有工具缓存的服务。

    返回 {"removed": 清理数, "registered": 注册数, "servers": 涉及服务数, "errors": [...]}
    """
    removed = clear_dynamic(PREFIX)
    total, servers = 0, 0
    errors: list[str] = []
    for s in mcp_store.enabled_servers():
        ok, errs = register_server_tools(s)
        total += ok
        if ok:
            servers += 1
        errors.extend(errs)
    return {"removed": removed, "registered": total, "servers": servers, "errors": errors}


def unregister_server_tools(server_item: dict) -> int:
    """移除某 server 的全部 mcp_* 动态工具（停用 / 删除服务时调用）。"""
    n = 0
    server_name = server_item.get("name", "")
    for t in server_item.get("tools_cache") or []:
        if unregister_dynamic(_full_name(server_name, t.get("name") or "")):
            n += 1
    return n


def dynamic_tool_status() -> list[dict]:
    """当前已注册的 mcp_* 动态工具清单（供前端能力中心展示）。"""
    from ..tools.registry import _tool_registry

    out = []
    for name, entry in _tool_registry.items():
        if name.startswith(PREFIX):
            schema = entry.get("schema") or {}
            fn = schema.get("function") or {}
            out.append({
                "name": name,
                "risk": entry.get("risk", RISK),
                "description": fn.get("description", ""),
            })
    return sorted(out, key=lambda x: x["name"])
