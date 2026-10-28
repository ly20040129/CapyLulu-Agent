"""桌面 GUI 操作工具（批次10）：pyautogui + win32gui + uiautomation。

覆盖：鼠标点击/滚轮、键入任意文本、按标题聚焦窗口、按控件名称点击 UI 元素。
让「打开桌面应用后继续做事情」成为可能（例如打开计算器后点击按钮、在记事本输入内容）。
"""
from __future__ import annotations

import json
import re
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
            "title": {"type": "string", "description": "窗口标题包含的关键字（与 title_substr 等价，二选一）"},
            "keyword": {"type": "string", "description": "窗口标题包含的关键字（与 title_substr 等价，二选一）"},
            "process_name": {"type": "string", "description": "进程名关键字（如 DingTalk/WeChat），提供时仅匹配该进程的窗口，避免浏览器标签页误命中"},
        },
        "required": [],
    },
    risk="medium",
)
def window_focus(title_substr: str = "", title: str = "", keyword: str = "", process_name: str = "") -> str:
    # 兼容 LLM 直觉参数名：title/keyword 与 title_substr 等价
    if not title_substr:
        title_substr = title or keyword
    if not title_substr:
        return "请提供窗口标题关键字（title_substr / title / keyword）"
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    found = []

    # 进程名过滤辅助：取窗口所属进程的 exe 文件名
    def _proc_name_of(hwnd):
        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            hproc = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not hproc:
                return ""
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            ok = kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size))
            kernel32.CloseHandle(hproc)
            if not ok:
                return ""
            return buf.value.split("\\")[-1]
        except Exception:  # noqa: BLE001
            return ""
    _proc_kw = (process_name or "").lower()

    # 关键：必须显式声明回调与 API 签名，否则 64 位句柄无法转换（Don't know how to convert parameter 1）
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL

    @WNDENUMPROC
    def _enum(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        visible = bool(user32.IsWindowVisible(hwnd))
        # 提供进程名时：该进程的窗口直接入选（标题仅作后续排序），避免标题随页面变化（如钉钉标题变为"日志"）而失配；
        # 不可见（最小化/托盘隐藏）窗口也收录，选中后统一 SW_RESTORE 恢复，保证前置聚焦成功
        pname = _proc_name_of(hwnd) if _proc_kw else ""
        if _proc_kw and pname and _proc_kw in pname.lower():
            found.append((hwnd, title, visible))
        elif (title_substr or "").lower() in title.lower():
            if _proc_kw and _proc_kw not in pname.lower():
                return True
            found.append((hwnd, title, visible))
        return True

    user32.EnumWindows(_enum, 0)
    # 应用可能仍在启动/加载，窗口未出现：短轮询等待最多约 8 秒
    for _ in range(10):
        if found:
            break
        time.sleep(0.8)
        found.clear()
        user32.EnumWindows(_enum, 0)
    if not found:
        return f"未找到标题包含「{title_substr}」的窗口"
    # 多匹配选择：精确标题 > 短标题前缀 > 面积，且排除浏览器标签页（标题含 Edge/Chrome 等）
    browser_mark = ("edge", "chrome", "firefox", "浏览器", "360", "iexplore")
    def _score(tup):
        hwnd, title, visible = tup
        t = title.strip().lower()
        s = 0
        if t == title_substr.strip().lower():
            s += 200  # 精确匹配
        elif t.startswith(title_substr.strip().lower()):
            s += 100
        if _proc_kw and _proc_kw in (_proc_name_of(hwnd) or "").lower():
            s += 300  # 进程名匹配的窗口优先（钉钉等标题随页面变化，标题匹配不可靠）
        if any(b in t for b in browser_mark):
            s -= 500  # 浏览器标签页不是目标应用主窗口
        s += 800 if visible else -800  # 可见窗口优先；不可见仅作兜底候选（选中后会 SW_RESTORE 恢复）
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        area = max(1, r.right - r.left) * max(1, r.bottom - r.top)
        s += min(area, 4000000) / 100000.0  # 面积兜底（最大约 40 分）
        return s
    target = max(found, key=_score)
    hwnd, title, visible = target
    try:
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.ShowWindow(hwnd, 5)  # SW_SHOW
        # 标准可靠置顶组合：附加输入线程后 SetForegroundWindow + BringWindowToTop
        kernel32 = ctypes.windll.kernel32
        cur_thread = kernel32.GetCurrentThreadId()
        win_thread = user32.GetWindowThreadProcessId(hwnd, None)
        attached = False
        if cur_thread != win_thread:
            user32.AttachThreadInput(cur_thread, win_thread, True)
            attached = True
        try:
            user32.SetForegroundWindow(hwnd)
            user32.BringWindowToTop(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(cur_thread, win_thread, False)
        # 校验前台是否真正切到目标窗口：SetForegroundWindow 受 Windows 前台锁限制，
        # 后台脚本调用常被静默拒绝（返回 False 或未生效）。未生效时用 Alt 键技巧绕过。
        time.sleep(0.25)
        if user32.GetForegroundWindow() != hwnd:
            user32.keybd_event(0x12, 0, 0, 0)  # VK_MENU 按下
            user32.keybd_event(0x12, 0, 2, 0)  # VK_MENU 释放（经典前台锁绕过）
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.25)
        fg_now = user32.GetForegroundWindow()
        if fg_now == hwnd:
            return f"已聚焦窗口：{title}（共找到 {len(found)} 个匹配，选中最大窗口）"
        return f"聚焦未完全生效：目标「{title}」未能置为前台（当前前台 hwnd={fg_now}），请人工确认窗口状态"
    except Exception as exc:  # noqa: BLE001
        return f"聚焦失败：{exc}"


@tool(
    name="ui_click",
    description="按控件名称点击应用内按钮/菜单项（基于 UIAutomation，适合标准 Windows 应用，如记事本菜单、计算器按钮）",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "控件名称，如 '确定'、'文件'、'7'"},
            "name": {"type": "string", "description": "控件名称（与 text 等价，二选一）"},
            "control_type": {"type": "string", "description": "控件类型，默认 Button；可用 'MenuItem'、'TabItem'、'Edit' 等"},
        },
        "required": [],
    },
    risk="medium",
)
def ui_click(text: str = "", name: str = "", control_type: str = "Button") -> str:
    # 兼容 LLM 直觉参数名：name 与 text 等价
    if not text:
        text = name
    if not text:
        return "请提供控件名称（text / name）"
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


# ---- 全流程自动化闭环：UIA 控件树快照（眼）+ 按编号点击（手） ----
# 参考 cowagent 的 DOM 快照模式：把界面可交互元素编号化，LLM 按编号决策。
# 与 uiautomation ControlTypeName 匹配时去掉 "Control" 后缀（如 "ButtonControl" -> "Button"）
_INTERACTIVE_CTRL_TYPES = {
    "Button", "Edit", "MenuItem", "TabItem", "ListItem", "CheckBox",
    "RadioButton", "ComboBox", "Hyperlink", "Slider", "TreeItem",
    "DataItem", "SplitButton", "HeaderItem", "Calendar", "StatusBarItem",
    "Document",
}

# 名称语义点击优先的可交互类型（视觉兜底也按此权重）
_SEMANTIC_CLICK_TYPES = ("Button", "Edit", "MenuItem", "ListItem", "TabItem",
                         "CheckBox", "RadioButton", "ComboBox", "Hyperlink",
                         "TreeItem", "DataItem", "SplitButton", "HeaderItem")


def _find_obs_keyword(kw: str, app: str = "") -> tuple | None:
    """视觉观察当前界面，返回名称含关键词的最优元素 (score, name, ctype, x, y)。

    供 send_chat_message 的视觉兜底链路使用：UIA 拿不到语义的自绘界面
    （钉钉/微信/QQ 会话列表项、输入框等），回退到截图+视觉模型按名称定位。
    """
    obs = ui_observe(app=app)
    if "视觉观察失败" in obs or "前置聚焦失败" in obs:
        return None
    best = None
    for line in obs.splitlines()[1:]:
        line = line.strip()
        m = re.search(r"(\d+)\s*,\s*(\d+)\s*$", line)
        if not m:
            continue
        x, y = int(m.group(1)), int(m.group(2))
        head = line[: m.start()].strip().strip('"[]{}').strip("|").strip()
        segs = [s.strip() for s in head.split("|") if s.strip()]
        name = "|".join(segs[:-1]) if len(segs) >= 2 else head
        ctype = segs[-1] if segs else "其他"
        if kw in name:
            # 头像/个人浮层不是会话入口，直接排除
            if ctype == "头像":
                continue
            # 名称命中精度优先于类型分：精确等于 > 以关键词开头 > 仅包含。
            # 否则日志/日报等长名称列表项（仅包含关键词）会压过真正的联系人（类型分被类型权重反超）。
            name_score = 6 if name.strip() == kw else (3 if name.strip().startswith(kw) else 0)
            # 会话列表项/菜单项优先；联系人类型可能是身份区（当前账号）而非会话入口，score 下调
            type_score = 2 if ctype in ("列表项",) else (
                2 if ctype in ("输入框", "按钮", "菜单项") else (
                1 if ctype == "联系人" else (1 if ctype in ("标签",) else 0)))
            base_score = name_score + type_score
            if best is None or base_score > best[0]:
                best = (base_score, name, ctype, x, y)
    return best


def _get_win_rect(app: str) -> tuple | None:
    """按应用名/进程名枚举顶层窗口，返回最大主窗口的屏幕 rect (left, top, right, bottom)。

    用于把视觉/坐标判断从「硬编码屏幕阈值」改为「基于窗口位置的相对判断」：
    钉钉等 IM 窗口可被拖动到任意位置，写死 x>450 之类阈值会整体失效。
    """
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    _APP_PROC = {"钉钉": "DingTalk", "微信": "WeChat", "企业微信": "WXWork", "qq": "QQ"}
    _pn = _APP_PROC.get((app or "").strip().lower(), "")

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL

    found = []

    def _proc_name_of(hwnd):
        try:
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            hproc = kernel32.OpenProcess(0x1000, False, pid.value)
            if not hproc:
                return ""
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            ok = kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size))
            kernel32.CloseHandle(hproc)
            if not ok:
                return ""
            return buf.value.split("\\")[-1]
        except Exception:  # noqa: BLE001
            return ""

    @WNDENUMPROC
    def _enum_win(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        t = buf.value
        pname = _proc_name_of(hwnd) if _pn else ""
        if (_pn and pname and _pn.lower() in pname.lower()) or (not _pn and (app or "").strip().lower() in t.lower()):
            r = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            found.append((r.left, r.top, r.right, r.bottom))
        return True

    user32.EnumWindows(_enum_win, 0)
    if not found:
        return None
    # 选中面积最大的窗口作为主窗口
    return max(found, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))


def _verify_chat_opened(contact: str, app: str = "") -> bool:
    """验证是否已真正进入「contact」的聊天会话：右侧会话标题含联系人，且聊天区出现输入框。

    防止点击误命中身份区/导航/群会话后被误判为成功（此前候选验证只看标题，点错群也通过）。
    输入框证据：优先视觉文本里的非搜索输入框；视觉漏识别时回退用 UIA 编辑框（钉钉实测输入框 UIA 可见）。
    右侧聊天区的判断基于窗口 rect 动态计算（聊天区 x > 窗口左缘 + 宽度*0.35），不再硬编码屏幕阈值。
    """
    try:
        obs = ui_observe(app=app)
    except Exception:  # noqa: BLE001
        return False
    if "视觉观察失败" in obs or "前置聚焦失败" in obs:
        return False
    win = _get_win_rect(app) if (app or "").strip() else None
    chat_x_min = (win[0] + (win[2] - win[0]) * 0.35) if win else 500
    hit_title = False
    hit_input = False
    for line in obs.splitlines()[1:]:
        m = re.search(r"(\d+)\s*,\s*(\d+)\s*$", line.strip())
        if not m:
            continue
        x = int(m.group(1))
        if x < chat_x_min:  # 只认右侧聊天区
            continue
        if contact in line and any(t in line for t in ("标签", "联系人")):
            hit_title = True
        if "输入框" in line and "搜索" not in line and "查找" not in line:
            hit_input = True
    if not hit_input:
        try:
            edits = _uia_find_edits(limit=30)
            hit_input = any("search" not in (e[0] or "").lower() and "搜索" not in e[0] for e in edits)
        except Exception:  # noqa: BLE001
            hit_input = False
    return hit_title and hit_input


def _open_contact_chat(contact: str, app: str, steps: list, pre_list: list | None = None) -> bool:
    """三级递进进入联系人会话：UIA 语义定位 → 视觉列表候选 → 快捷键搜索。每级点击后做会话验证，返回是否已进入。"""
    # 0) 前置强制聚焦：UIA 枚举基于前台窗口树，若被 WPS/浏览器等全屏窗口抢占前台，会枚举到错误窗口（假执行根源）
    _APP_PROC = {"钉钉": "DingTalk", "微信": "WeChat", "企业微信": "WXWork", "qq": "QQ"}
    if (app or "").strip():
        steps.append(f"进入会话前置聚焦: {window_focus(title_substr=app, process_name=_APP_PROC.get(app.lower(), ''))}")
        time.sleep(0.3)
    # 1) UIA 语义定位：按名称找可交互控件，排除身份区/导航区/标题栏
    for label, ctype, rect, ctrl in _uia_find_keyword(contact, limit=30):
        base = ctype[:-7] if ctype.endswith("Control") else ctype
        if base not in ("Button", "MenuItem", "ListItem", "TabItem", "DataItem", "Hyperlink", "Edit"):
            continue
        try:
            aid = (ctrl.AutomationId or "").lower()
        except Exception:  # noqa: BLE001
            aid = ""
        if any(k in aid for k in ("identity", "navigator", "titlebar", "header", "main_frame", "widget.split")):
            continue
        steps.append(f"UIA 定位联系人「{label}」({ctype})")
        steps.append(_click_uia_ctrl(ctrl, label.split(" | ")[0], ctype))
        time.sleep(1.2)
        if _verify_chat_opened(contact, app=app):
            steps.append("UIA 点击后验证通过：已进入联系人会话")
            return True
        steps.append("UIA 点击后验证未通过，继续尝试视觉路径")

    # 2) 视觉列表候选：会话列表项（基于窗口 rect 动态判断：排除身份区/导航 x<left+0.12w，排除顶部标题栏 y<top+0.06h）
    _win = _get_win_rect(app) if (app or "").strip() else None
    if _win:
        _list_x_min = _win[0] + (_win[2] - _win[0]) * 0.12
        _list_y_min = _win[1] + (_win[3] - _win[1]) * 0.06
    else:
        _list_x_min, _list_y_min = 450, 80

    def _visual_list_cands() -> list:
        cands = _find_obs_keyword_all(contact, app=app, retries=1) or _find_obs_keyword_all(contact.split()[0] if contact.split() else contact, app=app, retries=1)
        return [c for c in cands if c[2] in ("列表项", "联系人") and c[3] > _list_x_min and c[4] > _list_y_min]

    list_cands = [c for c in (pre_list or []) if c[2] in ("列表项", "联系人") and c[3] > _list_x_min and c[4] > _list_y_min] or _visual_list_cands()
    if not list_cands:
        # 无候选：ESC 关闭搜索浮层 + 点「消息」导航进入会话列表页，再重查
        try:
            import pyautogui
            pyautogui.press("esc")
            time.sleep(0.6)
            steps.append("已按 ESC 关闭搜索浮层")
        except Exception as exc:  # noqa: BLE001
            steps.append(f"ESC 失败：{exc}")
        nav = _find_obs_keyword("消息", app=app)
        if nav:
            nx, ny = _calibrate_visual_point(nav[1], nav[3], nav[4], app=app)
            steps.append(f"点击「消息」导航（校准 {nx},{ny}）")
            steps.append(mouse_click(x=nx, y=ny))
            time.sleep(1.5)
        list_cands = _visual_list_cands()

    # 2b) 逐候选点击并验证
    for _, name, ctype, vx, vy in list_cands[:5]:
        cx, cy = _calibrate_visual_point(name, vx, vy, app=app)
        steps.append(f"点击候选人「{name}」（类型={ctype}，视觉 {vx},{vy}，校准后 {cx},{cy}）")
        steps.append(mouse_click(x=cx, y=cy))
        time.sleep(1.2)
        if _verify_chat_opened(contact, app=app):
            steps.append("候选验证通过：右侧会话标题含联系人且已出现输入框")
            return True
        steps.append("候选验证未通过（可能是身份区/导航误命中），尝试下一候选")

    # 3) 快捷键搜索兜底：钉钉 Ctrl+Shift+F、微信/企微/QQ Ctrl+F 呼出搜索框 → 键入联系人 → 点搜索结果
    steps.append("列表候选未通过验证，改用快捷键搜索")
    import pyautogui
    _hotkeys = {"钉钉": ["ctrl", "shift", "f"], "微信": ["ctrl", "f"], "企业微信": ["ctrl", "f"], "qq": ["ctrl", "f"]}
    hk = _hotkeys.get((app or "").strip().lower(), ["ctrl", "shift", "f"])
    try:
        pyautogui.hotkey(*hk)
        time.sleep(1.2)
        steps.append(f"已用快捷键呼出搜索框（{' + '.join(h.upper() for h in hk)}）")
    except Exception as exc:  # noqa: BLE001
        steps.append(f"快捷键呼出搜索框失败：{exc}")
        box = _find_obs_keyword("搜索", app=app) or _find_obs_keyword("查找", app=app) or _find_obs_keyword("输入框", app=app)
        if not box:
            return False
        bx, by = _calibrate_visual_point(box[1], box[3], box[4], app=app)
        steps.append(f"点击搜索框「{box[1]}」（校准 {bx},{by}）")
        steps.append(mouse_click(x=bx, y=by))
        time.sleep(0.8)
    steps.append(f"键入搜索词: {type_text(text=contact, enter=False)}")
    time.sleep(1.5)
    sr = _find_obs_keyword_all(contact, app=app) or _find_obs_keyword_all(contact.split()[0] if contact.split() else contact, app=app)
    # 搜索结果区：列表项/联系人且位于顶部标题栏之下；y>150 排除身份区/导航区常驻候选（如「罗永康云集团」身份卡 y~99）
    sr_list = [c for c in sr if c[2] in ("列表项", "联系人") and c[4] > 150]
    if not sr_list:
        return False
    for _, name, ctype, vx, vy in sr_list[:3]:
        cx, cy = _calibrate_visual_point(name, vx, vy, app=app)
        steps.append(f"点击搜索结果「{name}」（类型={ctype}，视觉 {vx},{vy}，校准后 {cx},{cy}）")
        steps.append(mouse_click(x=cx, y=cy))
        time.sleep(1.2)
        if _verify_chat_opened(contact, app=app):
            steps.append("搜索结果验证通过：已进入联系人会话")
            return True
        steps.append("搜索结果验证未通过（可能点中非会话条目），尝试下一候选")
    return False


def _find_obs_keyword_all(kw: str, app: str = "", retries: int = 0) -> list:
    """视觉观察当前界面，返回名称含关键词的全部候选（按优先级降序）。

    返回 [(score, name, ctype, x, y), ...]，供 send_chat_message 逐候选点击验证。
    retries>0 时多次观察取并集（去重保留首次坐标），缓解单次视觉识别不稳定导致的漏召回。
    """
    cands = []
    seen_names = set()
    for _ in range(retries + 1):
        obs = ui_observe(app=app)
        if "视觉观察失败" in obs or "前置聚焦失败" in obs:
            continue
        for line in obs.splitlines()[1:]:
            line = line.strip()
            m = re.search(r"(\d+)\s*,\s*(\d+)\s*$", line)
            if not m:
                continue
            x, y = int(m.group(1)), int(m.group(2))
            head = line[: m.start()].strip().strip('"[]{}').strip("|").strip()
            segs = [s.strip() for s in head.split("|") if s.strip()]
            name = "|".join(segs[:-1]) if len(segs) >= 2 else head
            ctype = segs[-1] if segs else "其他"
            if kw in name:
                if ctype == "头像":
                    continue
                # 名称命中精度优先：精确等于 > 以关键词开头 > 仅包含；类型分仅作次级权重
                name_score = 6 if name.strip() == kw else (3 if name.strip().startswith(kw) else 0)
                type_score = 2 if ctype in ("列表项",) else (
                    2 if ctype in ("输入框", "按钮", "菜单项") else (
                    1 if ctype == "联系人" else (1 if ctype in ("标签",) else 0)))
                # 去重：同名称同类型只保留首次出现坐标（跨观察合并）
                dedup_key = (name, ctype)
                if dedup_key in seen_names:
                    continue
                seen_names.add(dedup_key)
                cands.append((name_score + type_score, name, ctype, x, y))
    cands.sort(key=lambda c: -c[0])
    return cands


def _calibrate_visual_point(name: str, x: int, y: int, app: str = "") -> tuple:
    """用 UIA 精确控件校准视觉模型坐标偏差。

    视觉模型（glm-4v-flash）返回的坐标对自绘界面常有 20~60px 偏移，
    导致点击命中相邻元素。策略：若视觉命中元素在 UIA 树里存在同名控件，
    直接用 UIA 控件中心精确坐标；否则统计同名视觉元素与 UIA 控件的平均
    偏移，校正到视觉坐标上。
    """
    try:
        hits = _uia_find_keyword(name.split("|")[0], limit=20)
    except Exception:  # noqa: BLE001
        return x, y
    if not hits:
        return x, y
    offsets = []
    for _, ctype, rect, ctrl in hits:
        try:
            cx = (rect.left + rect.right) // 2
            cy = (rect.top + rect.bottom) // 2
        except Exception:  # noqa: BLE001
            continue
        # 视觉坐标与 UIA 坐标接近（<60px）才视为同一元素；否则可能是其他控件同名（如身份区账号名），不可用作校准
        if abs(cx - x) < 60 and abs(cy - y) < 60:
            offsets.append((x - cx, y - cy))
            # 若视觉与 UIA 几乎重合，直接用 UIA 精确坐标
            if abs(x - cx) < 8 and abs(y - cy) < 8:
                return cx, cy
    if not offsets:
        return x, y
    # 平均偏移校正（多数情况视觉坐标整体平移）
    dx = int(sum(o[0] for o in offsets) / len(offsets))
    dy = int(sum(o[1] for o in offsets) / len(offsets))
    return x - dx, y - dy


def _uia_find_edits(limit: int = 20) -> list:
    """UIA 遍历前台窗口控件树，返回所有 Edit 输入框 [(label, ctype, rect, ctrl)]。

    label 为「名称 或 AutomationId」，用于区分搜索框与聊天输入框。
    """
    try:
        import uiautomation as auto
    except Exception:  # noqa: BLE001
        return []
    try:
        fg = auto.GetForegroundControl()
        if not fg:
            return []
        found = []
        stack = [fg]
        node_count = 0
        while stack and len(found) < int(limit or 20):
            ctrl = stack.pop()
            node_count += 1
            if node_count > 800:
                break
            try:
                ctype = ctrl.ControlTypeName or ""
                name = (ctrl.Name or "").strip()
                aid = (ctrl.AutomationId or "").strip()
                rect = ctrl.BoundingRectangle
            except Exception:  # noqa: BLE001
                continue
            if rect is None or rect.right <= rect.left or rect.bottom <= rect.top:
                continue
            if ctype not in ("EditControl", "Edit"):
                try:
                    children = ctrl.GetChildren()
                    if len(stack) + len(children) < 1200:
                        stack.extend(reversed(children))
                except Exception:  # noqa: BLE001
                    pass
                continue
            label = name or aid or "编辑框"
            found.append((label, ctype, rect, ctrl))
            try:
                children = ctrl.GetChildren()
                if len(stack) + len(children) < 1200:
                    stack.extend(reversed(children))
            except Exception:  # noqa: BLE001
                pass
        return found
    except Exception:  # noqa: BLE001
        return []


def _uia_find_keyword(kw: str, exact: bool = False, limit: int = 20) -> list:
    """UIA 遍历前台窗口控件树，按名称关键词返回可交互控件。

    返回 [(label, ctype, rect, ctrl)]，label 为「名称 或 AutomationId」，
    ctype 为 ControlTypeName，rect 为 BoundingRectangle，坐标已可直接用于点击。
    """
    try:
        import uiautomation as auto
    except Exception:  # noqa: BLE001
        return []
    try:
        fg = auto.GetForegroundControl()
        if not fg:
            return []
        found = []
        stack = [fg]
        node_count = 0
        while stack and len(found) < int(limit or 20):
            ctrl = stack.pop()
            node_count += 1
            if node_count > 800:
                break
            # 先扩展子节点，再判断是否命中（避免非交互类型 continue 导致子树丢失）
            try:
                children = ctrl.GetChildren()
                if len(stack) + len(children) < 1200:
                    stack.extend(reversed(children))
            except Exception:  # noqa: BLE001
                pass
            try:
                ctype = ctrl.ControlTypeName or ""
                name = (ctrl.Name or "").strip()
                aid = (ctrl.AutomationId or "").strip()
                rect = ctrl.BoundingRectangle
            except Exception:  # noqa: BLE001
                continue
            if rect is None or rect.right <= rect.left or rect.bottom <= rect.top:
                continue
            ctype_base = ctype[:-7] if ctype.endswith("Control") else ctype
            if ctype_base not in _INTERACTIVE_CTRL_TYPES:
                continue
            label = name or aid or ""
            if not label:
                continue
            if exact:
                ok = kw in (name, aid)
            else:
                ok = kw in name or (aid and kw in aid)
            if ok:
                found.append((label, ctype, rect, ctrl))
        # 去重：同 label+type 保留第一个（层级浅的优先）
        dedup, seen = [], set()
        for label, ctype, rect, ctrl in found:
            sig = f"{label}|{ctype}"
            if sig in seen:
                continue
            seen.add(sig)
            dedup.append((label, ctype, rect, ctrl))
        return dedup
    except Exception:  # noqa: BLE001
        return []


def _click_uia_ctrl(ctrl, name: str, ctype: str) -> str:
    """按 UIA 控件点击：优先直接用控件句柄点击，失效则按名称+类型重查。"""
    try:
        import uiautomation as auto
    except Exception as exc:  # noqa: BLE001
        return f"未安装 uiautomation 依赖：{exc}"
    try:
        if not ctrl.Exists(0.5):
            ctrl = auto.Control(searchDepth=1, Name=name, ControlType=ctype)
            if not ctrl.Exists(1.5):
                return f"控件已失效且按名称重查失败：{name} ({ctype})"
        ctrl.Click(simulateMove=False)
        # Edit 控件点击后主动 SetFocus，确保后续键入落到该控件（自绘应用仅 Click 可能不聚焦）
        try:
            if "Edit" in (ctype or "") or ctrl.ControlTypeName in ("EditControl", "Edit"):
                ctrl.SetFocus()
        except Exception:  # noqa: BLE001
            pass
        return f"已点击控件：{name} ({ctype})"
    except Exception as exc:  # noqa: BLE001
        return f"UI 点击失败：{exc}"


@tool(
    name="ui_click_name",
    description="按名称语义点击应用内控件（基于 UIAutomation 控件树，遍历搜索名称/AutomationId 包含关键词的控件，优先可交互类型）。区别于 ui_click_ref 的编号盲点：不依赖 window_inspect 编号，直接按语义名称定位，控件位置变化也能命中。适合『点击 消息/发送/确定』『给罗永发消息』等场景；UIA 拿不到自绘控件时再配合 ui_observe/ui_click_text 视觉兜底",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "要点击的控件名称关键词，如 '消息'、'罗永'、'发送'、'确定'；匹配 Name 或 AutomationId"},
            "app": {"type": "string", "description": "目标应用名（可选），带上前会先聚焦该窗口再搜索"},
            "exact": {"type": "boolean", "description": "是否精确匹配（默认 False，包含匹配）"},
        },
        "required": ["name"],
    },
    risk="medium",
)
def ui_click_name(name: str = "", app: str = "", exact: bool = False) -> str:
    name = (name or "").strip()
    if not name:
        return "请提供控件名称关键词（name）"
    if (app or "").strip():
        fc = window_focus(title_substr=app.strip())
        if "未找到" in fc:
            return f"ui_click_name 前置聚焦失败：{fc}"
    hits = _uia_find_keyword(name, exact=exact)
    if not hits:
        return f"UIA 控件树中未找到名称包含「{name}」的控件，可改用 ui_observe/ui_click_text 视觉兜底"
    # 优先可交互类型；同名多命中时取层级浅、面积最小的可交互项
    hits.sort(key=lambda h: (h[2].right - h[2].left) * (h[2].bottom - h[2].top))
    label, ctype, rect, ctrl = hits[0]
    return _click_uia_ctrl(ctrl, label.split(" | ")[0], ctype)

_LAST_UIA_CONTROLS: list = []  # [(name, control_type, rect, ctrl)]，供 ui_click_ref 使用
_LAST_UIA_AT = 0.0


def _snapshot_controls(limit: int = 40) -> str:
    """枚举前台窗口可交互控件并刷新全局快照（供 window_inspect 展示与 ui_click_ref 自动兜底）。"""
    global _LAST_UIA_CONTROLS, _LAST_UIA_AT
    try:
        import uiautomation as auto
    except Exception as exc:  # noqa: BLE001
        return f"未安装 uiautomation 依赖：{exc}"
    try:
        fg = auto.GetForegroundControl()
        if not fg:
            return "未获取到前台窗口"
        title = getattr(fg, "Name", "") or ""
        found = []
        stack = [fg]
        node_count = 0
        while stack and len(found) < int(limit or 40):
            ctrl = stack.pop()
            node_count += 1
            if node_count > 800:
                break
            try:
                ctype = ctrl.ControlTypeName or ""
                name = (ctrl.Name or "").strip()
                aid = ""
                try:
                    aid = (ctrl.AutomationId or "").strip()
                except Exception:  # noqa: BLE001
                    pass
                rect = ctrl.BoundingRectangle
            except Exception:  # noqa: BLE001
                continue
            visible = False
            try:
                visible = rect is not None and rect.right > rect.left and rect.bottom > rect.top
            except Exception:  # noqa: BLE001
                pass
            ctype_base = ctype[:-7] if ctype.endswith("Control") else ctype
            label = name or aid or ""
            if label and ctype_base in _INTERACTIVE_CTRL_TYPES and visible:
                found.append((label, ctype, rect, ctrl))
            try:
                children = ctrl.GetChildren()
                if len(stack) + len(children) < 1200:
                    stack.extend(reversed(children))
            except Exception:  # noqa: BLE001
                pass
        # 去重：同 label+type 只保留第一个（层级浅的优先）
        dedup = []
        seen = set()
        for label, ctype, rect, ctrl in found:
            sig = f"{label}|{ctype}"
            if sig in seen:
                continue
            seen.add(sig)
            dedup.append((label, ctype, rect, ctrl))
        _LAST_UIA_CONTROLS = dedup
        _LAST_UIA_AT = time.time()
        if not dedup:
            return f"窗口「{title}」内未发现可交互控件（扫描 {node_count} 个节点）"
        lines = [f"窗口：{title}（共 {len(dedup)} 个可交互控件，编号从 1 开始）"]
        for i, (name, ctype, rect, _) in enumerate(dedup, 1):
            try:
                pos = f"[{rect.left},{rect.top},{rect.right - rect.left}x{rect.bottom - rect.top}]"
            except Exception:  # noqa: BLE001
                pos = ""
            lines.append(f"[{i}] {name} ({ctype}) {pos}")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"窗口枚举失败：{exc}"


@tool(
    name="window_inspect",
    description="枚举当前前台窗口内的可交互控件，输出带编号的清单（基于 UIAutomation；配合 ui_click_ref 按编号操作）",
    parameters={
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "最多返回控件数，默认40"},
        },
        "required": [],
    },
    risk="low",
)
def window_inspect(limit: int = 40) -> str:
    return _snapshot_controls(limit)


@tool(
    name="ui_click_ref",
    description="按 window_inspect 返回的编号点击应用内控件（基于 UIAutomation；快照过期需重新 window_inspect）",
    parameters={
        "type": "object",
        "properties": {
            "index": {"type": "integer", "description": "window_inspect 返回的控件编号（从 1 开始）"},
        },
        "required": ["index"],
    },
    risk="medium",
)
def ui_click_ref(index: int) -> str:
    global _LAST_UIA_CONTROLS, _LAST_UIA_AT
    try:
        import uiautomation as auto
    except Exception as exc:  # noqa: BLE001
        return f"未安装 uiautomation 依赖：{exc}"
    if not _LAST_UIA_CONTROLS or time.time() - _LAST_UIA_AT > 30:
        # 快照缺失/过期：自动刷新一次（多步自动任务中无需预先 window_inspect）
        _snapshot_controls()
        if not _LAST_UIA_CONTROLS:
            return "控件快照已过期或为空，自动刷新后仍未获取到可交互控件，请先确认目标窗口在前台后再试"
    idx = int(index) - 1
    if idx < 0 or idx >= len(_LAST_UIA_CONTROLS):
        return f"编号 {index} 超出范围（当前快照共 {len(_LAST_UIA_CONTROLS)} 个控件）"
    name, ctype, _, ctrl = _LAST_UIA_CONTROLS[idx]
    try:
        if not ctrl.Exists(0.5):
            ctrl = auto.Control(searchDepth=1, Name=name, ControlType=ctype)
            if not ctrl.Exists(1.5):
                return f"控件已失效且按名称重查失败：{name} ({ctype})"
        ctrl.Click(simulateMove=False)
        return f"已点击控件 #{index}：{name} ({ctype})"
    except Exception as exc:  # noqa: BLE001
        return f"UI 点击失败：{exc}"


@tool(
    name="ui_observe",
    description="视觉观察当前界面：截图并调用视觉模型，返回界面上的文字元素清单（名称+类型+屏幕坐标）。适用于 UIA 快照拿不到语义的复杂应用（钉钉/微信/QQ/自绘界面等），供智能体按坐标决策操作；可选 app 参数指定目标应用名，会先聚焦该窗口再截图，避免观察错窗口",
    parameters={
        "type": "object",
        "properties": {
            "app": {"type": "string", "description": "目标应用名（可选），如 '钉钉'；传了会先聚焦该应用窗口再截图观察"},
        },
        "required": [],
    },
    risk="medium",
)
def ui_observe(app: str = "") -> str:
    """截取当前屏幕，调用视觉模型（glm-4v-flash）识别界面元素及屏幕坐标。

    返回格式：元素清单，每行「名称 | 类型 | 中心屏幕坐标(x,y)」。失败返回失败原因。
    """
    import base64
    from ..config import config

    try:
        from .registry import call_tool as _call_tool
    except Exception as exc:  # noqa: BLE001
        return f"工具注册表不可用：{exc}"

    offset_x, offset_y = 0, 0
    shot_mode = "full"
    win_rect = None
    if (app or "").strip():
        _app_proc_map = {"钉钉": "DingTalk", "微信": "WeChat", "企业微信": "WXWork", "qq": "QQ"}
        _pn = _app_proc_map.get(app.strip().lower(), "")
        if _pn:
            focus = _call_tool("window_focus", {"title_substr": app.strip(), "process_name": _pn})
        else:
            focus = _call_tool("window_focus", {"title_substr": app.strip()})
        if "未找到" in focus:
            return f"ui_observe 前置聚焦失败：{focus}"
        # 窗口模式截图：只拍目标窗口，排除其他窗口干扰；记录窗口左上角，用于把窗口内坐标换算成屏幕坐标
        # 关键：这里枚举定位目标窗口 rect，而非依赖 GetForegroundWindow（前台可能被抢占导致 offset 与截图区域错位）
        shot_mode = "window"
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int
        found_windows = []

        kernel32 = ctypes.windll.kernel32

        def _proc_name_of(hwnd):
            try:
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                hproc = kernel32.OpenProcess(0x1000, False, pid.value)
                if not hproc:
                    return ""
                buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                ok = kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(size))
                kernel32.CloseHandle(hproc)
                if not ok:
                    return ""
                return buf.value.split("\\")[-1]
            except Exception:  # noqa: BLE001
                return ""

        @WNDENUMPROC
        def _enum_win(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            t = buf.value
            pname = _proc_name_of(hwnd) if _pn else ""
            # 进程名匹配的窗口直接入选（标题随页面变化不可靠）；否则按标题匹配
            if (_pn and pname and _pn.lower() in pname.lower()) or (not _pn and app.strip().lower() in t.lower()):
                browser_mark = ("edge", "chrome", "firefox", "浏览器", "360", "iexplore")
                r = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(r))
                w = max(1, r.right - r.left)
                h = max(1, r.bottom - r.top)
                score = 200 if t.strip().lower() == app.strip().lower() else (100 if t.strip().lower().startswith(app.strip().lower()) else 0)
                if _pn and pname and _pn.lower() in pname.lower():
                    score += 300  # 进程匹配优先
                if any(b in t.lower() for b in browser_mark):
                    score -= 500
                score += min(w * h, 4000000) / 100000.0
                found_windows.append((score, hwnd, (r.left, r.top, w, h), t))
            return True

        user32.EnumWindows(_enum_win, 0)
        if found_windows:
            found_windows.sort(key=lambda x: -x[0])
            _, _hwnd, win_rect, _title = found_windows[0]
            offset_x, offset_y = win_rect[0], win_rect[1]
        else:
            rect = wintypes.RECT()
            if user32.GetWindowRect(user32.GetForegroundWindow(), ctypes.byref(rect)):
                win_rect = (rect.left, rect.top, max(1, rect.right - rect.left), max(1, rect.bottom - rect.top))
                offset_x, offset_y = win_rect[0], win_rect[1]
    if win_rect is not None and shot_mode == "window":
        # 用枚举出的目标窗口 rect 直接截图，避免 screenshot 工具取前台窗口造成区域与 offset 错位
        import subprocess
        import datetime
        import os
        now = datetime.datetime.now()
        fname = f"screenshot_{now.year}{now.month:02d}{now.day:02d}_{now.hour:02d}{now.minute:02d}{now.second:02d}.png"
        save_path = os.path.join(config.data_dir, "screenshots", fname)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        x, y, w, h = win_rect
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            f"$bmp = New-Object System.Drawing.Bitmap({w},{h}); "
            "$g = [System.Drawing.Graphics]::FromImage($bmp); "
            f"$g.CopyFromScreen({x},{y},0,0,$bmp.Size); "
            f"$bmp.Save('{save_path}',[System.Drawing.Imaging.ImageFormat]::Png); "
            "$g.Dispose(); $bmp.Dispose(); 'ok'"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=60,
        )
        out = (r.stdout or "").strip()
        if out == "ok":
            shot = f"已截取活动窗口，保存到：{save_path}"
        else:
            shot = f"截图失败：{out or r.stderr[:200]}"
    else:
        shot = _call_tool("screenshot", {"mode": shot_mode})
    if not shot.startswith("已截取"):
        return f"截图失败：{shot}"
    path = shot.rsplit("：", 1)[-1].strip()

    api_key = (config.llm_config.get("api_key") or "").strip()
    base_url = (config.llm_config.get("base_url") or "").strip()
    if not api_key:
        return "未配置 LLM API Key，无法进行视觉观察"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url or "https://open.bigmodel.cn/api/paas/v4/")
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        resp = client.chat.completions.create(
            model="glm-4v-flash",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": (
                        "这是电脑界面截图。请识别图中所有可操作/有意义的文字元素，"
                        "输出每行一个元素：格式「名称 | 类型 | 坐标x,y」，坐标取元素中心在图片内的像素值。"
                        "类型填：按钮/输入框/联系人/菜单项/列表项/标签/消息/其他。"
                        "注意：如果界面是聊天窗口，聊天消息文本也要作为元素列出（类型=消息）。"
                        "只输出清单，最多 40 行，不要解释。"
                    )},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }],
            max_tokens=900,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            return "视觉模型未返回元素清单"
        # 清洗输出：去掉可能的 ```json 围栏与数组语法，逐行还原为「名称 | 类型 | 坐标x,y」
        clean = content
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:json)?\s*", "", clean)
            clean = re.sub(r"\s*```$", "", clean)
        if clean.strip().startswith("[") and clean.strip().endswith("]"):
            try:
                arr = json.loads(clean)
                clean = "\n".join(str(x) for x in arr)
            except Exception:  # noqa: BLE001
                pass
        # 兜底：逐行剥掉首尾引号/方括号/尾部逗号，统一为「名称 | 类型 | x,y」
        rows = []
        for line in clean.splitlines():
            line = line.strip()
            if not line:
                continue
            line = line.strip(" \t\r\n\"'[]{}").rstrip(",").strip()
            # 兼容「"名称" | 类型 | x,y」格式：去掉名称两侧残留引号
            line = line.replace('"', "").replace("'", "")
            if line:
                rows.append(line)
        clean = "\n".join(rows)
        # 窗口模式：把视觉模型返回的窗口内坐标换算成屏幕绝对坐标，保证与 mouse_click 全屏坐标一致
        if shot_mode == "window" and (offset_x or offset_y):
            shifted = []
            for line in clean.splitlines():
                line = line.strip()
                # 行格式可能为「名称 | 类型 | x,y」或「名称 | 类型 | | x,y」，统一以最后的「数字,数字」为坐标
                m = re.search(r"(\d+)\s*,\s*(\d+)\s*$", line)
                if m:
                    x = int(m.group(1)) + offset_x
                    y = int(m.group(2)) + offset_y
                    parts = line.rsplit("|", 1)
                    shifted.append(f"{parts[0].strip()} | {x},{y}")
                else:
                    shifted.append(line)
            clean = "\n".join(shifted)
        return f"视觉观察完成（截图：{path}）：\n{clean}"
    except Exception as exc:  # noqa: BLE001
        return f"视觉观察失败：{exc}"


@tool(
    name="ui_click_text",
    description="按文本语义点击：先对目标窗口做视觉观察，找到名称包含指定关键词的元素，点击其屏幕坐标。用于钉钉/微信/QQ 等自绘界面（UIA 拿不到语义控件），可点击「消息」「罗永」「发送」等任意可见文字元素",
    parameters={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要点击的元素名称关键词，如 '消息'、'罗永'、'发送'、'确定'"},
            "app": {"type": "string", "description": "目标应用名（可选），带上前会先聚焦该窗口再观察，避免截错窗口"},
        },
        "required": ["text"],
    },
    risk="medium",
)
def ui_click_text(text: str = "", app: str = "") -> str:
    """按文本语义点击：ui_observe 视觉观察 -> 名称包含关键词 -> mouse_click 屏幕坐标。"""
    text = (text or "").strip()
    if not text:
        return "请提供要点击的文本关键词（text）"
    obs = ui_observe(app=app or "")
    if "视觉观察失败" in obs or "前置聚焦失败" in obs:
        return f"ui_click_text 前置观察失败：{obs[:300]}"
    # 解析观察返回的元素行：格式「名称 | 类型 | x,y」（坐标可能被偏移过，已是屏幕绝对坐标）
    candidates = []
    for line in obs.splitlines()[1:]:  # 第一行是"视觉观察完成..."
        line = line.strip()
        # 统一以行尾「数字,数字」作为坐标；元素名取 | 分隔的其余部分
        m = re.search(r"(\d+)\s*,\s*(\d+)\s*$", line)
        if not m:
            continue
        x, y = int(m.group(1)), int(m.group(2))
        head = line[: m.start()].strip().strip('"[]{}').strip("|").strip()
        # head 形如「名称 | 类型」或「名称 | 类型 |」，取最后两段为名称与类型
        segs = [s.strip() for s in head.split("|") if s.strip()]
        if len(segs) < 2:
            name, ctype = head, "其他"
        else:
            ctype, name = segs[-1], "|".join(segs[:-1])
        if text in name:
            # 头像/身份区元素不是可点击进入会话的目标，直接排除（防止点中左上角个人信息进个人页/工作台）
            if ctype in ("头像", "身份", "个人信息"):
                continue
            # 优先点击可交互类型；标签/消息/其他作为后备
            score = 3 if ctype in ("按钮", "输入框", "联系人", "菜单项", "列表项", "按钮或链接") else (2 if ctype in ("标签",) else 1)
            # 同一名称多候选时，靠下的（y 更大）更可能是会话列表项而非顶部身份区/导航
            score += y / 100000.0
            candidates.append((score, name, ctype, x, y))
    if not candidates:
        return f"视觉观察中未找到包含「{text}」的元素。观察内容：\n{obs[:900]}"
    candidates.sort(key=lambda c: -c[0])
    _, name, ctype, x, y = candidates[0]
    res = mouse_click(x=x, y=y)
    return f"已按语义点击「{name}」（类型={ctype}，坐标 {x},{y}）：{res}"


@tool(
    name="send_chat_message",
    description="按名称语义给聊天应用（钉钉/微信/QQ/飞书等）的联系人发送消息：自动搜索联系人→点击进入会话→点击聊天区底部输入框聚焦→键入消息回车→视觉验证发送成功。全程按名称定位，不依赖 UIA 编号或硬编码坐标。用于『给XX发消息』类任务，优先于手动组合 ui_click_text/type_text",
    parameters={
        "type": "object",
        "properties": {
            "app": {"type": "string", "description": "目标应用名，如 '钉钉'、'微信'、'QQ'"},
            "contact": {"type": "string", "description": "联系人姓名或关键词，如 '罗永'"},
            "message": {"type": "string", "description": "要发送的消息内容，如 '你好'"},
        },
        "required": ["app", "contact", "message"],
    },
    risk="medium",
)
def send_chat_message(app: str = "", contact: str = "", message: str = "") -> str:
    """给聊天应用联系人发送消息：搜索→选会话→聚焦输入框→键入回车→验证。"""
    app = (app or "").strip()
    contact = (contact or "").strip()
    message = (message or "").strip()
    if not app or not contact or not message:
        return "请提供 app（应用名）、contact（联系人）、message（消息内容）"

    steps = []
    # 1. 聚焦目标应用。进程名过滤优先（钉钉等标题会随页面变化，仅按标题可能误命中浏览器标签页）
    _APP_PROC = {"钉钉": "DingTalk", "微信": "WeChat", "企业微信": "WXWork", "qq": "QQ"}
    _proc = _APP_PROC.get((app or "").lower(), "")
    fc = window_focus(title_substr=app, process_name=_proc) if _proc else window_focus(title_substr=app)
    if "未找到" in fc and _proc:
        # 进程名未命中时退回纯标题匹配（避免进程名拼写差异导致整体失败）
        fc = window_focus(title_substr=app)
    steps.append(f"聚焦: {fc}")
    if "失败" in fc or "未找到" in fc or "未完全生效" in fc:
        return "\n".join(steps) + "\n结果: 聚焦失败（可能有其他全屏窗口抢占前台），终止，请人工确认窗口状态"

    # 1.5 确保处于消息主界面：钉钉主窗口可能停在「日志/模力方舟」等 WebView 独立功能页（无左侧全局导航，会话列表不出现）。
    # 通过观察判断：左侧导航区（x<450）若找不到「消息/通讯录/文档」等菜单项，视为独立功能页，按 Alt+1 切回消息页。
    _nav_kws = ("消息", "通讯录", "文档", "日历", "待办", "工作台")
    _has_main_nav = False
    for _ in range(2):
        _obs0 = ui_observe(app=app)
        for _ln in _obs0.splitlines()[1:]:
            _m0 = re.search(r"(\d+)\s*,\s*(\d+)\s*$", _ln.strip())
            if not _m0:
                continue
            _x0 = int(_m0.group(1))
            _head0 = _ln.strip()[: _m0.start()].strip()
            if _x0 < 450 and "菜单项" in _head0 and any(k in _head0 for k in _nav_kws):
                _has_main_nav = True
                break
        if _has_main_nav:
            break
        # 未检测到主界面导航：尝试 Alt+1 切回消息页（钉钉左侧导航第一项）
        try:
            import pyautogui
            pyautogui.hotkey("alt", "1")
            time.sleep(1.5)
            steps.append("检测到独立功能页（无消息导航），已按 Alt+1 切回消息主界面")
        except Exception as exc:  # noqa: BLE001
            steps.append(f"Alt+1 切换消息页失败：{exc}")
            break
    if not _has_main_nav:
        steps.append("未确认消息主界面（左侧无消息/通讯录等导航），继续尝试会话定位")

    # 2. 视觉优先：若会话列表已包含目标联系人（钉钉等 IM 主界面），直接走会话列表点击，避免搜索浮层干扰
    _pre_cands = _find_obs_keyword_all(contact, app=app) or _find_obs_keyword_all(contact.split()[0] if contact.split() else contact, app=app)
    # 会话入口类型：视觉模型对 IM 会话列表项可能标为「列表项」或「联系人」（钉钉实测为「联系人」）。
    # 但「联系人」类型也可能是左侧身份区/右侧聊天标题，因此仅坐标落在会话列表区（基于窗口 rect 动态判断，不再硬编码 x>450）的才视为会话入口。
    _pre_win = _get_win_rect(app) if (app or "").strip() else None
    if _pre_win:
        _pre_x_min = _pre_win[0] + (_pre_win[2] - _pre_win[0]) * 0.12
        _pre_y_min = _pre_win[1] + (_pre_win[3] - _pre_win[1]) * 0.06
    else:
        _pre_x_min, _pre_y_min = 450, 80
    _pre_list = [c for c in _pre_cands if c[2] in ("列表项", "联系人") and c[3] > _pre_x_min and c[4] > _pre_y_min]
    if _pre_list:
        steps.append("会话列表已存在目标联系人，跳过搜索框")
    else:
        steps.append("当前界面无目标联系人会话列表项，稍后经「消息」导航进入")

    # 2b. 点击联系人条目并进入其会话。语义定位（UIA）→ 视觉列表候选 → 快捷键搜索 三级递进，每级点击后都做会话验证，全部失败才放弃
    if not _open_contact_chat(contact, app, steps, pre_list=_pre_list):
        return "\n".join(steps) + "\n结果: 未能进入联系人会话（UIA/列表候选/搜索均未通过验证），已停止（避免误发）"
    # 3. 找聊天区底部输入框并点击聚焦。语义优先：UIA Edit 控件里排除搜索框，取面积最小的编辑框
    # 先强制重聚焦目标窗口：此前 WPS 等全屏窗口会抢占前台，UIA 控件的屏幕坐标点击会落到抢占窗口上（假执行根源）
    _f3 = window_focus(title_substr=app, process_name=_APP_PROC.get(app.lower(), "")) if app else ""
    steps.append(f"定位输入框前重聚焦: {_f3}")
    time.sleep(0.3)
    obs_before = ui_observe(app=app)
    steps.append(f"会话页观察:\n{obs_before.splitlines()[1][:200] if len(obs_before.splitlines()) > 1 else obs_before[:200]}...")
    chat_edit = None
    edits = _uia_find_edits(limit=30)
    non_search = [e for e in edits if "search" not in (e[0] or "").lower() and "搜索" not in e[0]]
    if non_search:
        # 输入框通常是最小、最靠下的编辑框
        non_search.sort(key=lambda e: (e[2].right - e[2].left) * (e[2].bottom - e[2].top))
        chat_edit = non_search[0]
        steps.append(f"UIA 定位输入框：{chat_edit[0]} ({chat_edit[1]})")
        # UIA 控件中心可能是屏幕坐标，点击前再聚焦一次确保前台仍为目标窗口
        window_focus(title_substr=app, process_name=_APP_PROC.get(app.lower(), ""))
        steps.append(_click_uia_ctrl(chat_edit[3], "", "EditControl"))
        time.sleep(0.6)
    if chat_edit is None:
        hit = _find_obs_keyword("输入框", app=app) or _find_obs_keyword("输入", app=app) or _find_obs_keyword("发送消息", app=app) or _find_obs_keyword("写消息", app=app)
        if not hit:
            # 兜底：直接点击聊天区中部靠下位置后键入
            steps.append("未定位到输入框，尝试直接点击会话区底部后键入")
            obs = obs_before
            xs, ys = [], []
            for line in obs.splitlines()[1:]:
                m = re.search(r"(\d+)\s*,\s*(\d+)\s*$", line.strip())
                if m:
                    xs.append(int(m.group(1)))
                    ys.append(int(m.group(2)))
            if xs and ys:
                steps.append(mouse_click(x=int(sum(xs) / len(xs)), y=int(max(ys))))
            time.sleep(0.6)
        else:
            cx, cy = _calibrate_visual_point(hit[1], hit[3], hit[4], app=app)
            steps.append(f"点击输入框「{hit[1]}」（视觉 {hit[3]},{hit[4]}，校准后 {cx},{cy}）")
            steps.append(mouse_click(x=cx, y=cy))
            time.sleep(0.6)

    # 4. 键入消息并回车：先强制重聚焦目标窗口（此前多次出现 WPS/其他窗口抢占焦点，消息键入到了错误窗口造成假执行）
    # 等待缩短至 0.15s：WPS 等全屏窗口会在聚焦后约 0.9s 内抢回前台，等待过长则键入落在抢占窗口上
    _refocus = window_focus(title_substr=app, process_name=_APP_PROC.get(app.strip().lower(), "")) if (app or "").strip() else ""
    steps.append(f"键入前重聚焦: {_refocus}")
    time.sleep(0.15)
    steps.append(f"键入消息并发送: {type_text(text=message, enter=True)}")
    time.sleep(1.2)

    # 5. 视觉验证：最近一次观察里应出现消息文本
    obs = ui_observe(app=app)
    if "视觉观察失败" in obs or "前置聚焦失败" in obs:
        return "\n".join(steps) + f"\n结果: 已发送（验证观察失败：{obs[:120]}）"
    if message[:4] in obs:
        return "\n".join(steps) + "\n结果: 已发送并验证：消息出现在聊天窗口"
    return "\n".join(steps) + f"\n结果: 已执行发送动作，但验证未在观察中出现消息文本「{message[:10]}」，请人工确认"
