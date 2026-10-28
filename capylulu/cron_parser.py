"""cron 表达式解析器：五字段（分 时 日 月 周），无第三方依赖。

每字段支持：* | 数字 | a-b 区间 | a,b 列表 | */n 步长。
纯函数、无 IO、无全局状态；非法表达式抛 ValueError。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from loguru import logger

_STEP_RE = re.compile(r"^\*/(\d+)$")
_RANGE_RE = re.compile(r"^(\d+)(?:-(\d+))?(?:/(\d+))?$")


def _parse_field(text: str, lo: int, hi: int) -> set[int]:
    """解析单个 cron 字段为允许值集合；* 即全范围，非法格式抛 ValueError。"""
    text = (text or "").strip()
    if not text:
        raise ValueError("cron 字段不能为空")
    values: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if part == "*":
            values.update(range(lo, hi + 1))
            continue
        m = _STEP_RE.match(part)
        if m:
            n = int(m.group(1))
            if n < 1:
                raise ValueError(f"步长必须 >= 1：{part}")
            values.update(range(lo, hi + 1, n))
            continue
        m = _RANGE_RE.match(part)
        if not m:
            raise ValueError(f"cron 字段格式非法：{part}")
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) is not None else a
        step = int(m.group(3)) if m.group(3) else 1
        if a < lo or b > hi or a > b or step < 1:
            raise ValueError(f"cron 字段越界或区间非法：{part}（允许 {lo}~{hi}）")
        values.update(range(a, b + 1, step))
    if not values:
        raise ValueError(f"cron 字段无有效值：{text}")
    return values


def parse_cron(expr: str) -> dict:
    """解析 "分 时 日 月 周" 五字段，返回 {minute, hour, day, month, dow} 集合。"""
    fields = (expr or "").strip().split()
    if len(fields) != 5:
        raise ValueError(f"cron 必须 5 段，当前 {len(fields)} 段：{expr}")
    minute = _parse_field(fields[0], 0, 59)
    hour = _parse_field(fields[1], 0, 23)
    day = _parse_field(fields[2], 1, 31)
    month = _parse_field(fields[3], 1, 12)
    dow_raw = _parse_field(fields[4], 0, 7)
    # dow 支持 0-6（0=周日），7 归一为 0
    dow = {(0 if v == 7 else v) for v in dow_raw}
    spec = {
        "minute": minute,
        "hour": hour,
        "day": day,
        "month": month,
        "dow": dow,
    }
    logger.debug(f"[Cron] 已解析：{expr}")
    return spec


def _dow_of(dt: datetime) -> int:
    """取 cron 周几（0=周日）：Python weekday 周一=0，转成 cron 表示。"""
    return (dt.weekday() + 1) % 7


def _matches(dt: datetime, spec: dict) -> bool:
    """判断某分钟是否命中 cron 规则；day 与 dow 同时受限时按“或”语义（cron 惯例）。"""
    if dt.minute not in spec["minute"]:
        return False
    if dt.hour not in spec["hour"]:
        return False
    if dt.month not in spec["month"]:
        return False
    day_full = len(spec["day"]) == 31  # 日字段是否全范围
    dow_full = len(spec["dow"]) == 7   # 周字段是否全范围
    if not day_full and not dow_full:
        # 两者都受限：命中其一即可
        if dt.day not in spec["day"] and _dow_of(dt) not in spec["dow"]:
            return False
    elif not day_full:
        if dt.day not in spec["day"]:
            return False
    elif not dow_full:
        if _dow_of(dt) not in spec["dow"]:
            return False
    return True


def next_after(spec: dict, now: datetime) -> datetime | None:
    """基于当前时间计算下一个触发时刻（严格大于 now，分钟精度，秒/微秒归零）。

    在分钟~年的范围内暴力推进；5 年未命中返回 None。
    """
    dt = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = now + timedelta(days=365 * 5)
    while dt <= limit:
        if _matches(dt, spec):
            return dt
        dt += timedelta(minutes=1)
    return None
