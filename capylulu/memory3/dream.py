"""Deep Dream 蒸馏引擎：情景记忆 → 语义记忆。

- LLM 模式：把一批情景事件交给 LLM 总结为主题 / 要点 / 来源 / 置信度，生成或合并语义条目；
- 规则模式：LLM 不可用（无 API Key / 超时 / 解析失败）时降级为关键词提取 + 高频主题聚合；
- 触发方式：手动 deep_dream() 与按间隔自动触发 maybe_auto_dream(interval_seconds)。
- 间隔判定：简单时间戳（data/memory/.last_dream.json），不引入调度框架。
"""
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path

from ..config import config
from ..llm import create_llm
from . import store

LAST_DREAM_FILE: Path = config.data_dir / "memory" / ".last_dream.json"

_STOPWORDS = {
    "的", "了", "和", "与", "在", "我", "你", "他", "它", "是", "把", "被",
    "给", "对", "从", "到", "用", "做", "这个", "那个", "一下", "一个",
    "然后", "因为", "所以", "以及", "进行", "可以", "我们", "你们", "他们",
}


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global LAST_DREAM_FILE
    LAST_DREAM_FILE = store.MEMORY_DIR / ".last_dream.json"


# ---------------- LLM 蒸馏 ----------------

def _build_prompt(events: list[dict]) -> str:
    lines = []
    for ev in events:
        lines.append(
            f"- 事件：{ev.get('task', '')}｜动作：{ev.get('action', '')}｜"
            f"结果：{ev.get('result', '')}｜参与者：{ev.get('agents', '')}"
        )
    return (
        "你是记忆蒸馏引擎。请把下面的情景事件总结为若干条长期语义记忆（每条一个主题）。\n"
        "输出 JSON 数组，每项格式："
        "{\"topic\": \"主题(10字以内)\", \"points\": [\"要点1\", \"要点2\"], "
        "\"sources\": [\"来源事件简述\"], \"confidence\": 0到1之间的数字}\n"
        "要点需凝练事实与结论，不要重复事件原话。只输出 JSON，不要解释。\n\n事件列表：\n"
        + "\n".join(lines)
    )


def _parse_json_array(text: str) -> list[dict] | None:
    """容错解析 LLM 输出的 JSON 数组（支持 ```json 围栏与前后杂质文本）。"""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        start = text.index("[")
        end = text.rindex("]")
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, list) else None
    except Exception:  # noqa: BLE001
        return None


def _llm_distill(events: list[dict]) -> list[dict] | None:
    """LLM 总结蒸馏；任何失败返回 None 以触发规则降级。"""
    try:
        llm = create_llm()
        resp = llm.chat([{"role": "user", "content": _build_prompt(events)}])
        return _parse_json_array(resp.get("content") or "")
    except Exception:  # noqa: BLE001
        return None


# ---------------- 规则降级 ----------------

def _tokenize(text: str) -> list[str]:
    """粗粒度分词：2~4 字中文窗口 + 英文/数字词，过滤停用词。"""
    tokens: list[str] = []
    text = re.sub(r"\s+", "", text or "")
    for m in re.finditer(r"[A-Za-z0-9_]{2,}", text):
        tokens.append(m.group(0).lower())
    for n in (2, 3, 4):
        for i in range(len(text) - n + 1):
            seg = text[i:i + n]
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", seg) and seg not in _STOPWORDS:
                tokens.append(seg)
    return tokens


def _rule_distill(events: list[dict], top_k: int = 5) -> list[dict]:
    """规则降级：关键词频次 → 高频主题聚类，生成语义条目。"""
    counter: Counter = Counter()
    for ev in events:
        text = f"{ev.get('task', '')} {ev.get('action', '')} {ev.get('result', '')}"
        for t in _tokenize(text):
            counter[t] += 1
    best = [w for w, _ in counter.most_common(top_k) if w]
    results: list[dict] = []
    for topic in best:
        hits = [
            ev for ev in events
            if topic in f"{ev.get('task', '')} {ev.get('action', '')} {ev.get('result', '')}"
        ]
        support = len(hits)
        points: list[str] = []
        for ev in hits[:5]:
            pts = f"{ev.get('task', '')}: {ev.get('result', '')}".strip(" :")
            if pts and pts not in points:
                points.append(pts[:60])
        results.append({
            "topic": topic,
            "points": points or [f"多次出现主题「{topic}」"],
            "sources": [ev.get("id", "") for ev in hits][:10],
            "confidence": round(min(0.9, 0.3 + 0.15 * support), 2),
        })
    return results


# ---------------- 触发与状态 ----------------

def _last_dream_ts() -> float | None:
    try:
        data = json.loads(LAST_DREAM_FILE.read_text(encoding="utf-8"))
        return float(data.get("ts", 0))
    except Exception:  # noqa: BLE001
        return None


def _mark_last_dream() -> None:
    LAST_DREAM_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_DREAM_FILE.write_text(
        json.dumps({"ts": time.time()}, ensure_ascii=False), encoding="utf-8"
    )


def last_dream_status() -> dict:
    """上次蒸馏状态（供前端展示）。"""
    last = _last_dream_ts()
    return {
        "last_ts": last,
        "last_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last)) if last else None,
        "episodic_count": store.count_tier("episodic"),
        "semantic_count": store.count_tier("semantic"),
        "working_count": store.count_tier("working"),
    }


def deep_dream(limit: int = 50, force: bool = False) -> dict:
    """手动触发蒸馏：把情景记忆批量蒸馏为语义记忆。返回报告 dict。"""
    events = store.list_tier("episodic")[:max(1, int(limit or 50))]
    if not events:
        return {
            "ok": True, "mode": "skip",
            "message": "没有情景记忆可蒸馏，先记录事件（memory_log_event）再触发",
            "distilled": 0, "created": 0, "merged": 0,
        }

    distilled = _llm_distill(events)
    mode = "llm" if distilled is not None else "rule"
    if distilled is None:
        distilled = _rule_distill(events)

    created = merged = 0
    for item in distilled:
        r = store.save_semantic(
            topic=item.get("topic", "未命名主题")[:40],
            points=item.get("points") or [],
            sources=item.get("sources") or [],
            confidence=float(item.get("confidence") or 0.7),
        )
        if r.get("merged"):
            merged += 1
        else:
            created += 1
    _mark_last_dream()
    mode_txt = "LLM 蒸馏" if mode == "llm" else "规则降级蒸馏（LLM 不可用）"
    return {
        "ok": True,
        "mode": mode,
        "message": f"✓ 深度蒸馏完成（{mode_txt}）：处理 {len(events)} 条情景，新建 {created} 条语义、合并 {merged} 条",
        "distilled": len(events),
        "created": created,
        "merged": merged,
    }


def maybe_auto_dream(interval_seconds: int = 3600, limit: int = 50) -> dict:
    """按间隔自动触发：距上次蒸馏超过 interval 且有情景事件时才执行。"""
    interval = max(60, int(interval_seconds or 3600))
    last = _last_dream_ts()
    now_ts = time.time()
    if last is not None and (now_ts - last) < interval:
        return {
            "ok": True, "mode": "skip",
            "message": f"距上次蒸馏 {now_ts - last:.0f}s，未到间隔 {interval}s，跳过",
            "distilled": 0, "created": 0, "merged": 0,
        }
    if not store.list_tier("episodic"):
        return {
            "ok": True, "mode": "skip",
            "message": "无情景记忆，跳过自动蒸馏",
            "distilled": 0, "created": 0, "merged": 0,
        }
    return deep_dream(limit=limit, force=True)
