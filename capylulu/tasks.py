"""自动任务：清单 + 调度字段（存储路径由 config.data_dir 决定，默认 data/tasks.json）。

任务条目字段：
    text     任务原文
    created  创建时间
    kind     daily / weekly / once / manual
    weekday  每周几（0=周一 .. 6=周日，仅 weekly 有效）
    time     "HH:MM" 触发时刻
    next     "YYYY-MM-DD HH:MM" 下次触发时间（由 scheduler 推进）
    enabled  是否启用
    action   remind / note / both

执行记录存 task_logs.json；便签写入 <data_dir>/notes/。
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from .config import config

WEEKDAY_NAMES = {
    "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5,
    "日": 6, "天": 6, "1": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5, "7": 6,
}
WEEKDAY_DISPLAY = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

TIME_COLON_RE = re.compile(r"(?P<hour>\d{1,2})\s*[:：]\s*(?P<min>\d{1,2})")
TIME_CN_RE = re.compile(r"(?P<hour>\d{1,2})\s*点(?P<half>半)?")
WEEKLY_RE = re.compile(r"每周(?:星期|周)?([一二三四五六日天1-7])")
DAILY_RE = re.compile(r"每天|每日")
TODAY_RE = re.compile(r"今天")
TOMORROW_RE = re.compile(r"明天")
REMIND_RE = re.compile(r"提醒|通知|叫我|喊我")
NOTE_RE = re.compile(r"便签|备注|备忘|记下|记录")


def _data_dir() -> Path:
    return config.data_dir


STORE = _data_dir() / "tasks.json"          # 任务清单文件
LOG_STORE = _data_dir() / "task_logs.json"  # 任务执行记录文件
NOTES_DIR = _data_dir() / "notes"           # 便签目录


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global STORE, LOG_STORE, NOTES_DIR
    STORE = _data_dir() / "tasks.json"
    LOG_STORE = _data_dir() / "task_logs.json"
    NOTES_DIR = _data_dir() / "notes"


# ---- 解析任务文本 ----

def parse_task(text: str) -> dict | None:
    """解析任务文本 → 调度字段；无法识别触发时刻时返回 None（视为普通清单）。

    兼容 "每天18:40提醒我下班" / "每天 18:40 生成便签" / "每周五 17:00 ..." /
    "今天 9:30 提醒" / 全角冒号 "18：40" 等格式。
    """
    text = (text or "").strip()
    m = TIME_COLON_RE.search(text)
    if not m:
        m = TIME_CN_RE.search(text)
        if not m:
            return None
        hour, minute = int(m.group("hour")), 30 if m.group("half") else 0
    else:
        hour, minute = int(m.group("hour")), int(m.group("min"))
    if hour > 23 or minute > 59:
        return None
    wm = WEEKLY_RE.search(text)
    if wm:
        kind, weekday = "weekly", WEEKDAY_NAMES[wm.group(1)]
    elif DAILY_RE.search(text):
        kind, weekday = "daily", None
    elif TODAY_RE.search(text) or TOMORROW_RE.search(text):
        kind, weekday = "once", None
    else:
        # 无前缀默认每天（长期提醒最符合直觉）
        kind, weekday = "daily", None
    has_remind = bool(REMIND_RE.search(text))
    has_note = bool(NOTE_RE.search(text))
    action = "both" if has_remind and has_note else ("remind" if has_remind else ("note" if has_note else "both"))
    return {
        "kind": kind,
        "weekday": weekday,
        "time": f"{hour:02d}:{minute:02d}",
        "action": action,
    }


def next_trigger(item: dict, now: datetime | None = None) -> datetime | None:
    """计算任务的下次触发时刻；一次性任务已过时间返回 None。"""
    now = now or datetime.now()
    kind = item.get("kind")
    t = item.get("time") or ""
    if not t or ":" not in t:
        return None
    try:
        hh, mm = (int(x) for x in t.split(":"))
    except ValueError:
        return None
    base = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if kind == "once":
        # 一次性：今天/明天前缀
        if TODAY_RE.search(item.get("text") or ""):
            return base if base > now else None
        if TOMORROW_RE.search(item.get("text") or ""):
            base += timedelta(days=1)
            return base
        return base if base > now else None
    if kind == "daily":
        return base if base > now else base + timedelta(days=1)
    if kind == "weekly":
        wd = item.get("weekday")
        if wd is None:
            return None
        delta = (int(wd) - base.weekday()) % 7
        nxt = base + timedelta(days=delta)
        return nxt if nxt > now else nxt + timedelta(days=7)
    return None


def _describe(item: dict) -> str:
    kind = item.get("kind")
    t = item.get("time") or ""
    if kind == "weekly":
        wd = item.get("weekday")
        return f"每周{WEEKDAY_DISPLAY[wd] if wd is not None else '?'} {t}"
    if kind == "once":
        return f"一次性 {t}"
    if kind == "daily":
        return f"每天 {t}"
    return "仅清单（未识别到时间）"


# ---- 任务清单 ----

def load() -> list[dict]:
    if not STORE.exists():
        return []
    try:
        return json.loads(STORE.read_text(encoding="utf-8")) or []
    except json.JSONDecodeError:
        logger.warning(f"[Tasks] 任务文件损坏，返回空清单：{STORE}")
        return []


def save(items: list[dict]) -> None:
    """写回任务清单文件。"""
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"[Tasks] 已保存任务清单：{len(items)} 条 -> {STORE}")


def add(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return _fmt()
    items = load()
    item = {
        "text": text,
        "created": time.strftime("%Y-%m-%d %H:%M"),
        "kind": "manual",
        "weekday": None,
        "time": "",
        "action": "both",
        "next": "",
        "enabled": True,
    }
    parsed = parse_task(text)
    if parsed:
        item.update(parsed)
        nxt = next_trigger(item)
        item["next"] = nxt.strftime("%Y-%m-%d %H:%M") if nxt else ""
    items.insert(0, item)
    save(items)
    return _fmt()


def remove_by_text(text: str) -> str:
    """按任务文本删除（首次匹配）。"""
    text = (text or "").strip()
    if not text:
        return _fmt()
    items = load()
    for i, item in enumerate(items):
        if item.get("text") == text:
            items.pop(i)
            save(items)
            break
    return _fmt()


def update_by_text(old_text: str, new_text: str) -> str:
    """按原文本更新任务（首次匹配）：重新解析新文本的调度字段，保留 enabled/created。"""
    old_text = (old_text or "").strip()
    new_text = (new_text or "").strip()
    if not old_text or not new_text:
        return _fmt()
    items = load()
    for item in items:
        if item.get("text") == old_text:
            item["text"] = new_text
            parsed = parse_task(new_text)
            if parsed:
                item.update(parsed)
                nxt = next_trigger(item)
                item["next"] = nxt.strftime("%Y-%m-%d %H:%M") if nxt else ""
            else:
                item["kind"] = "manual"
                item["weekday"] = None
                item["time"] = ""
                item["next"] = ""
            save(items)
            logger.info(f"[Tasks] 已更新任务：{old_text} -> {new_text}")
            break
    return _fmt()


def set_enabled(text: str, enabled: bool) -> str:
    """切换任务启停（按文本匹配，首次命中）。"""
    text = (text or "").strip()
    if not text:
        return _fmt()
    items = load()
    for item in items:
        if item.get("text") == text:
            item["enabled"] = bool(enabled)
            if enabled:
                nxt = next_trigger(item)
                item["next"] = nxt.strftime("%Y-%m-%d %H:%M") if nxt else ""
            save(items)
            break
    return _fmt()


def choices() -> list[str]:
    """任务文本列表（下拉选择用）。"""
    return [i.get("text", "") for i in load()]


def is_auto(item: dict) -> bool:
    """自动任务判定：含 module+func 的脚本任务、steps 多步脚本任务、或 mode=agentic+goal 的智能体任务均属自动任务；旧 text 便签走旧逻辑。"""
    if not item:
        return False
    if item.get("module") and item.get("func"):
        return True
    if isinstance(item.get("steps"), list) and item.get("steps"):
        return True
    return bool(item.get("mode") == "agentic" and (item.get("goal") or "").strip())


def rows() -> list[list]:
    """任务页 Dataframe：任务 / 类型 / 下次触发 / 状态；自动任务展示 name/cron/next/enabled。"""
    rows_out = []
    for i in load():
        if is_auto(i):
            rows_out.append([
                i.get("name", ""),
                i.get("cron", ""),
                (i.get("next") or "—"),
                "✅ 启用" if i.get("enabled", True) else "⛔ 停用",
            ])
        else:
            rows_out.append([
                i.get("text", ""),
                _describe(i),
                (i.get("next") or "—"),
                "✅ 启用" if i.get("enabled", True) else "⛔ 停用",
            ])
    return rows_out


def _fmt() -> str:
    items = load()
    if not items:
        return "还没有自动任务。写一句要噜噜记住的事，点添加。"
    lines = []
    for i in items:
        flag = "" if i.get("enabled", True) else "（停用）"
        nxt = i.get("next") or "未排期"
        lines.append(f"- [{i['created']}] {i['text']} · {_describe(i)} · 下次 {nxt}{flag}")
    return "\n".join(lines)


# ---- 执行记录 ----

def load_logs() -> list[dict]:
    if not LOG_STORE.exists():
        return []
    try:
        return json.loads(LOG_STORE.read_text(encoding="utf-8")) or []
    except json.JSONDecodeError:
        logger.warning(f"[Tasks] 执行记录文件损坏，返回空记录：{LOG_STORE}")
        return []


def save_logs(logs: list[dict]) -> None:
    LOG_STORE.parent.mkdir(parents=True, exist_ok=True)
    LOG_STORE.write_text(json.dumps(logs, ensure_ascii=False, indent=2), encoding="utf-8")


def log_event(text: str, result: str = "") -> str:
    """手动记录一次任务执行（触发时间 / 任务 / 结果）。"""
    return log_event_raw(text, time.strftime("%Y-%m-%d %H:%M:%S"), result)


def log_event_raw(text: str, ts: str, result: str = "", note: str = "") -> str:
    """写一条执行记录（调度器 / 手动通用），返回格式化执行记录文本。"""
    text = (text or "").strip()
    if not text:
        return _fmt_logs()
    logs = load_logs()
    entry = {
        "text": text,
        "time": ts or time.strftime("%Y-%m-%d %H:%M:%S"),
        "result": (result or "").strip(),
    }
    if note:
        entry["note"] = str(note)
    logs.insert(0, entry)
    save_logs(logs[:200])  # 最多留 200 条
    logger.info(f"[Tasks] 已记录执行：{text}")
    return _fmt_logs()


def _fmt_logs() -> str:
    logs = load_logs()
    if not logs:
        return "还没有执行记录。选一条任务点「记录一次执行」试试。"
    return "\n".join(
        f"- [{x['time']}] {x['text']}" + (f" → {x['result']}" if x.get("result") else "") for x in logs
    )
