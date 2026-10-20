"""桌面 GUI 操作工具（批次10）：pyautogui + win32gui + uiautomation。

覆盖：鼠标点击/滚轮、键入任意文本、按标题聚焦窗口、按控件名称点击 UI 元素。
让「打开桌面应用后继续做事情」成为可能（例如打开计算器后点击按钮、在记事本输入内容）。
"""
from __future__ import annotations

import time

from .registry import tool


@tool(
    name="mouse_click",
    description="按屏幕坐标点击鼠标（可指定左/右键、次数、双击与移动耗时）",
    parameters={
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "屏幕横坐标（像素）"},
            "y": {"type": "integer", "description": "屏幕纵坐标（像素）"},
            "button": {"type": "string", "description": "'left'（默认）/'right'/'middle'"},
            "clicks": {"type": "integer", "description": "点击次数，默认1"},
            "interval": {"type": "number", "description": "两次点击间隔秒，默认0.2"},
        },
        "required": ["x", "y"],
    },
    risk="medium",
)
def mouse_click(x: int, y: int, button: str = "left", clicks: int = 1, interval: float = 0.2) -> str:
    try:
        import pyautogui
        pyautogui.FAILSAFE = True
        clicks = max(1, int(clicks or 1))
        pyautogui.click(x=int(x), y=int(y), button=button, clicks=clicks, interval=max(0.05, float(interval or 0.2)))
        return f"已在 ({x},{y}) 点击 {button} 键 {clicks} 次"
    except Exception as exc:  # noqa: BLE001
        return f"鼠标点击失败：{exc}"


@tool(
    name="mouse_scroll",
    description="滚动鼠标滚轮（正数向上、负数向下）",
    parameters={
        "type": "object",
        "properties": {
            "clicks": {"type": "integer", "description": "滚动格数，正上负下，如 -5"},
        },
        "required": ["clicks"],
    },
    risk="medium",
)
def mouse_scroll(clicks: int = -3) -> str:
    try:
        import pyautogui
        pyautogui.scroll(int(clicks))
        return f"已滚动 {clicks} 格"
    except Exception as exc:  # noqa: BLE001
        return f"滚动失败：{exc}"


@tool(
    name="type_text",
    description="在当前焦点窗口键入文本（模拟键盘输入；enter=True 时末尾回车提交）",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要键入的文本"},
            "interval": {"type": "number", "description": "每字符间隔秒，默认0.05"},
            "enter": {"type": "boolean", "description": "是否末尾回车，默认false"},
        },
        "required": ["text"],
    },
    risk="medium",
)
def type_text(text: str, interval: float = 0.05, enter: bool = False) -> str:
    try:
        import pyautogui
        if not text:
            return "请输入要键入的文本"
        pyautogui.write(str(text), interval=max(0.01, float(interval or 0.05)))
        if enter:
            pyautogui.press("enter")
        return f"已键入 {len(text)} 个字符{'（含回车）' if enter else ''}"
    except Exception as exc:  # noqa: BLE001
        return f"键入失败：{exc}"


@tool(
    name="window_focus",
    description="按标题关键字查找窗口并置为前台（用于把目标应用切到最前再操作）",
    parameters={
        "type": "object",
        "properties": {
            "title_substr": {"type": "string", "description": "窗口标题包含的关键字，如 '记事本'、'Excel'"},
        },
        "required": ["title_substr"],
    },
    risk="medium",
)
def window_focus(title_substr: str) -> str:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    found = []

    def _enum(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if (title_substr or "").lower() in buf.value.lower():
            found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(_enum, 0)
    if not found:
        return f"未找到标题包含「{title_substr}」的窗口"
    hwnd, title = found[0]
    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.3)
        return f"已聚焦窗口：{title}（共找到 {len(found)} 个匹配）"
    except Exception as exc:  # noqa: BLE001
        return f"聚焦失败：{exc}"


@tool(
    name="ui_click",
    description="按控件名称点击应用内按钮/菜单项（基于 UIAutomation，适合标准 Windows 应用，如记事本菜单、计算器按钮）",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "控件名称，如 '确定'、'文件'、'7'"},
            "control_type": {"type": "string", "description": "控件类型，默认 Button；可用 'MenuItem'、'TabItem'、'Edit' 等"},
        },
        "required": ["text"],
    },
    risk="medium",
)
def ui_click(text: str, control_type: str = "Button") -> str:
    try:
        import uiautomation as auto
    except Exception as exc:  # noqa: BLE001
        return f"未安装 uiautomation 依赖：{exc}"
    try:
        ctrl = auto.Control(searchDepth=1, Name=str(text), ControlType=control_type)
        if not ctrl.Exists(1.5):
            return f"未找到名为「{text}」的 {control_type} 控件"
        ctrl.Click(simulateMove=False)
        return f"已点击控件：{text} ({control_type})"
    except Exception as exc:  # noqa: BLE001
        return f"UI 点击失败：{exc}"
