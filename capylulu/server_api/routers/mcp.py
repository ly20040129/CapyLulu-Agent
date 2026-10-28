"""MCP 能力中心：MCP Server 增删改查、启停、工具列表与连通性测试。

- GET/POST /mcp/servers：服务器列表 / 新增；
- PUT/DELETE /mcp/servers/{name}：更新 / 移除；
- PATCH /mcp/servers/{name}/enabled：启停；
- POST/GET /mcp/servers/{name}/test|tools：连通性测试 / 工具列表；
- GET/POST /mcp/market(|/install)：市场搜索 / 一键安装；
- GET/POST /mcp/dynamic|refresh：动态注册工具查看 / 一键重刷。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capylulu.mcp import client as mcp_client
from capylulu.mcp import dynamic_registry
from capylulu.mcp import market
from capylulu.mcp import store as mcp_store

router = APIRouter(tags=["mcp"])


class McpBody(BaseModel):
    name: str = ""
    type: str = "stdio"
    config: str = ""
    enabled: bool = True


@router.get("/mcp/servers")
def list_servers() -> dict:
    """已配置的 MCP 服务器列表（含 SDK 是否可用）。"""
    return {"items": mcp_store.load_mcps(), "sdk_ok": mcp_client.sdk_ok()}


@router.post("/mcp/servers")
def add_server(body: McpBody) -> dict:
    """新增 MCP 服务器配置。"""
    msg = mcp_store.add_mcp(body.name, body.type, body.config, body.enabled)
    if "已接入" not in msg and "已存在" not in msg:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.put("/mcp/servers/{name}")
def update_server(name: str, body: McpBody) -> dict:
    """更新 MCP 服务器配置。"""
    msg = mcp_store.update_mcp(name, body.config, body.enabled)
    if "已更新" not in msg:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.delete("/mcp/servers/{name}")
def remove_server(name: str) -> dict:
    """移除 MCP 服务器配置。"""
    msg = mcp_store.remove_mcp(name)
    if "已移除" not in msg:
        raise HTTPException(status_code=404, detail=msg)
    dynamic_registry.refresh_enabled_mcp_tools()  # 移除后重刷动态注册
    return {"ok": True, "message": msg}


class ToggleBody(BaseModel):
    enabled: bool = True


@router.patch("/mcp/servers/{name}/enabled")
def toggle_server(name: str, body: ToggleBody) -> dict:
    """启用 / 停用 MCP 服务器。"""
    msg = mcp_store.set_enabled(name, body.enabled)
    if "不存在" in msg:
        raise HTTPException(status_code=404, detail=msg)
    dynamic_registry.refresh_enabled_mcp_tools()  # 启用状态变化后重刷动态注册
    return {"ok": True, "message": msg}


@router.post("/mcp/servers/{name}/test")
def test_server(name: str) -> dict:
    """连通性测试：连接服务器并拉取工具清单。"""
    item = mcp_store.get_mcp(name)
    if not item:
        raise HTTPException(status_code=404, detail=f"服务 {name} 不存在")
    err, tools = mcp_client.list_tools(item)
    if err:
        return {"ok": False, "message": err, "count": 0}
    mcp_store.set_tools_cache(name, tools)
    if item.get("enabled"):
        refreshed = dynamic_registry.refresh_enabled_mcp_tools()
        return {
            "ok": True,
            "message": f"连接成功，共 {len(tools)} 个工具，动态注册 {refreshed['registered']} 个",
            "count": len(tools),
            "tools": tools,
            "registered": refreshed["registered"],
        }
    return {"ok": True, "message": f"连接成功，共 {len(tools)} 个工具", "count": len(tools), "tools": tools}


@router.get("/mcp/servers/{name}/tools")
def server_tools(name: str) -> dict:
    """浏览指定服务器的工具清单（拉取后写入缓存并同步动态注册）。"""
    item = mcp_store.get_mcp(name)
    if not item:
        raise HTTPException(status_code=404, detail=f"服务 {name} 不存在")
    err, tools = mcp_client.list_tools(item)
    if err:
        raise HTTPException(status_code=502, detail=err)
    mcp_store.set_tools_cache(name, tools)
    if item.get("enabled"):
        dynamic_registry.refresh_enabled_mcp_tools()  # 工具清单更新后同步动态注册
    return {"items": tools}


# ---------------- MCP 市场与动态注册 ----------------

class MarketInstallBody(BaseModel):
    name: str = ""


@router.get("/mcp/market")
def market_search(q: str = "") -> dict:
    """市场目录搜索：q 为空返回全部内置服务。"""
    return {"items": market.search(q), "total": len(market.MARKET_ITEMS)}


@router.post("/mcp/market/install")
def market_install(body: MarketInstallBody) -> dict:
    """一键安装市场服务：写入 mcp.json 并触发工具列表刷新 + 动态注册。"""
    ok, msg, item = market.install(body.name)
    if not ok:
        status = 400 if item else 404
        raise HTTPException(status_code=status, detail=msg)
    return {"ok": True, "message": msg, "name": item["name"]}


@router.get("/mcp/dynamic")
def dynamic_tools() -> dict:
    """当前已动态注册进主工具表的 mcp_* 工具清单。"""
    items = dynamic_registry.dynamic_tool_status()
    return {"items": items, "count": len(items), "prefix": dynamic_registry.PREFIX}


@router.post("/mcp/refresh")
def refresh_dynamic() -> dict:
    """一键重刷：清空旧 mcp_* 注册，按已启用服务的工具缓存重新注册。"""
    result = dynamic_registry.refresh_enabled_mcp_tools()
    return {"ok": True, "message": f"动态注册已刷新，当前 {result['registered']} 个工具", **result}
