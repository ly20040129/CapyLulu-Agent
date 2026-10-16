"""MCP 接入存储：data/mcp.json，管理已接入的 MCP Server。

每项结构：
{
  "name": "服务名",
  "type": "stdio | sse | http",
  "config": {  # 按类型：
      # stdio: {"command": "...", "args": [...], "env": {...}}
      # sse/http: {"url": "..."}
  },
  "enabled": true,
  "tools_cache": [{"name": "...", "description": "...", "inputSchema": {...}}],
  "added_at": "2026-10-14 10:00:00"
}
"""
from __future__ import annotations

import json
from datetime import datetime

from capylulu.config import config

STORE = config.data_dir / "mcp.json"

VALID_TYPES = ("stdio", "sse", "http")


def _load() -> list[dict]:
    if not STORE.exists():
        return []
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _save(data: list[dict]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_mcps() -> list[dict]:
    return _load()


def get_mcp(name: str) -> dict | None:
    return next((x for x in _load() if x.get("name") == name), None)


def add_mcp(name: str, mtype: str, config_json: str, enabled: bool = True) -> str:
    name = (name or "").strip()
    mtype = (mtype or "").strip().lower()
    if not name:
        return "服务名不能为空"
    if mtype not in VALID_TYPES:
        return f"type 仅支持: {', '.join(VALID_TYPES)}"
    try:
        conf = json.loads(config_json) if config_json and config_json.strip() else {}
    except json.JSONDecodeError:
        return "config 不是合法的 JSON"
    if not isinstance(conf, dict):
        return "config 必须是 JSON 对象"
    if mtype == "stdio":
        if not conf.get("command"):
            return "stdio 类型需要 config.command（启动命令）"
    else:
        if not conf.get("url"):
            return f"{mtype} 类型需要 config.url"
    data = _load()
    if any(x.get("name") == name for x in data):
        return f"服务 {name} 已存在"
    data.append({
        "name": name,
        "type": mtype,
        "config": conf,
        "enabled": bool(enabled),
        "tools_cache": [],
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save(data)
    return f"已接入 MCP 服务 {name}"


def update_mcp(name: str, config_json: str, enabled: bool | None = None) -> str:
    data = _load()
    item = next((x for x in data if x.get("name") == name), None)
    if not item:
        return f"服务 {name} 不存在"
    try:
        conf = json.loads(config_json) if config_json and config_json.strip() else item.get("config", {})
    except json.JSONDecodeError:
        return "config 不是合法的 JSON"
    if not isinstance(conf, dict):
        return "config 必须是 JSON 对象"
    item["config"] = conf
    item["type"] = (item.get("type") or "stdio").lower()
    if item["type"] == "stdio" and not conf.get("command"):
        return "stdio 类型需要 config.command"
    if item["type"] in ("sse", "http") and not conf.get("url"):
        return f"{item['type']} 类型需要 config.url"
    item["tools_cache"] = []  # 配置变了，旧缓存作废
    if enabled is not None:
        item["enabled"] = bool(enabled)
    _save(data)
    return f"已更新服务 {name}"


def remove_mcp(name: str) -> str:
    data = _load()
    nxt = [x for x in data if x.get("name") != name]
    if len(nxt) == len(data):
        return f"服务 {name} 不存在"
    _save(nxt)
    return f"已移除服务 {name}"


def set_enabled(name: str, enabled: bool) -> str:
    data = _load()
    item = next((x for x in data if x.get("name") == name), None)
    if not item:
        return f"服务 {name} 不存在"
    item["enabled"] = bool(enabled)
    _save(data)
    return f"已{'启用' if enabled else '停用'}服务 {name}"


def set_tools_cache(name: str, tools: list[dict]) -> None:
    data = _load()
    item = next((x for x in data if x.get("name") == name), None)
    if not item:
        return
    item["tools_cache"] = tools[:100]
    _save(data)


def enabled_servers() -> list[dict]:
    """当前启用中的服务（供 LLM 工具清单展示）"""
    return [x for x in _load() if x.get("enabled")]
