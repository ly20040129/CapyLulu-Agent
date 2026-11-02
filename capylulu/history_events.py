"""会话事件日志：追加式 JSONL + 回放（history.py 的增强，保持旧接口兼容）。

事件文件：<data_dir>/sessions/<sess_id>.jsonl，每行一个事件。
事件类型：
    session/created / user/message / assistant/message
    tool/call / tool/result（result 截断 500 字符）/ agent/assign / compress
默认开关 config.agent.get("event_log", True)；关闭时不写盘。
支持 register_event_writer 替换写入后端（默认 JSONL 文件）。
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable

from loguru import logger

from .config import config

_RESULT_MAX = 500

# 自定义事件写入后端：name -> fn(sess_id, event) -> bool
_event_writers: dict[str, Callable[[str, dict], bool]] = {}


def _enabled() -> bool:
    return bool(config.agent.get("event_log", True))


def _event_path(sess_id: str) -> Path:
    base = config.data_dir / "sessions"
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{sess_id}.jsonl"


def register_event_writer(name: str, fn: Callable[[str, dict], bool]) -> bool:
    """注册自定义事件写入后端；注册后 append_event 优先走它（替换默认 JSONL）。"""
    if not name or name in _event_writers:
        return False
    _event_writers[name] = fn
    return True


def unregister_event_writer(name: str) -> bool:
    """注销自定义写入后端；返回是否真的移除。"""
    return _event_writers.pop(name, None) is not None


def append_event(sess_id: str, event: dict) -> bool:
    """追加一行事件；目录不存在自动建。返回是否成功写盘。"""
    if not _enabled():
        return False
    event = dict(event)
    event.setdefault("ts", time.time())
    if event.get("type") == "tool/result":
        result = event.get("result", "")
        if isinstance(result, str) and len(result) > _RESULT_MAX:
            event["result"] = result[:_RESULT_MAX] + "...(已截断)"
    # 已注册自定义后端时优先调用（可替换默认 JSONL）
    for name, fn in list(_event_writers.items()):
        try:
            if fn(sess_id, event):
                return True
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[Events] 自定义写入后端 {name} 失败：{e}")
    try:
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
        with open(_event_path(sess_id), "a", encoding="utf-8") as f:
            f.write(line + "\n")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[Events] 事件写入失败：{e}")
        return False


def _events_of(sess_id: str) -> list[dict]:
    path = _event_path(sess_id)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def replay(sess_id: str) -> list[dict]:
    """按时间顺序重放为 OpenAI messages（user / assistant / tool 三角色）。"""
    messages: list[dict] = []
    tool_id: dict[str, str] = {}  # 最近一次 tool/call 生成的 id（按工具名）
    seq = 0
    for ev in _events_of(sess_id):
        typ = ev.get("type")
        if typ == "session/created":
            continue
        if typ == "user/message":
            messages.append({"role": "user", "content": ev.get("content", "")})
        elif typ == "assistant/message":
            messages.append({"role": "assistant", "content": ev.get("content", "")})
        elif typ == "tool/call":
            seq += 1
            cid = f"call_{seq}"
            tool_id[ev.get("name", "")] = cid
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": cid,
                    "type": "function",
                    "function": {
                        "name": ev.get("name", ""),
                        "arguments": json.dumps(ev.get("arguments") or {}, ensure_ascii=False),
                    },
                }],
            })
        elif typ == "tool/result":
            cid = tool_id.get(ev.get("name", ""))
            if cid:
                messages.append({
                    "role": "tool",
                    "tool_call_id": cid,
                    "content": ev.get("result", ""),
                })
        elif typ == "agent/assign":
            messages.append({"role": "user", "content": f"（任务派发给 {ev.get('agent', '')}）"})
        elif typ == "compress":
            messages.append({"role": "system", "content": "历史摘要（供上下文参考）：" + ev.get("summary", "")})
    return messages


def list_event_sessions() -> list[str]:
    """返回已有事件日志的会话 id 列表。"""
    base = config.data_dir / "sessions"
    if not base.exists():
        return []
    return sorted(p.stem for p in base.glob("*.jsonl"))


def clear_events(sess_id: str) -> bool:
    """删除指定会话的事件日志；返回是否真的删除。"""
    path = _event_path(sess_id)
    if not path.exists():
        return False
    try:
        path.unlink()
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[Events] 事件日志清理失败：{e}")
        return False
