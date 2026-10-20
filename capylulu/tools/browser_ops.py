"""浏览器自动化工具（批次10）：基于 Playwright 的可控浏览器实例。

核心设计：模块级单例（_browser / _context / _page）跨调用保持会话，
使用持久化用户目录 data/browser_profile，登录态可跨任务复用。
覆盖：打开网页、跳转、点击、填表、按键、等待、提取文本/表格、截图、下载文件、关闭。
"""
from __future__ import annotations

import datetime
import functools
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from ..config import config
from .registry import tool

_browser = None
_context = None
_page = None
_ready = False
_pw = None  # Playwright 上下文管理器实例；不 stop 会让线程级 running loop 残留，导致同线程第二次 start() 误报 asyncio 冲突

# Playwright Sync API 是线程绑定的：浏览器实例在哪个线程创建，就必须在哪个线程操作。
# FastAPI 线程池每次请求可能落在不同线程，跨线程复用会报
# "Target page, context or browser has been closed" / "Sync API inside the asyncio loop"。
# 因此所有 browser_* 工具统一提交到单线程执行器，保证全程同线程、会话稳定。
_browser_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="capy-browser")


def _in_browser_thread(func):
    """把工具函数固定提交到浏览器专属线程执行。"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        future = _browser_executor.submit(func, *args, **kwargs)
        return future.result(timeout=240)

    return wrapper


def _profile_dir() -> str:
    d = os.path.join(config.data_dir, "browser_profile")
    os.makedirs(d, exist_ok=True)
    return d


def _download_dir() -> str:
    d = os.path.join(config.data_dir, "downloads")
    os.makedirs(d, exist_ok=True)
    return d


def _screenshots_dir() -> str:
    d = os.path.join(config.data_dir, "screenshots")
    os.makedirs(d, exist_ok=True)
    return d


def _cleanup_pw() -> None:
    """显式停止 Playwright 上下文管理器，避免线程级 running loop 残留。"""
    global _pw
    pw = _pw
    _pw = None
    if pw is not None:
        try:
            pw.stop()
        except Exception:  # noqa: BLE001
            pass


def _ensure_browser() -> str:
    """确保浏览器实例就绪，返回错误串或空串。"""
    global _browser, _context, _page, _ready, _pw
    if _ready and _page is not None and not _page.is_closed():
        return ""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        return f"未安装 playwright 依赖：{exc}"
    _cleanup_pw()
    try:
        _pw = sync_playwright().start()
        _browser = _pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        _context = _browser.new_context(
            accept_downloads=True,
            viewport={"width": 1366, "height": 860},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        )
        _context.set_default_timeout(15000)
        # 忽略常见弹窗
        _context.add_init_script(
            "window.alert=()=>{};window.confirm=()=>true;"
            "window.prompt=()=>null;"
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        _page = _context.new_page()
        _ready = True
        return ""
    except Exception as exc:  # noqa: BLE001
        _ready = False
        return f"浏览器启动失败：{exc}"


@tool(
    name="browser_open",
    description="打开浏览器并访问指定网址（首次会自动启动可控 Chromium 浏览器；后续复用同一实例，登录态保持）",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要访问的完整网址，如 https://example.com"},
        },
        "required": ["url"],
    },
    risk="medium",
)
@_in_browser_thread
def browser_open(url: str) -> str:
    err = _ensure_browser()
    if err:
        return err
    if not (url or "").strip().lower().startswith(("http://", "https://")):
        return f"只支持 http/https 链接：{url}"
    try:
        _page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(0.8)
        return f"已打开 {url}，当前标题：{_page.title()}"
    except Exception as exc:  # noqa: BLE001
        return f"打开 {url} 失败：{exc}"


@tool(
    name="browser_goto",
    description="在当前浏览器标签页跳转到新网址（保持同一会话与登录态）",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要跳转的完整网址"},
        },
        "required": ["url"],
    },
    risk="medium",
)
@_in_browser_thread
def browser_goto(url: str) -> str:
    err = _ensure_browser()
    if err:
        return err
    try:
        _page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(0.8)
        return f"已跳转 {url}，当前标题：{_page.title()}"
    except Exception as exc:  # noqa: BLE001
        return f"跳转 {url} 失败：{exc}"


@tool(
    name="browser_click",
    description="点击页面元素（CSS 选择器；可指定第几个匹配项）",
    parameters={
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS 选择器，如 '#login-btn'、'button:has-text(\"登录\")'"},
            "index": {"type": "integer", "description": "匹配到的第几个（从0开始），默认0"},
        },
        "required": ["selector"],
    },
    risk="medium",
)
@_in_browser_thread
def browser_click(selector: str, index: int = 0) -> str:
    err = _ensure_browser()
    if err:
        return err
    selector = _coerce_selector(selector)
    try:
        loc = _page.locator(selector).nth(index)
        loc.wait_for(state="visible", timeout=10000)
        loc.click()
        time.sleep(0.5)
        return f"已点击：{selector}"
    except Exception as exc:  # noqa: BLE001
        return _diagnose(f"点击 {selector}", selector, exc)


@tool(
    name="browser_fill",
    description="在输入框中填入文本（CSS 选择器定位；填密码等敏感字段请用户注意）",
    parameters={
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "CSS 选择器，如 '#username'、'input[name=\"password\"]'"},
            "text": {"type": "string", "description": "要填入的文本"},
        },
        "required": ["selector", "text"],
    },
    risk="medium",
)
@_in_browser_thread
def browser_fill(selector: str, text: str) -> str:
    err = _ensure_browser()
    if err:
        return err
    selector = _coerce_selector(selector)
    try:
        loc = _page.locator(selector).first
        loc.wait_for(state="visible", timeout=10000)
        loc.fill(text)
        return f"已填入 {selector}"
    except Exception as exc:  # noqa: BLE001
        return _diagnose(f"填入 {selector}", selector, exc)


@tool(
    name="browser_press",
    description="在当前页面或指定元素上按键（如 Enter、Tab、Escape；常用于提交表单）",
    parameters={
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "按键名，如 'Enter'、'Tab'、'Escape'、'F5'"},
            "selector": {"type": "string", "description": "可选，聚焦到该元素后再按键"},
        },
        "required": ["key"],
    },
    risk="medium",
)
@_in_browser_thread
def browser_press(key: str, selector: str = "") -> str:
    err = _ensure_browser()
    if err:
        return err
    try:
        if selector:
            _page.locator(_coerce_selector(selector)).first.press(key)
        else:
            _page.keyboard.press(key)
        time.sleep(0.5)
        return f"已按键：{key}"
    except Exception as exc:  # noqa: BLE001
        return f"按键 {key} 失败：{exc}"


@tool(
    name="browser_wait",
    description="等待指定毫秒数（页面加载/跳转后的缓冲）",
    parameters={
        "type": "object",
        "properties": {
            "ms": {"type": "integer", "description": "等待毫秒数，如 2000"},
        },
        "required": ["ms"],
    },
    risk="low",
)
@_in_browser_thread
def browser_wait(ms: int = 1000) -> str:
    time.sleep(max(0, int(ms or 0)) / 1000.0)
    return f"已等待 {ms} 毫秒"


@tool(
    name="browser_extract",
    description="提取当前页面文本内容；selector 为空时提取整页正文，填表格选择器时可返回表格数据（最多前50行）",
    parameters={
        "type": "object",
        "properties": {
            "selector": {"type": "string", "description": "可选，CSS 选择器，如 'table'、'#content'"},
            "limit": {"type": "integer", "description": "最多返回字符数，默认3000"},
        },
        "required": [],
    },
    risk="low",
)
@_in_browser_thread
def browser_extract(selector: str = "", limit: int = 3000) -> str:
    err = _ensure_browser()
    if err:
        return err
    try:
        if selector:
            loc = _page.locator(selector).first
            loc.wait_for(state="visible", timeout=8000)
            text = loc.inner_text(timeout=8000)
        else:
            text = _page.inner_text("body", timeout=8000)
        text = (text or "").strip()
        if len(text) > limit:
            text = text[:limit] + f"\n...（内容过长已截断，共{len(text)}字）"
        return f"当前标题：{_page.title()}\n\n{text}" if text else "页面没有可提取的文本"
    except Exception as exc:  # noqa: BLE001
        # selector 提取失败时自动降级整页提取，避免 Agent 反复死磕 selector 超时
        if selector:
            try:
                text = _page.inner_text("body", timeout=8000)
                text = (text or "").strip()
                if len(text) > limit:
                    text = text[:limit] + f"\n...（内容过长已截断，共{len(text)}字）"
                return (
                    f"（selector {selector!r} 不可用，已改用整页提取）\n"
                    f"当前标题：{_page.title()}\n\n{text}" if text
                    else f"（selector {selector!r} 不可用，整页也无文本）"
                )
            except Exception:  # noqa: BLE001
                pass
        return _diagnose("提取失败", selector, exc)


@tool(
    name="browser_screenshot",
    description="截取当前浏览器页面，保存到 data/screenshots/ 并返回路径",
    parameters={
        "type": "object",
        "properties": {
            "full_page": {"type": "boolean", "description": "是否截取整页（默认false，只截可视区）"},
        },
        "required": [],
    },
    risk="low",
)
@_in_browser_thread
def browser_screenshot(full_page: bool = False) -> str:
    err = _ensure_browser()
    if err:
        return err
    try:
        now = datetime.datetime.now()
        fname = f"browser_{now.year}{now.month:02d}{now.day:02d}_{now.hour:02d}{now.minute:02d}{now.second:02d}.png"
        save_path = os.path.join(_screenshots_dir(), fname)
        _page.screenshot(path=save_path, full_page=bool(full_page))
        return f"已截取浏览器页面，保存到：{save_path}"
    except Exception as exc:  # noqa: BLE001
        return f"截图失败：{exc}"


@tool(
    name="browser_download",
    description="在浏览器中下载当前页面触发的文件（若提供 URL 则直接访问并下载），保存到 data/downloads/ 并返回文件路径",
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "可选，直接访问该 URL 并下载返回的文件"},
            "save_name": {"type": "string", "description": "可选，自定义保存文件名（含扩展名）"},
        },
        "required": [],
    },
    risk="medium",
)
@_in_browser_thread
def browser_download(url: str = "", save_name: str = "") -> str:
    err = _ensure_browser()
    if err:
        return err
    try:
        with _page.expect_download(timeout=45000) as dl_info:
            if url:
                try:
                    _page.goto(url, wait_until="domcontentloaded", timeout=30000)
                except Exception:  # noqa: BLE001
                    # 直接导航到下载链接时 Playwright 会抛 "Download is starting"，
                    # 但 download 事件仍会正常触发，继续等待保存即可。
                    pass
                time.sleep(1.5)
        dl = dl_info.value
        fname = save_name or os.path.basename(dl.suggested_filename or f"download_{int(time.time())}")
        save_path = os.path.join(_download_dir(), fname)
        dl.save_as(save_path)
        return f"已下载文件：{save_path}"
    except Exception as exc:  # noqa: BLE001
        return f"下载失败（可能页面没有触发文件下载）：{exc}"


@tool(
    name="browser_close",
    description="关闭可控浏览器实例（释放资源；下次 browser_open 会重新启动）",
    parameters={"type": "object", "properties": {}},
    risk="low",
)
@_in_browser_thread
def browser_close() -> str:
    global _browser, _context, _page, _ready
    try:
        if _context is not None:
            _context.close()
        if _browser is not None:
            _browser.close()
    except Exception:  # noqa: BLE001
        pass
    _cleanup_pw()
    _browser = _context = _page = None
    _ready = False
    return "已关闭浏览器实例"


def _coerce_selector(selector: str) -> str:
    """把 Agent 常见的不规范选择器自动转成合法 Playwright CSS。

    - 'button "搜索"' → 'button:has-text("搜索")'
    - 'a "登录"' → 'a:has-text("登录")'
    - 其余原样返回。
    """
    s = (selector or "").strip()
    m = re.match(r'^([a-zA-Z][\w-]*)\s+"([^"]+)"$', s)
    if m:
        return f'{m.group(1)}:has-text("{m.group(2)}")'
    return s


def _element_hints(limit: int = 20) -> list:
    """收集当前页面可交互元素（input/textarea/select/button/a）的『可直接使用』选择器。

    每个元素输出：推荐选择器（优先 id > name > placeholder > class > :has-text 文本）
    + 简要属性描述，供上层 Agent 换选择器时复制即用。返回字符串列表。
    """
    try:
        data = _page.evaluate(
            """() => {
                const out = [];
                const seen = new Set();
                const push = (el) => {
                    const tag = el.tagName.toLowerCase();
                    const id = el.id || '';
                    const name = el.getAttribute('name') || '';
                    const placeholder = el.getAttribute('placeholder') || '';
                    const cls = (typeof el.className === 'string' ? el.className : '') || '';
                    const text = (el.innerText || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 30);
                    let rec = tag;
                    if (id) rec = tag + '#' + id;
                    else if (name) rec = tag + '[name="' + name + '"]';
                    else if (placeholder) rec = tag + '[placeholder="' + placeholder + '"]';
                    else if (cls) rec = tag + '.' + cls.split(/\s+/).filter(Boolean).join('.');
                    else if (text) rec = tag + ':has-text("' + text + '")';
                    const parts = [];
                    if (id) parts.push('id=' + id);
                    if (name) parts.push('name=' + name);
                    if (placeholder) parts.push('placeholder=' + placeholder);
                    if (text) parts.push('text="' + text + '"');
                    const sig = rec + ' | ' + parts.join(' ');
                    if (!seen.has(sig)) { seen.add(sig); out.push(rec + '   # ' + parts.join(' ')); }
                };
                document.querySelectorAll('input, textarea, select, button, a').forEach(push);
                return out;
            }"""
        )
    except Exception:  # noqa: BLE001
        return []
    hints = [f"  {item}" for item in (data or [])[:limit]]
    if data and len(data) > limit:
        hints.append(f"  ...（共 {len(data)} 个可交互元素，仅列前 {limit} 个）")
    return hints


def _diagnose(action: str, selector: str = "", exc: Exception = None) -> str:
    """失败诊断文本：包含当前 URL / 标题 / 相关元素提示，禁止只回一句『失败』。"""
    lines = [f"{action}失败：{exc}"]
    try:
        if _page is not None and not _page.is_closed():
            lines.append(f"当前URL：{_page.url}")
            lines.append(f"当前标题：{_page.title()}")
            hints = _element_hints(12)
            if hints:
                lines.append("页面可交互元素提示（可改用这些选择器）：")
                lines.extend(hints)
            else:
                lines.append("（页面暂无可交互元素；可用 browser_screenshot 观察实际页面）")
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(lines)


@tool(
    name="browser_inspect",
    description="检查当前页面真实 DOM：返回当前 URL、标题、页面中所有 input/button/链接/输入框的关键选择器清单（id/name/placeholder/class/文本）及正文片段；用于定位元素或在操作失败后换选择器",
    parameters={"type": "object", "properties": {}},
    risk="low",
)
@_in_browser_thread
def browser_inspect() -> str:
    err = _ensure_browser()
    if err:
        return err
    try:
        lines = [f"当前URL：{_page.url}", f"当前标题：{_page.title()}"]
        hints = _element_hints(30)
        if hints:
            lines.append("可交互元素（选择器提示）：")
            lines.extend(hints)
        else:
            lines.append("（页面暂无可交互元素）")
        text = (_page.inner_text("body", timeout=8000) or "").strip()
        if len(text) > 1500:
            text = text[:1500] + f"...（正文过长，共{len(text)}字）"
        if text:
            lines.append("正文片段：")
            lines.append(text)
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"inspect 失败：{exc}"
