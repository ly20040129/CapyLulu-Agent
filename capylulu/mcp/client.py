"""MCP 客户端：按配置建立 stdio / sse / http 连接，提供工具列表与调用。

依赖官方 mcp SDK（pip install mcp）。SDK 缺失时优雅降级，返回可读错误。
"""
from __future__ import annotations

import asyncio
from typing import Any

from . import store as mcp_store

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client

    SDK_READY = True
except Exception:  # noqa: BLE001
    SDK_READY = False

# http 客户端在新版 SDK（mcp>=1.8 附近）才有，旧版缺失时降级提示
try:
    from mcp.client.http import http_client

    HTTP_READY = True
except Exception:  # noqa: BLE001
    HTTP_READY = False


def sdk_ok() -> str:
    return "" if SDK_READY else "MCP SDK 未安装（pip install mcp）"


def _entry(cfg: dict) -> tuple:
    """返回 (进入函数, 参数)：mcp 1.x 的 asynccontextmanager 支持 async with 直接解包。"""
    mtype = (cfg.get("type") or "stdio").lower()
    conf = cfg.get("config") or {}
    if mtype == "stdio":
        params = StdioServerParameters(
            command=conf.get("command", ""),
            args=conf.get("args", []) or [],
            env=conf.get("env"),
        )
        return stdio_client, (params,)
    if mtype == "sse":
        return sse_client, (conf.get("url", ""),)
    if not HTTP_READY:
        raise RuntimeError("当前 MCP SDK 版本不支持 http 连接，请升级：pip install -U mcp")
    return http_client, (conf.get("url", ""),)


async def _session(cfg: dict):
    """生成 (ClientSession, 退出函数)；用法：
        enter, close, session = await _session(cfg)
    """
    if not SDK_READY:
        raise RuntimeError("MCP SDK 未安装（pip install mcp）")
    entry, args = _entry(cfg)
    ctx = entry(*args)
    read, write = await ctx.__aenter__()
    session = ClientSession(read, write)
    await session.__aenter__()
    await session.initialize()
    return session, ctx, session


async def _list_tools_async(cfg: dict) -> tuple[str, list[dict]]:
    if not SDK_READY:
        return "MCP SDK 未安装（pip install mcp）", []
    entry, args = _entry(cfg)
    ctx = entry(*args)
    read, write = await ctx.__aenter__()
    try:
        session = ClientSession(read, write)
        await session.__aenter__()
        try:
            await session.initialize()
            tools = await session.list_tools()
            out = [{
                "name": t.name,
                "description": (t.description or "")[:200],
                "inputSchema": t.inputSchema or {},
            } for t in tools.tools]
            return "", out
        finally:
            await session.__aexit__(None, None, None)
    finally:
        await ctx.__aexit__(None, None, None)


async def _call_tool_async(cfg: dict, tool_name: str, arguments: dict) -> str:
    if not SDK_READY:
        return "MCP SDK 未安装（pip install mcp）"
    entry, args = _entry(cfg)
    ctx = entry(*args)
    read, write = await ctx.__aenter__()
    try:
        session = ClientSession(read, write)
        await session.__aenter__()
        try:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments or {})
            parts = []
            for c in result.content or []:
                text = getattr(c, "text", None)
                if text:
                    parts.append(text)
                else:
                    parts.append(str(c))
            if result.structuredContent:
                import json

                parts.append(json.dumps(result.structuredContent, ensure_ascii=False)[:2000])
            if result.isError:
                return "MCP 工具执行出错: " + ("\n".join(parts) or "unknown error")
            return "\n".join(parts) if parts else "(无返回内容)"
        finally:
            await session.__aexit__(None, None, None)
    finally:
        await ctx.__aexit__(None, None, None)


def list_tools(cfg: dict) -> tuple[str, list[dict]]:
    """同步入口：连接并列出该服务工具。返回 (错误信息, 工具列表)。"""
    try:
        return asyncio.run(_list_tools_async(cfg))
    except Exception as exc:  # noqa: BLE001
        return f"连接失败: {exc}", []


def call_tool(cfg: dict, tool_name: str, arguments: dict) -> str:
    """同步入口：调用该服务下某个工具。"""
    try:
        return asyncio.run(_call_tool_async(cfg, tool_name, arguments or {}))
    except Exception as exc:  # noqa: BLE001
        return f"MCP 调用失败: {exc}"
