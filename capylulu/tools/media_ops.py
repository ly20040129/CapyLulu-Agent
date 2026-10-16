"""媒体工具（批次8）：系统音量读写（winmm waveOut）与显示器亮度调节（WMI）。

音量实现基于 ctypes winmm.waveOutSetVolume / waveOutGetVolume（标准 API，无重型依赖），
作用于系统 wave/主输出音量通道；亮度实现基于 WMI WmiMonitorBrightness，
显示器不支持 DDC/CI 或 WMI 不可用时会返回明确说明。
"""
from __future__ import annotations

import ctypes
import subprocess

from .registry import tool

winmm = ctypes.windll.winmm

_POWERSHELL = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]


def _run_ps(script: str) -> str:
    try:
        r = subprocess.run(_POWERSHELL + [script], capture_output=True, text=True, timeout=60)
        out = (r.stdout or "").strip()
        if r.returncode != 0 and not out:
            return f"执行失败：{(r.stderr or '').strip()}"
        return out
    except subprocess.TimeoutExpired:
        return "执行超时"
    except Exception as exc:  # noqa: BLE001
        return f"执行异常：{exc}"


def _pack_volume(percent: int) -> int:
    """0-100 → waveOut 左右声道音量字（低 16 位左声道、高 16 位右声道）。"""
    pct = max(0, min(100, int(percent)))
    word = int(0xFFFF * pct / 100)
    return (word << 16) | word


def _unpack_volume(packed: int) -> int:
    word = packed & 0xFFFF
    return round(word * 100 / 0xFFFF)


@tool(
    name="volume_set",
    description="设置系统音量（0-100），作用于系统主输出音量通道（waveOut）",
    parameters={
        "type": "object",
        "properties": {
            "volume": {"type": "integer", "description": "目标音量 0-100"},
        },
        "required": ["volume"],
    },
    risk="medium",
)
def volume_set(volume: int) -> str:
    packed = _pack_volume(volume)
    result = winmm.waveOutSetVolume(0, packed)
    if result != 0:
        return f"设置音量失败（winmm 错误码 {result}）"
    return f"音量已设置为 {max(0, min(100, int(volume)))}%"


@tool(
    name="volume_get",
    description="获取当前系统音量（0-100）",
    parameters={"type": "object", "properties": {}, "required": []},
    risk="low",
)
def volume_get() -> str:
    packed = ctypes.c_ulong(0)
    result = winmm.waveOutGetVolume(0, ctypes.byref(packed))
    if result != 0:
        return f"获取音量失败（winmm 错误码 {result}）"
    return f"当前系统音量：{_unpack_volume(packed.value)}%"


@tool(
    name="brightness_set",
    description="设置显示器亮度（0-100），基于 WMI；显示器不支持时返回说明",
    parameters={
        "type": "object",
        "properties": {
            "brightness": {"type": "integer", "description": "目标亮度 0-100"},
        },
        "required": ["brightness"],
    },
    risk="medium",
)
def brightness_set(brightness: int) -> str:
    val = max(0, min(100, int(brightness)))
    script = (
        "$m = Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness "
        "-ErrorAction SilentlyContinue; "
        "if (-not $m) { 'no_support'; exit }; "
        "if ($m.CurrentBrightness -eq " + str(val) + ") { 'same'; exit }; "
        "try { "
        "$method = Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods "
        "-ErrorAction Stop; "
        "$method.WmiSetBrightness(1, " + str(val) + "); 'ok' "
        "} catch { 'failed: ' + $_.Exception.Message }"
    )
    out = _run_ps(script).strip()
    if out == "no_support":
        return "显示器不支持亮度调节（WMI WmiMonitorBrightness 不可用，可能为台式机/外接显示器）"
    if out == "same":
        return f"亮度已是 {val}%"
    if out == "ok":
        return f"亮度已设置为 {val}%"
    return f"亮度设置失败：{out}"
