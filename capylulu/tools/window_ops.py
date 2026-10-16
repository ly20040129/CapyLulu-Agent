"""窗口管理工具（批次8）：枚举 / 激活 / 最小化 / 最大化 / 还原 / 关闭窗口。

基于 ctypes user32 标准 API（EnumWindows / ShowWindow / PostMessage），
不引入 psutil 等重型依赖；进程名用 OpenProcess + QueryFullProcessImageNameW 获取。
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes

from .registry import tool

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

WM_CLOSE = 0x0010
SW_MINIMIZE = 6
SW_MAXIMIZE = 3
SW_RESTORE = 9
SW_SHOW = 5
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _pid_to_exe(pid: int) -> str:
    """PID → 可执行文件名（QueryFullProcessImageNameW），失败返回 '未知'。"""
    if pid <= 0:
        return "未知"
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return "未知"
    try:
        buf = ctypes.create_unicode_buffer(4096)
        size = wintypes.DWORD(4096)
        ok = kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
        if ok:
            return buf.value.rsplit("\\", 1)[-1]
        return "未知"
    finally:
        kernel32.CloseHandle(h)


def _enum_visible_windows() -> list[dict]:
    """枚举所有可见、带标题的顶层窗口。"""
    results: list[dict] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, lparam):  # noqa: ARG001
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if not title:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        results.append({
            "hwnd": int(hwnd),
            "pid": int(pid.value),
            "title": title,
            "exe": _pid_to_exe(int(pid.value)),
        })
        return True

    user32.EnumWindows(_cb, 0)
    return results


def _find_windows(keyword: str) -> list[dict]:
    """按标题关键字（不区分大小写）匹配窗口；空关键字返回全部。"""
    kw = (keyword or "").strip().lower()
    wins = _enum_visible_windows()
    if not kw:
        return wins
    return [w for w in wins if kw in w["title"].lower()]


def _show_for_hwnd(hwnd: int, mode: int) -> str:
    user32.ShowWindow(hwnd, mode)
    return "ok"


@tool(
    name="window_list",
    description="列出当前可见窗口（标题 / 进程名 / PID / 窗口句柄），可按标题关键字过滤",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "标题关键字过滤，留空列出全部（最多 80 个）"},
        },
        "required": [],
    },
    risk="low",
)
def window_list(keyword: str = "") -> str:
    wins = _find_windows(keyword)[:80]
    if not wins:
        return "没有找到可见窗口。" if keyword else "当前没有可见窗口。"
    lines = [f"共 {len(wins)} 个窗口：" if not keyword else f"匹配「{keyword}」的窗口共 {len(wins)} 个："]
    for w in wins:
        lines.append(f"- [{w['hwnd']}] {w['exe']}(PID {w['pid']})：{w['title']}")
    return "\n".join(lines)


@tool(
    name="window_activate",
    description="按标题或关键字将窗口激活置前（会先还原最小化窗口）",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "窗口标题关键字（如 '记事本' / 'Chrome'）"},
        },
        "required": ["keyword"],
    },
    risk="medium",
)
def window_activate(keyword: str) -> str:
    wins = _find_windows(keyword)
    if not wins:
        return f"未找到标题包含「{keyword}」的窗口"
    hwnd = wins[0]["hwnd"]
    if not user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    # 前置需要前台权限：先模拟一次 Alt 按键，再 SetForegroundWindow
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(hwnd)
    return f"已激活窗口：{wins[0]['title']}"


@tool(
    name="window_minimize",
    description="按标题或关键字最小化窗口",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "窗口标题关键字"},
        },
        "required": ["keyword"],
    },
    risk="medium",
)
def window_minimize(keyword: str) -> str:
    wins = _find_windows(keyword)
    if not wins:
        return f"未找到标题包含「{keyword}」的窗口"
    _show_for_hwnd(wins[0]["hwnd"], SW_MINIMIZE)
    return f"已最小化窗口：{wins[0]['title']}"


@tool(
    name="window_maximize",
    description="按标题或关键字最大化窗口",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "窗口标题关键字"},
        },
        "required": ["keyword"],
    },
    risk="medium",
)
def window_maximize(keyword: str) -> str:
    wins = _find_windows(keyword)
    if not wins:
        return f"未找到标题包含「{keyword}」的窗口"
    _show_for_hwnd(wins[0]["hwnd"], SW_MAXIMIZE)
    return f"已最大化窗口：{wins[0]['title']}"


@tool(
    name="window_restore",
    description="按标题或关键字还原（取消最小化/最大化）窗口",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "窗口标题关键字"},
        },
        "required": ["keyword"],
    },
    risk="medium",
)
def window_restore(keyword: str) -> str:
    wins = _find_windows(keyword)
    if not wins:
        return f"未找到标题包含「{keyword}」的窗口"
    _show_for_hwnd(wins[0]["hwnd"], SW_RESTORE)
    return f"已还原窗口：{wins[0]['title']}"


@tool(
    name="window_close",
    description="按标题或关键字关闭窗口（发送 WM_CLOSE，可能触发未保存提示）",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "窗口标题关键字"},
        },
        "required": ["keyword"],
    },
    risk="high",
)
def window_close(keyword: str) -> str:
    wins = _find_windows(keyword)
    if not wins:
        return f"未找到标题包含「{keyword}」的窗口"
    hwnd = wins[0]["hwnd"]
    user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    return f"已向窗口发送关闭请求：{wins[0]['title']}"
