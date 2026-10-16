"""三级记忆合并检索：语义 > 情景 > 工作，带时间衰减。

供 Leader 决策提示注入（memory_brief）与 memory_query 工具 / REST 查询使用。
"""
from __future__ import annotations

import re
import time

from . import store

# 基础优先级：语义 > 情景 > 工作
_PRIORITY = {"semantic": 3.0, "episodic": 2.0, "working": 1.0}
# 时间衰减半衰期（天）：长期知识最耐用，工作记忆最容易过期
_HALF_LIFE_DAYS = {"semantic": 365.0, "episodic": 30.0, "working": 1.0}


def _text_of(item: dict) -> str:
    tier = item.get("type", "")
    if tier == "semantic":
        return f"{item.get('topic', '')} {' '.join(item.get('points', []))}"
    if tier == "episodic":
        return (
            f"{item.get('task', '')} {item.get('action', '')} "
            f"{item.get('result', '')} {item.get('agents', '')}"
        )
    return f"{item.get('session', '')} {item.get('content', '')}"


def _hit_count(text: str, keyword: str) -> int:
    return len(re.findall(re.escape(keyword), text))


def _age_days(item: dict) -> float:
    ts = item.get("updated_at") or item.get("created_at") or item.get("time") or ""
    try:
        dt = time.mktime(time.strptime(ts, "%Y-%m-%d %H:%M:%S"))
    except Exception:  # noqa: BLE001
        return 0.0
    return max(0.0, (time.time() - dt) / 86400.0)


def _title_of(item: dict) -> str:
    tier = item.get("type", "")
    if tier == "semantic":
        return item.get("topic", "")
    if tier == "episodic":
        return item.get("task", "") or "情景事件"
    return f"工作记忆[{item.get('session', 'default')}]"


def _snippet_of(item: dict, keyword: str) -> str:
    text = _text_of(item)
    idx = text.find(keyword)
    if idx < 0:
        return text[:80]
    return text[max(0, idx - 20):idx + 60]


def query(keyword: str = "", limit: int = 10) -> list[dict]:
    """按关键词检索三级记忆并合并排序返回。

    排序规则：score = 基础优先级 × 时间衰减 × (1 + 0.5 × (命中次数 - 1))。
    返回 [{tier, id, title, snippet, score, time}]，按 score 降序。
    """
    keyword = (keyword or "").strip()
    limit = max(1, min(int(limit or 10), 100))
    if not keyword:
        return []

    results: list[dict] = []
    for tier in ("semantic", "episodic", "working"):
        for item in store.list_tier(tier):
            text = _text_of(item)
            hits = _hit_count(text, keyword)
            if hits <= 0:
                continue
            age = _age_days(item)
            decay = 1.0 / (1.0 + age / _HALF_LIFE_DAYS.get(tier, 30.0))
            score = round(_PRIORITY[tier] * decay * (1.0 + 0.5 * (hits - 1)), 4)
            results.append({
                "tier": tier,
                "id": item.get("id", ""),
                "title": _title_of(item),
                "snippet": _snippet_of(item, keyword),
                "score": score,
                "time": item.get("updated_at") or item.get("created_at") or item.get("time") or "",
            })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def memory_brief(limit: int = 8, top_semantic: int = 4) -> str:
    """供 Leader 决策提示注入的三级记忆简报（语义 / 情景 / 工作上下文）。"""
    lines: list[str] = []
    sem = store.list_tier("semantic")[:top_semantic]
    if sem:
        lines.append("【长期语义记忆】")
        for it in sem:
            pts = "；".join(it.get("points", [])[:3])
            lines.append(f"- {it.get('topic', '')}（置信 {it.get('confidence', 0)}）：{pts}")
    epi = store.list_tier("episodic")[:max(1, limit - top_semantic)]
    if epi:
        lines.append("【近期情景记忆】")
        for it in epi:
            lines.append(f"- [{it.get('time', '')}] {it.get('task', '')}→{it.get('result', '')}")
    wk = store.list_tier("working")[:3]
    if wk:
        lines.append("【当前工作上下文】")
        for it in wk:
            lines.append(f"- {it.get('session', 'default')}: {it.get('content', '')[:60]}")
    return "\n".join(lines)
