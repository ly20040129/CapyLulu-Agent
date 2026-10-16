"""屏幕与键鼠工具（批次8）：截图（全屏/活动窗口）与安全按键组合模拟。

screenshot 基于 PowerShell System.Windows.Forms/Drawing 的 CopyFromScreen，
保存到 data/screenshots/ 并返回路径；key_simulate 基于 user32.keybd_event
（C# Add-Type 封装），仅支持安全组合白名单，HIGH 风险需用户确认后经 UI 通道执行。
"""
from __future__ import annotations

import ctypes
import datetime
import os
import subprocess
from ctypes import wintypes

from ..config import config
from .registry import tool

user32 = ctypes.windll.user32

_POWERSHELL = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]

# 安全按键组合白名单：组合名 -> [VK 序列]（修饰键在前，按下顺序，释放逆序）
KEY_COMBOS: dict[str, list[int]] = {
    "win+d": [0x5B, 0x44],      # 显示桌面
    "win+e": [0x5B, 0x45],      # 打开资源管理器
    "win+l": [0x5B, 0x4C],      # 锁屏
    "ctrl+c": [0x11, 0x43],     # 复制
    "ctrl+v": [0x11, 0x56],     # 粘贴
    "ctrl+x": [0x11, 0x58],     # 剪切
    "ctrl+a": [0x11, 0x41],     # 全选
    "ctrl+z": [0x11, 0x5A],     # 撤销
    "ctrl+y": [0x11, 0x59],     # 重做
    "alt+tab": [0x12, 0x09],    # 切换窗口
    "alt+f4": [0x12, 0x73],     # 关闭当前窗口
    "enter": [0x0D],            # 回车
    "esc": [0x1B],              # 取消
    "f5": [0x74],               # 刷新
}

_ADD_TYPE_SNIPPET = r"""
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class KeySim {
    [DllImport(""user32.dll"")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    public static void Combo(int[] vks) {
        foreach (int vk in vks) keybd_event((byte)vk, 0, 0, UIntPtr.Zero);
        for (int i = vks.Length - 1; i >= 0; i--) keybd_event((byte)vks[i], 0, 2, UIntPtr.Zero);
    }
}
"@
"""


def _run_ps(script: str) -> str:
    try:
        r = subprocess.run(_POWERSHELL + [script], capture_output=True, text=True, timeout=90)
        out = (r.stdout or "").strip()
        if r.returncode != 0 and not out:
            return f"执行失败：{(r.stderr or '').strip()}"
        return out
    except subprocess.TimeoutExpired:
        return "执行超时"
    except Exception as exc:  # noqa: BLE001
        return f"执行异常：{exc}"


def _screenshots_dir() -> str:
    d = os.path.join(config.data_dir, "screenshots")
    os.makedirs(d, exist_ok=True)
    return d


@tool(
    name="screenshot",
    description="截取全屏或活动窗口，保存到 data/screenshots/ 并返回文件路径",
    parameters={
        "type": "object",
        "properties": {
            "mode": {"type": "string", "description": "'full'=全屏（默认），'window'=当前活动窗口"},
        },
        "required": [],
    },
    risk="medium",
)
def screenshot(mode: str = "full") -> str:
    now = datetime.datetime.now()
    fname = f"screenshot_{now.year}{now.month:02d}{now.day:02d}_{now.hour:02d}{now.minute:02d}{now.second:02d}.png"
    save_path = os.path.join(_screenshots_dir(), fname)

    if mode == "window":
        hwnd = user32.GetForegroundWindow()
        rect = wintypes.RECT()
        if hwnd and user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            x, y = rect.left, rect.top
            w = max(1, rect.right - rect.left)
            h = max(1, rect.bottom - rect.top)
            script = (
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
                "$bmp = New-Object System.Drawing.Bitmap(" + str(w) + "," + str(h) + "); "
                "$g = [System.Drawing.Graphics]::FromImage($bmp); "
                "$g.CopyFromScreen(" + str(x) + "," + str(y) + ",0,0,$bmp.Size); "
                f"$bmp.Save('{save_path}',[System.Drawing.Imaging.ImageFormat]::Png); "
                "$g.Dispose(); $bmp.Dispose(); 'ok'"
            )
            out = _run_ps(script).strip()
            if out == "ok":
                return f"已截取活动窗口，保存到：{save_path}"
            return f"截图失败：{out}"
        return "无法获取活动窗口"
    # 全屏（虚拟桌面，覆盖多显示器）
    script = (
        "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
        "$b = [System.Windows.Forms.SystemInformation]::VirtualScreen; "
        "$bmp = New-Object System.Drawing.Bitmap($b.Width,$b.Height); "
        "$g = [System.Drawing.Graphics]::FromImage($bmp); "
        "$g.CopyFromScreen($b.Left,$b.Top,0,0,$bmp.Size); "
        f"$bmp.Save('{save_path}',[System.Drawing.Imaging.ImageFormat]::Png); "
        "$g.Dispose(); $bmp.Dispose(); 'ok'"
    )
    out = _run_ps(script).strip()
    if out == "ok":
        return f"已截取全屏，保存到：{save_path}"
    return f"截图失败：{out}"


@tool(
    name="key_simulate",
    description="模拟安全按键组合（仅支持白名单：win+d/e/l、ctrl+c/v/x/a/z/y、alt+tab、alt+f4、enter、esc、f5）",
    parameters={
        "type": "object",
        "properties": {
            "combo": {"type": "string", "description": "组合名，如 'win+d'、'ctrl+c'、'alt+tab'"},
        },
        "required": ["combo"],
    },
    risk="high",
)
def key_simulate(combo: str) -> str:
    key = (combo or "").strip().lower()
    vks = KEY_COMBOS.get(key)
    if not vks:
        allowed = "、".join(sorted(KEY_COMBOS.keys()))
        return f"组合「{key}」不在安全白名单内，仅支持：{allowed}"
    vk_list = ",".join(str(v) for v in vks)
    script = (
        _ADD_TYPE_SNIPPET +
        f"[KeySim]::Combo([int[]]@({vk_list})); 'ok'"
    )
    out = _run_ps(script).strip()
    if out == "ok":
        return f"已模拟按键组合：{key}"
    return f"按键模拟失败：{out}"
