"""MCP 市场：内置常见 MCP 服务目录，支持关键字搜索与一键安装。

安装流程：把市场条目写入 data/mcp.json（mcp_store.add_mcp）→ 立即触发一次
工具列表刷新（mcp_client.list_tools 真实连接）→ 成功后写入 tools_cache 并
执行动态注册（refresh_enabled_mcp_tools），使 Leader 与各 Agent 立刻可调。
连接失败不阻断安装：条目保留，用户可在能力中心手动「测试连接」刷新。
"""
from __future__ import annotations

import json

from . import client as mcp_client
from . import store as mcp_store
from .dynamic_registry import refresh_enabled_mcp_tools

# 内置市场目录：均为官方 / 常见 MCP 服务；stdio 条目可直接 npx 启动，
# http 条目需自行部署或提供网络可达地址（desc 中已注明）。
MARKET_ITEMS: list[dict] = [
    {
        "name": "filesystem",
        "display": "文件系统",
        "type": "stdio",
        "config": {"command": "cmd.exe", "args": ["/c", "D:\\nodejs\\npx.cmd", "-y", "@modelcontextprotocol/server-filesystem", "D:/"]},
        "desc": "本地文件读写、目录遍历与操作（官方 reference server）",
        "keywords": ["文件", "fs", "目录", "file", "filesystem"],
    },
    {
        "name": "fetch",
        "display": "网页抓取",
        "type": "stdio",
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-fetch"]},
        "desc": "抓取网页内容并转成 Markdown（官方 reference server）",
        "keywords": ["网页", "抓取", "url", "fetch", "html"],
    },
    {
        "name": "memory",
        "display": "记忆图谱",
        "type": "stdio",
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-memory"]},
        "desc": "基于知识图谱的持久化记忆（官方 reference server）",
        "keywords": ["记忆", "知识图谱", "graph", "memory", "实体"],
    },
    {
        "name": "sequential-thinking",
        "display": "顺序思考",
        "type": "stdio",
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]},
        "desc": "结构化多步推理，适合拆解复杂问题（官方 reference server）",
        "keywords": ["思考", "推理", "reasoning", "thinking", "规划"],
    },
    {
        "name": "time",
        "display": "时间与时区",
        "type": "stdio",
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-time", "Asia/Shanghai"]},
        "desc": "当前时间与任意时区换算（官方 reference server）",
        "keywords": ["时间", "时区", "time", "date", "clock"],
    },
    {
        "name": "git",
        "display": "Git 仓库",
        "type": "stdio",
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-git", "."]},
        "desc": "Git 仓库查询与操作（官方 reference server；args 末尾可改仓库路径）",
        "keywords": ["git", "仓库", "repo", "提交", "commit"],
    },
    {
        "name": "sqlite",
        "display": "SQLite 数据库",
        "type": "stdio",
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sqlite", "D:/data.db"]},
        "desc": "SQLite 查询与表结构管理（官方 reference server；args 末尾可改库文件）",
        "keywords": ["数据库", "sqlite", "sql", "db", "查询"],
    },
    {
        "name": "everart",
        "display": "AI 绘图",
        "type": "stdio",
        "config": {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-everart"]},
        "desc": "AI 图像生成（需 EVERART_API_KEY 环境变量）",
        "keywords": ["绘图", "图像", "画图", "everart", "ai画图"],
    },
    {
        "name": "github",
        "display": "GitHub",
        "type": "http",
        "config": {"url": "https://api.githubcopilot.com/mcp/"},
        "desc": "GitHub 仓库 / Issue / PR 操作（需 GITHUB_TOKEN 环境变量或网关鉴权）",
        "keywords": ["github", "仓库", "issue", "pr", "代码"],
    },
    {
        "name": "weather",
        "display": "天气查询",
        "type": "http",
        "config": {"url": "http://localhost:8080/mcp"},
        "desc": "天气查询示例（需自行部署 MCP 天气服务，并替换 url）",
        "keywords": ["天气", "weather", "温度", "气温"],
    },
]


def search(keyword: str = "") -> list[dict]:
    """按关键字搜索市场目录（匹配 name / display / desc / keywords）。"""
    kw = (keyword or "").strip().lower()
    if not kw:
        return [dict(x) for x in MARKET_ITEMS]
    out = []
    for x in MARKET_ITEMS:
        hay = " ".join([
            x.get("name", ""),
            x.get("display", ""),
            x.get("desc", ""),
            " ".join(x.get("keywords") or []),
        ]).lower()
        if kw in hay:
            out.append(dict(x))
    return out


def get(name: str) -> dict | None:
    return next((x for x in MARKET_ITEMS if x.get("name") == (name or "").strip()), None)


def install(name: str) -> tuple[bool, str, dict | None]:
    """一键安装市场服务。返回 (是否成功安装, 消息, 市场条目)。

    安装后自动触发工具列表刷新；连接失败时条目保留并提示手动测试。
    """
    item = get(name)
    if not item:
        return False, f"市场不存在该服务: {name}", None
    if mcp_store.get_mcp(item["name"]):
        return False, f"服务 {item['name']} 已接入，无需重复安装", item
    msg = mcp_store.add_mcp(
        item["name"], item["type"], json.dumps(item["config"], ensure_ascii=False), enabled=True
    )
    if "已接入" not in msg:
        return False, msg, item
    # 安装后触发工具列表刷新：真实连接一次
    cfg = mcp_store.get_mcp(item["name"])
    err, tools = mcp_client.list_tools(cfg)
    if err:
        return True, f"已安装「{item['name']}」，但连接失败：{err}（可在能力中心测试连接后刷新工具）", item
    mcp_store.set_tools_cache(item["name"], tools)
    refreshed = refresh_enabled_mcp_tools()
    return (
        True,
        f"已安装「{item['name']}」，发现 {len(tools)} 个工具，"
        f"动态注册 {refreshed['registered']} 个（mcp_{item['name']}_*）",
        item,
    )
