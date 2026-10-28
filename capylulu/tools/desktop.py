"""桌面助手工具：时间、系统信息、打开路径/网页、桌面列表、文本检索。"""
import os
import platform
import re
import subprocess
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


def _app_start_menu_dirs() -> list:
    """开始菜单快捷方式根目录（系统级 + 用户级）。"""
    dirs = []
    pd = os.environ.get("ProgramData")
    if pd:
        dirs.append(os.path.join(pd, "Microsoft", "Windows", "Start Menu", "Programs"))
    ad = os.environ.get("APPDATA")
    if ad:
        dirs.append(os.path.join(ad, "Microsoft", "Windows", "Start Menu", "Programs"))
    return [d for d in dirs if os.path.isdir(d)]


# 常见中文名 -> App Paths 键名（纯"名字桥"，不含任何路径；路径仍由注册表/开始菜单动态解析）。
# 用途：卸载表 DisplayIcon 常为 .ico 而非 exe，App Paths 键名又是英文，此表把常见中文名桥到
# App Paths 键名，使「钉钉」这类中文名能被运行时检索到。未在表内的应用照常被全量扫描发现。
_APP_NAME_BRIDGE = {
    "钉钉": "DingTalk.exe",
    "企业微信": "WXWork.exe",
    "微信": "WeChat.exe",
    "qq": "QQ.exe",
    "tim": "TIM.exe",
    "腾讯会议": "wemeetapp.exe",
    "网易云音乐": "cloudmusic.exe",
    "网易云": "cloudmusic.exe",
    "qq音乐": "QQMusic.exe",
    "酷狗音乐": "KuGou.exe",
    "百度网盘": "BaiduNetdisk.exe",
    "百度云": "BaiduNetdisk.exe",
    "steam": "steam.exe",
    "谷歌浏览器": "chrome.exe",
    "火狐": "firefox.exe",
}


# ---- 运行时应用索引：全量扫描本机已安装应用，不写死任何路径，适配不同电脑 ----

_app_index: dict | None = None  # 模块级缓存


def _norm_key(s: str) -> str:
    """应用名归一化：去空白/点号、转小写，用于模糊匹配。"""
    return re.sub(r"[\s.]+", "", (s or "").lower())


def _scan_app_index() -> dict:
    """扫描本机已安装应用，返回 {归一化名: {"display": 展示名, "target": 启动目标, "kind": "exe"|"lnk"}}。

    数据来源（全部运行时检索，跨机器通用）：
    1. App Paths 注册表：键名即可执行文件名（DingTalk.exe 等），值即 exe 绝对路径；
    2. 卸载注册表：DisplayName（中文名）+ DisplayIcon / InstallLocation，提供中文名到 exe 的映射；
    3. 开始菜单快捷方式：*.lnk，覆盖未写注册表的绿色/便携应用。
    """
    import winreg

    index: dict[str, dict] = {}

    def _add(display: str, target: str, kind: str) -> None:
        key = _norm_key(display) or _norm_key(os.path.splitext(os.path.basename(target))[0])
        if not key or "卸载" in key or "uninstall" in key:
            return
        if key not in index:  # 先到先得：App Paths > 卸载表 > 开始菜单
            index[key] = {"display": display, "target": target, "kind": kind}

    # 1) App Paths 注册表
    app_paths_roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    for hkey, sub in app_paths_roots:
        try:
            with winreg.OpenKey(hkey, sub) as root_key:
                i = 0
                while True:
                    try:
                        entry = winreg.EnumKey(root_key, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(root_key, entry) as ek:
                            exe, _ = winreg.QueryValueEx(ek, "")
                    except OSError:
                        continue
                    if exe and os.path.isfile(exe):
                        _add(os.path.splitext(entry)[0], exe, "exe")
        except OSError:
            continue

    # 2) 卸载注册表（中文显示名 -> exe/快捷方式）
    uninstall_roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hkey, sub in uninstall_roots:
        try:
            with winreg.OpenKey(hkey, sub) as root_key:
                i = 0
                while True:
                    try:
                        skey = winreg.EnumKey(root_key, i)
                    except OSError:
                        break
                    i += 1
                    try:
                        with winreg.OpenKey(root_key, skey) as ek:
                            display = ""
                            icon = ""
                            n = 0
                            while True:
                                try:
                                    vname, vval, _ = winreg.EnumValue(ek, n)
                                except OSError:
                                    break
                                n += 1
                                if vname == "DisplayName":
                                    display = str(vval or "")
                                elif vname == "DisplayIcon":
                                    icon = str(vval or "")
                    except OSError:
                        continue
                    if not display:
                        continue
                    # 剥离引号（部分安装器写入带引号路径）与 ",0" 之类图标序号
                    icon = re.sub(r",\d+$", "", (icon or "").strip().strip('"').strip("'"))
                    if icon.lower().endswith((".exe", ".lnk")) and os.path.isfile(icon):
                        _add(display, icon, "lnk" if icon.lower().endswith(".lnk") else "exe")
        except OSError:
            continue

    # 3) 开始菜单快捷方式
    for root in _app_start_menu_dirs():
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                if not fn.lower().endswith(".lnk"):
                    continue
                _add(os.path.splitext(fn)[0], os.path.join(dirpath, fn), "lnk")

    # 4) 中文名桥注入：常见中文名 -> App Paths 键名（路径不变，仅补名字）
    for zh, exe_key in _APP_NAME_BRIDGE.items():
        zhk = _norm_key(zh)
        if zhk in index:
            continue
        for cand in (_norm_key(exe_key), _norm_key(os.path.splitext(exe_key)[0])):
            if cand in index:
                index[zhk] = index[cand]
                break
    return index


def _get_app_index(force: bool = False) -> dict:
    """应用索引（模块级缓存；force=True 强制重扫，供安装新应用后刷新）。"""
    global _app_index
    if _app_index is None or force:
        _app_index = _scan_app_index()
    return _app_index


def _find_app_by_index(name: str) -> dict | None:
    """在应用索引中按名称查找：精确匹配优先，其次包含匹配（取最短命中）。"""
    key = _norm_key(name)
    if not key:
        return None
    index = _get_app_index()
    hit = index.get(key)
    if hit:
        return hit
    best = None
    for k, v in index.items():
        if len(key) >= 2 and (key in k or k in key):
            if best is None or len(k) < len(best[0]):
                best = (k, v)
    return best[1] if best else None


def _launch_installed_app(name: str) -> str:
    """启动任意已安装应用：运行时应用索引 -> cmd start 兜底。

    索引由 _scan_app_index 动态扫描（App Paths / 卸载注册表 / 开始菜单），
    不依赖任何写死路径或白名单，换电脑/换安装位置同样可用。
    返回统一中文结果文本；失败文本含「未能找到应用」，供自动任务失败识别。
    """
    key = (name or "").strip()
    if not key:
        return "未提供应用名"
    if not re.fullmatch(r"[\w\u4e00-\u9fff .\-+()（）]+", key):
        return f"应用名「{key}」包含非法字符，无法启动"
    # 1) 运行时应用索引（App Paths + 卸载注册表 + 开始菜单，精确/包含匹配）
    hit = _find_app_by_index(key)
    if hit:
        try:
            os.startfile(hit["target"])
            return f"✓ 已启动 {key}（{hit['target']}）"
        except Exception as exc:  # noqa: BLE001
            return f"启动 {key} 失败：{exc}"
    # 2) cmd start 兜底（可按名称解析部分开始菜单项 / PATH 程序）
    try:
        proc = subprocess.run(
            ["cmd", "/c", "start", "", key],
            capture_output=True, text=True, timeout=8,
        )
        err = (proc.stderr or "") + (proc.stdout or "")
        if "找不到" in err or "not recognized" in err.lower():
            return f"未能找到应用「{key}」，请确认已安装"
        return f"✓ 已尝试启动 {key}"
    except subprocess.TimeoutExpired:
        # start 是异步的，超时不代表失败，按已尝试处理
        return f"✓ 已尝试启动 {key}"
    except Exception as exc:  # noqa: BLE001
        return f"未能找到应用「{key}」，请确认已安装（{exc}）"


@tool(
    name="list_installed_apps",
    description="列出本机已安装的应用（扫描 App Paths 注册表、卸载注册表、开始菜单快捷方式），可按关键词过滤，返回应用名列表。用于自动任务补参/启动前确认应用是否存在",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "可选关键词，仅返回名称包含该词的应用；为空返回全部（最多 50 个）",
            },
        },
    },
    risk="low",
)
def list_installed_apps(keyword: str = "") -> str:
    """检索本机已安装应用名列表（运行时扫描，不依赖写死路径）。"""
    index = _get_app_index()
    kw = _norm_key(keyword)
    names = sorted(
        v["display"] for k, v in index.items()
        if not kw or kw in k or k in kw
    )
    if not names:
        return "本机未检索到应用" if not keyword else f"未检索到包含「{keyword}」的应用"
    limit = 50
    shown = names[:limit]
    tail = f"…（共 {len(names)} 个）" if len(names) > limit else ""
    return "、".join(shown) + tail


@tool(
    name="launch_app",
    description="启动本机已安装的应用，支持任意已安装软件：记事本、计算器、画图、资源管理器、钉钉、微信、QQ、浏览器等",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string", "description": "应用名，如 钉钉 / 微信 / 记事本 / 计算器"}},
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
    key = (name or "").strip()
    exe = alias.get(key.lower()) or alias.get(key)
    if exe:
        try:
            os.startfile(exe)
            return f"已尝试启动: {exe}"
        except Exception as exc:  # noqa: BLE001
            return f"启动 {key} 失败：{exc}"
    # 非白名单：通用启动任意已安装应用
    return _launch_installed_app(key)


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
