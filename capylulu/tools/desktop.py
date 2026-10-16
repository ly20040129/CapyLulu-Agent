"""桌面助手工具：时间、系统信息、打开路径/网页、桌面列表、文本检索。"""
import os
import platform
import webbrowser
from datetime import datetime
from pathlib import Path

from .registry import tool


def _desktop() -> Path:
    home = Path.home()
    for name in ("Desktop", "桌面"):
        p = home / name
        if p.exists():
            return p
    return home


@tool(
    name="now_datetime",
    description="获取当前本地日期和时间",
    parameters={"type": "object", "properties": {}},
    risk="low",
)
def now_datetime() -> str:
    """当前时间。"""
    now = datetime.now()
    # 避免 strftime 格式串含中文字符在 Windows 的兼容坑，改用 f-string 拼接
    return f"{now.year}-{now.month:02d}-{now.day:02d} {now.hour:02d}:{now.minute:02d}:{now.second:02d} 星期" + "一二三四五六日"[now.weekday()]


@tool(
    name="system_info",
    description="查看本机系统、主机名、CPU 架构等基本信息",
    parameters={"type": "object", "properties": {}},
    risk="low",
)
def system_info() -> str:
    """只读系统概况，不含隐私扫描。"""
    return (
        f"系统: {platform.system()} {platform.release()}\n"
        f"版本: {platform.version()}\n"
        f"机器: {platform.machine()}\n"
        f"处理器: {platform.processor()}\n"
        f"主机名: {platform.node()}\n"
        f"Python: {platform.python_version()}\n"
        f"用户目录: {Path.home()}\n"
        f"工作目录: {Path.cwd()}"
    )


@tool(
    name="list_desktop",
    description="列出用户桌面上的文件和文件夹",
    parameters={"type": "object", "properties": {}},
    risk="low",
)
def list_desktop() -> str:
    """桌面目录一览。"""
    d = _desktop()
    items = sorted(d.iterdir())
    if not items:
        return f"桌面是空的：{d}"
    lines = [f"桌面路径: {d}"]
    for item in items[:80]:
        tag = "[目录]" if item.is_dir() else "[文件]"
        lines.append(f"{tag} {item.name}")
    if len(items) > 80:
        lines.append("...(已截断)")
    return "\n".join(lines)


@tool(
    name="open_path",
    description="用系统默认程序打开文件或文件夹（资源管理器/关联应用）",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "要打开的路径"}},
        "required": ["path"],
    },
    risk="medium",
)
def open_path(path: str) -> str:
    """打开本地路径。"""
    p = Path(path).expanduser()
    if not p.exists():
        return f"路径不存在: {path}"
    os.startfile(str(p))  # Windows
    return f"已打开: {p}"


@tool(
    name="open_url",
    description="用默认浏览器打开一个 http/https 网址",
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string", "description": "网址"}},
        "required": ["url"],
    },
    risk="medium",
)
def open_url(url: str) -> str:
    """打开网页。"""
    if not url.startswith(("http://", "https://")):
        return "只允许 http/https 链接"
    webbrowser.open(url)
    return f"已在浏览器打开: {url}"


@tool(
    name="append_file",
    description="在已有文本文件末尾追加内容（不覆盖）",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "追加的文字"},
        },
        "required": ["path", "content"],
    },
    risk="medium",
)
def append_file(path: str, content: str) -> str:
    """追加写入。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(content)
    return f"已追加 {len(content)} 字符到 {path}"


@tool(
    name="search_text",
    description="在指定文件中搜索包含关键词的行",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "keyword": {"type": "string", "description": "关键词"},
        },
        "required": ["path", "keyword"],
    },
    risk="low",
)
def search_text(path: str, keyword: str) -> str:
    """文件内文本检索。"""
    p = Path(path)
    if not p.is_file():
        return f"不是文件: {path}"
    hits = []
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if keyword in line:
            hits.append(f"{i}: {line.strip()[:200]}")
        if len(hits) >= 40:
            hits.append("...(已截断)")
            break
    return "\n".join(hits) if hits else "没有匹配行"


@tool(
    name="disk_usage",
    description="查看磁盘剩余空间（只读，不删除文件）",
    parameters={
        "type": "object",
        "properties": {"path": {"type": "string", "description": "盘符或路径，默认 C:\\"}},
    },
    risk="low",
)
def disk_usage(path: str = "C:\\") -> str:
    import shutil
    u = shutil.disk_usage(path or "C:\\")
    gb = lambda n: f"{n / 1024**3:.1f} GB"
    return f"{path} 总量 {gb(u.total)} / 已用 {gb(u.used)} / 剩余 {gb(u.free)}"


@tool(
    name="open_settings",
    description="打开 Windows 设置页，如系统、显示、关于本机",
    parameters={
        "type": "object",
        "properties": {
            "page": {"type": "string", "description": "可选：display / about / storage / empty 打开设置首页"},
        },
    },
    risk="medium",
)
def open_settings(page: str = "") -> str:
    uri = {
        "display": "ms-settings:display",
        "about": "ms-settings:about",
        "storage": "ms-settings:storagesense",
    }.get((page or "").lower(), "ms-settings:")
    os.startfile(uri)
    return f"已打开系统设置: {uri}"


@tool(
    name="launch_app",
    description="启动本机常见应用：记事本、计算器、画图、资源管理器",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "应用名，如 记事本 / 计算器 / explorer"}},
        "required": ["name"],
    },
    risk="medium",
)
def launch_app(name: str) -> str:
    alias = {
        "记事本": "notepad", "notepad": "notepad",
        "计算器": "calc", "calc": "calc",
        "画图": "mspaint", "paint": "mspaint",
        "资源管理器": "explorer", "explorer": "explorer",
        "cmd": "cmd",
    }
    exe = alias.get(name.strip().lower()) or alias.get(name.strip())
    if not exe:
        return f"暂不支持启动「{name}」，可以说：记事本、计算器、画图、资源管理器"
    os.startfile(exe)
    return f"已尝试启动: {exe}"


@tool(
    name="fetch_page",
    description="读取一个 http/https 网页的纯文本摘要（最多约 4000 字）",
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string", "description": "网址"}},
        "required": ["url"],
    },
    risk="medium",
)
def fetch_page(url: str) -> str:
    import re
    import urllib.request
    if not url.startswith(("http://", "https://")):
        return "只允许 http/https"
    req = urllib.request.Request(url, headers={"User-Agent": "Capylulu/0.1"})
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = resp.read(200000)
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:4000] or "(页面没有可读文字)"
