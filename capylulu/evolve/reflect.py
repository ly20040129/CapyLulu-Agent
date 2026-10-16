"""反思引擎：从任务台账提炼经验写入经验库。

批次7「自主进化」的感知层：读取 capylulu/team/store.py 的委派台账，对最近完成的
任务（done / failed / escalated）批量反思——

- LLM 模式：把任务清单交给 LLM，输出 JSON [{trigger, advice, task_ref, confidence}]；
- 规则降级：LLM 不可用（无 API Key / 超时 / 解析失败）时，对失败任务提取失败关键词
  模式、对成功任务提取成功模式，生成模板化经验；
- 去重：新增经验统一走 lessons.add_lesson，trigger + advice 相同则跳过，避免重复条目；
- 联动：每次反思把新经验写入 memory3 情景记忆，延续批次6 台账 → 记忆的蒸馏来源链。
"""
from __future__ import annotations

import json
import re
from collections import Counter

from ..config import config
from ..llm import create_llm
from .. import team
from ..memory3 import store as m3_store
from . import lessons

DONE_STATUSES = ("done", "failed", "escalated")

_FAIL_PATTERNS = [
    ("失败", "任务失败或执行未达预期"),
    ("出错", "执行过程报错"),
    ("错误", "出现错误"),
    ("找不到", "找不到目标文件 / 资源"),
    ("无法", "无法完成目标能力"),
    ("超时", "执行超时"),
    ("拒绝", "操作被拒绝"),
    ("异常", "出现异常"),
]
_SUCCESS_PATTERNS = [
    ("成功", "任务成功完成"),
    ("完成", "任务完成"),
    ("搞定", "任务搞定"),
]


def _llm_ready() -> bool:
    """是否已配置 API Key（与 ui.common._llm_ready 一致）。"""
    return bool(config.llm_config.get("api_key"))


# ---------------- LLM 反思 ----------------

def _build_prompt(tasks: list[dict]) -> str:
    lines = []
    for t in tasks:
        lines.append(
            f"- 任务：{t.get('task', '')}｜执行者：{t.get('agent', '')}｜"
            f"状态：{t.get('status', '')}｜结果：{t.get('result', '')}"
        )
    return (
        "你是自主进化反思引擎。请基于以下委派任务执行记录，提炼可复用的经验与教训。\n"
        "成功任务提炼「继续保持 / 推广」的做法；失败任务提炼「避免踩坑 / 改进」的建议。\n"
        "输出 JSON 数组，每项格式："
        "{\"trigger\": \"触发条件(一句话描述适用场景)\", "
        "\"advice\": \"建议(具体可执行的注意项或偏好，30字以内)\", "
        "\"task_ref\": \"来源任务简述(取自对应任务文本)\", "
        "\"confidence\": 0到1之间的数字}\n"
        "只输出 JSON，不要解释。\n\n任务记录：\n" + "\n".join(lines)
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


def _llm_reflect(tasks: list[dict]) -> list[dict] | None:
    """LLM 提炼经验；任何失败返回 None 以触发规则降级。"""
    try:
        llm = create_llm()
        resp = llm.chat([{"role": "user", "content": _build_prompt(tasks)}])
        return _parse_json_array(resp.get("content") or "")
    except Exception:  # noqa: BLE001
        return None


# ---------------- 规则降级 ----------------

def _aggregate(tasks: list[dict], patterns: list[tuple[str, str]], kind: str) -> list[dict]:
    """按关键词聚合任务，生成模板化经验。"""
    grouped: dict[str, list[dict]] = {}
    for t in tasks:
        text = f"{t.get('task', '')} {t.get('result', '')}"
        for kw, label in patterns:
            if kw in text:
                grouped.setdefault(kw, []).append(t)
                break
    results: list[dict] = []
    for kw, group in grouped.items():
        support = len(group)
        sample_task = group[-1].get("task", "")[:60]
        if kind == "fail":
            advice = (
                f"执行任务涉及「{kw}」类场景时，先检查前置条件与可用工具，"
                f"失败后尝试换路径或升级兜底，避免在同类问题上重复踩坑"
            )
        else:
            advice = (
                f"「{kw}」类做法被验证有效，可沿用：先明确目标再执行，"
                f"完成后及时记录结果，方便复盘复用"
            )
        results.append({
            "trigger": f"{label}（已出现 {support} 次，样例：{sample_task}）",
            "advice": advice[:120],
            "task_ref": "；".join(t.get("task", "")[:40] for t in group[:3]),
            "confidence": round(min(0.9, 0.4 + 0.12 * support), 2),
        })
    return results


def _rule_reflect(tasks: list[dict]) -> list[dict]:
    """规则降级：失败关键词模式 + 成功模式聚合。"""
    failed = [t for t in tasks if t.get("status") in ("failed", "escalated")]
    done = [t for t in tasks if t.get("status") == "done"]
    results: list[dict] = []
    results.extend(_aggregate(failed, _FAIL_PATTERNS, "fail"))
    results.extend(_aggregate(done, _SUCCESS_PATTERNS, "success"))
    return results


# ---------------- 反思入口 ----------------

def _sync_to_episodic(lesson: dict) -> None:
    """把新经验写入 memory3 情景记忆（try/except 包裹，不阻塞反思主流程）。"""
    try:
        m3_store.log_episodic(
            task=f"自主进化反思：{lesson.get('trigger', '')[:60]}",
            action="evolve.reflect",
            result=f"经验沉淀：{lesson.get('advice', '')[:120]}",
            agents="evolve",
        )
    except Exception:  # noqa: BLE001
        pass


def reflect(limit: int = 20, force: bool = False) -> dict:
    """从任务台账最近 limit 条已完成/失败委派批量反思，产出经验写入经验库。

    - force=False 时仅做校验（真正的间隔/任务数触发由 maybe_evolve 负责）；
    - 返回：reflected（反思的任务数）/ added（新增经验）/ skipped（重复跳过）/
      source（LLM / rule）/ items（新增经验预览）。
    """
    if limit < 1 or limit > 200:
        limit = 20
    all_tasks = team.load_tasks()
    tasks = [t for t in all_tasks[-limit:] if t.get("status") in DONE_STATUSES]
    if not tasks:
        return {
            "reflected": 0, "added": 0, "skipped": 0,
            "source": "none", "items": [], "message": "暂无已完成 / 失败的任务可反思",
        }

    source = "llm"
    items = _llm_reflect(tasks) if _llm_ready() else None
    if items is None:
        source = "rule"
        items = _rule_reflect(tasks)

    added = 0
    skipped = 0
    new_lessons: list[dict] = []
    for it in items:
        r = lessons.add_lesson(
            trigger=it.get("trigger", ""),
            advice=it.get("advice", ""),
            task_ref=it.get("task_ref", ""),
            confidence=it.get("confidence", 0.5),
        )
        if r.get("duplicate"):
            skipped += 1
            continue
        if r.get("lesson"):
            added += 1
            new_lessons.append(r["lesson"])
            _sync_to_episodic(r["lesson"])

    return {
        "reflected": len(tasks),
        "added": added,
        "skipped": skipped,
        "source": source,
        "items": new_lessons,
        "message": f"反思 {len(tasks)} 条任务（{source} 模式），新增经验 {added} 条，跳过重复 {skipped} 条",
    }
