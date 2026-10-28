"""天气查询工具：weather_now（注册进主 registry）。

数据源：wttr.in 免费天气 API（无需 Key）。
- 城市参数支持「贵阳 / 贵州 / 广东省 / Guiyang」等中文或拼音；
- 省份名自动映射到省会城市，保证查询命中；
- 优先取 JSON 详细数据（温度/体感/天气/湿度/风），失败降级为一行摘要；
- 全程只读、无副作用，风险等级 low。
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

from .registry import tool

# 省级 → 省会映射（用户说省份时查省会天气）
_PROVINCE_CAPITAL = {
    "北京": "北京", "天津": "天津", "上海": "上海", "重庆": "重庆",
    "河北": "石家庄", "山西": "太原", "辽宁": "沈阳", "吉林": "长春",
    "黑龙江": "哈尔滨", "江苏": "南京", "浙江": "杭州", "安徽": "合肥",
    "福建": "福州", "江西": "南昌", "山东": "济南", "河南": "郑州",
    "湖北": "武汉", "湖南": "长沙", "广东": "广州", "广西": "南宁",
    "海南": "海口", "四川": "成都", "贵州": "贵阳", "云南": "昆明",
    "西藏": "拉萨", "陕西": "西安", "甘肃": "兰州", "青海": "西宁",
    "宁夏": "银川", "新疆": "乌鲁木齐", "内蒙古": "呼和浩特", "台湾": "台北",
    "香港": "香港", "澳门": "澳门",
}

_TIMEOUT = 15  # 秒


def _fetch(url: str) -> str:
    """抓取 URL 文本，超时或失败抛异常。"""
    req = urllib.request.Request(url, headers={"User-Agent": "capylulu-weather/1.0"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _normalize_city(city: str) -> str:
    """清洗城市名：去掉「市/省/自治区」等后缀，省份映射到省会。"""
    city = (city or "").strip()
    if not city:
        return ""
    # 去掉常见行政后缀
    for suffix in ("市", "省", "自治区", "特别行政区", "壮族", "回族", "维吾尔"):
        if city.endswith(suffix):
            city = city[: -len(suffix)]
            break
    if not city:
        return ""
    # 省份（或省名去掉后缀后）映射省会
    if city in _PROVINCE_CAPITAL:
        return _PROVINCE_CAPITAL[city]
    return city


def _parse_json_detail(city: str, raw: str) -> str | None:
    """解析 wttr.in JSON（format=j1），返回可读天气摘要。"""
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return None
    cond = (data.get("current_condition") or [{}])[0]
    if not cond:
        return None
    desc_list = cond.get("weatherDesc") or [{}]
    desc = (desc_list[0].get("value") if desc_list else "") or ""
    temp = cond.get("temp_C", "")
    feels = cond.get("FeelsLikeC", "")
    humid = cond.get("humidity", "")
    wind = cond.get("windspeedKmph", "")
    wind_dir = cond.get("winddir16Point", "")
    obs = cond.get("observation_time", "")
    parts = [f"{city}当前天气"]
    if desc:
        parts.append(f"天气 {desc}")
    if temp:
        parts.append(f"气温 {temp}°C")
    if feels:
        parts.append(f"体感 {feels}°C")
    if humid:
        parts.append(f"湿度 {humid}%")
    if wind:
        parts.append(f"风速 {wind}km/h{(' ' + wind_dir) if wind_dir else ''}")
    if obs:
        parts.append(f"观测时间 {obs} UTC")
    return "，".join(parts)


def _parse_line_summary(city: str, raw: str) -> str:
    """降级解析 wttr.in 一行摘要（format=3）。"""
    line = raw.strip()
    if line:
        return f"{city}当前天气：{line}"
    return f"（{city} 天气查询无返回数据）"


@tool(
    name="weather_now",
    description=(
        "查询指定城市/地区当前的天气与温度（实时天气、体感温度、湿度、风速等）。"
        "支持中文城市名（如：贵阳、广州）或省份名（如：贵州、广东，自动查询省会）。"
        "用户询问天气、温度、气温、下雨、冷热等问题时直接调用本工具，"
        "不要打开浏览器或编造数据。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "城市或省份名，如：贵阳 / 贵州 / 北京 / 广州",
            },
        },
        "required": ["city"],
    },
    risk="low",
)
def weather_now(city: str = "") -> str:
    """查询指定城市当前天气与温度（wttr.in 免费 API）。"""
    city = (city or "").strip()
    if not city:
        return "参数缺失（失败）：请提供要查询的城市或省份名（如：贵阳、贵州、北京）。"
    target = _normalize_city(city)
    if not target:
        return f"无法识别的城市名：{city}"

    encoded = urllib.parse.quote(target)
    # 优先详细 JSON（中文描述）
    url_json = f"https://wttr.in/{encoded}?format=j1&lang=zh"
    try:
        detail = _parse_json_detail(target, _fetch(url_json))
        if detail:
            return detail
    except Exception:  # noqa: BLE001
        pass
    # 降级：一行摘要
    url_line = f"https://wttr.in/{encoded}?format=3&lang=zh"
    try:
        return _parse_line_summary(target, _fetch(url_line))
    except Exception as exc:  # noqa: BLE001
        return f"天气查询失败：{exc}（请检查网络后重试，或换用浏览器打开天气网站）"
