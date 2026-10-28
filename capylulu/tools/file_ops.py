"""文件操作工具"""
import shutil
from pathlib import Path

from ..config import config
from .registry import tool


def _human_size(n: int) -> str:
    """把字节数转成带换算的人类可读大小，避免 LLM 口算换算出错。

    例：98884276 → '98884276 bytes (94.3 MB)'；不足 1KB 仅返回字节数。
    """
    try:
        n = int(n)
    except (TypeError, ValueError):
        return f"{n} bytes"
    raw = n
    size = float(n)
    unit = "bytes"
    for u in ("KB", "MB", "GB", "TB"):
        if size < 1024:
            break
        size /= 1024.0
        unit = u
    if unit == "bytes":
        return f"{raw} bytes"
    return f"{raw} bytes ({size:.1f} {unit})"


@tool(
    name="read_file",
    description="读取指定路径的文件内容；返回头部带文件总行数与总字符数（统计行数类任务无需另找工具）",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
        },
        "required": ["path"],
    },
    risk="low",
)
def read_file(path: str) -> str:
    """读文本，超 8000 字截断；头部附行数/字符数元信息，供行数统计等场景直接引用。"""
    p = Path(path)
    if not p.exists():
        parent = p.parent
        while parent and parent != parent.parent:
            cand = parent / p.name
            if cand.exists():
                return f"文件不存在: {path}；上级目录 {parent} 下存在同名文件 {cand}，如需要请改用该路径"
            parent = parent.parent
        return f"文件不存在: {path}"
    if p.is_dir():
        return f"路径是目录，不是文件: {path}"
    content = p.read_text(encoding="utf-8", errors="replace")
    lines = content.count("\n")
    if not content.endswith("\n") and content:
        lines += 1
    header = f"[文件共 {lines} 行 / {len(content)} 字符]"
    if len(content) > 8000:
        content = content[:8000] + "\n...(内容过长已截断，文件总行数见头部)"
    return header + "\n" + content


@tool(
    name="write_file",
    description="将内容写入指定路径的文件（覆盖写入）",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径"},
            "content": {"type": "string", "description": "写入内容"},
        },
        "required": ["path", "content"],
    },
    risk="medium",
)
def write_file(path: str, content: str) -> str:
    """覆盖写入，自动建父目录。内容含明显占位符（编号式/占位式）时拒绝写入，
    防止 Agent 把编造内容当成真实结果落盘。"""
    import re

    # 类 Unix 路径串台校验：Windows 环境禁止 Linux 风格绝对路径，
    # 防止 Agent 幻觉路径（如 /home/kk/...）被错误落到驱动器根目录脏目录。
    _norm = path.replace("\\", "/").strip().lower()
    if _norm.startswith(
        ("/home/", "/root/", "/tmp/", "/var/", "/usr/", "/etc/",
         "/opt/", "/users/", "/mnt/", "/data/", "/srv/")
    ):
        return (
            f"拒绝写入：路径 {path!r} 是 Linux/Unix 风格路径，当前是 Windows 环境。"
            "请改用 Windows 绝对路径（如 E:\\work\\file.txt）或工作区相对路径（如 data/output/file.txt）。"
        )

    p = Path(path)
    stripped = content.strip()
    if len(stripped) < 10:
        return (
            "拒绝写入：content 过短（疑似工具调用残片/无意义内容）。"
            "必须写入有意义的真实数据；没有真实数据时不要调用本工具，直接如实汇报。"
        )
    placeholder = re.compile(
        r"(新闻标题|标题|内容|正文|提取到的[^，。\n]{0,10}标题|占位|示例文本)([0-9０-９]|\s*\d|$)"
    )
    if placeholder.search(stripped):
        return (
            "拒绝写入：content 疑似占位符/编造内容"
            f"（命中模式：{placeholder.search(content.strip()).group(0)!r}）。"
            "必须写入真实数据；没有真实数据时不要调用本工具，直接如实汇报未取得数据。"
        )
    if any(k in stripped for k in ("本步骤依赖前置步骤", "前置步骤的真实执行结果", "【步骤", "步骤执行结果】")):
        return (
            "拒绝写入：content 是任务上下文注入文本（前置步骤说明），不是本步骤应保存的真实数据。"
            "请只写入从真实执行中提取到的目标内容；没有目标内容时不要调用本工具，直接如实汇报。"
        )
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"已写入 {len(content)} 字符到 {path}"


@tool(
    name="list_dir",
    description="列出目录下的文件和子目录，支持按名称或修改时间排序（sort=name/mtime，order=asc/desc）",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径，默认当前目录"},
            "sort": {"type": "string", "enum": ["name", "mtime"], "description": "排序方式：name=按名称（默认），mtime=按修改时间"},
            "order": {"type": "string", "enum": ["asc", "desc"], "description": "排序方向：asc=升序（默认），desc=降序"},
        },
    },
    risk="low",
)
def list_dir(path: str = ".", sort: str = "name", order: str = "asc") -> str:
    """列出一层目录，标注文件/文件夹；支持按名称或修改时间排序。"""
    p = Path(path)
    if not p.exists():
        parent = p.parent
        while parent and parent != parent.parent:
            cand = parent / p.name
            if cand.exists() and cand.is_dir():
                return f"目录不存在: {path}；上级目录 {parent} 下存在同名目录 {cand}，如需要请改用该路径"
            parent = parent.parent
        return f"目录不存在: {path}"
    if not p.is_dir():
        return f"不是目录: {path}"
    items = list(p.iterdir())
    reverse = str(order).lower() == "desc"
    if str(sort).lower() == "mtime":
        items.sort(key=lambda x: x.stat().st_mtime, reverse=reverse)
    else:
        items.sort(key=lambda x: x.name.lower(), reverse=reverse)
    lines = []
    for item in items:
        prefix = "[目录] " if item.is_dir() else "[文件] "
        size = ""
        if item.is_file():
            try:
                size = f" ({_human_size(item.stat().st_size)})"
            except OSError:
                pass
        lines.append(f"{prefix}{item.name}{size}")
    return "\n".join(lines) if lines else "(空目录)"


def _name_match(name: str, key: str) -> bool:
    """文件名匹配：含通配符（* ? [）时按 glob 通配匹配，否则按子串匹配。"""
    if any(ch in key for ch in "*?["):
        import fnmatch
        return fnmatch.fnmatch(name, key)
    return key in name


@tool(
    name="search_files",
    description="按文件名关键词搜索目录下的文件（递归），支持按名称或修改时间排序（sort=name/mtime，order=asc/desc）；with_line_counts=true 时对文本文件附加行数，适合统计行数类任务，无需再逐个 read_file",
    parameters={
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "搜索目录"},
            "keyword": {"type": "string", "description": "文件名关键词，可用 | 分隔多个关键词（任一命中）；支持 * ? 通配符（如 *.txt、*发票*）"},
            "sort": {"type": "string", "enum": ["name", "mtime"], "description": "排序方式：name=按名称（默认），mtime=按修改时间"},
            "order": {"type": "string", "enum": ["asc", "desc"], "description": "排序方向：asc=升序（默认），desc=降序"},
            "with_line_counts": {"type": "boolean", "description": "是否附加文本文件行数（默认 false；统计行数时设 true）"},
        },
        "required": ["directory", "keyword"],
    },
    risk="low",
)
def search_files(directory: str, keyword: str, sort: str = "name", order: str = "asc", with_line_counts: bool = False) -> str:
    """文件名模糊搜索，最多 50 条；每条附带文件大小，避免 LLM 臆测。"""
    p = Path(directory)
    if not p.exists():
        return f"目录不存在: {directory}"
    # 支持多关键词：keyword 用 | 分隔（如 "发票|invoice"），任一命中即匹配
    keys = [k.strip() for k in str(keyword).replace("或", "|").split("|") if k.strip()]
    if not keys:
        return "关键词不能为空"
    matches = []
    for item in p.rglob("*"):
        if any(_name_match(item.name, k) for k in keys):
            try:
                mtime = item.stat().st_mtime
            except OSError:
                mtime = 0
            matches.append((mtime, item))
            if len(matches) >= 50:
                matches.append((0, "__(截断标记)__"))
                break
    reverse = str(order).lower() == "desc"
    if str(sort).lower() == "mtime":
        matches.sort(key=lambda t: t[0], reverse=reverse)
    else:
        matches.sort(key=lambda t: t[1].name.lower(), reverse=reverse)
    lines = []
    for mtime, item in matches:
        if getattr(item, "name", "") == "__(截断标记)__":
            lines.append("...(结果过多已截断)")
            continue
        try:
            extra = ""
            if with_line_counts and item.is_file():
                try:
                    with open(item, "r", encoding="utf-8", errors="replace") as fh:
                        cnt = sum(1 for _ in fh)
                    extra = f", {cnt} 行"
                except OSError:
                    extra = ""
            size = f" ({_human_size(item.stat().st_size)}{extra})" if item.is_file() else " (dir)"
        except OSError:
            size = ""
        lines.append(f"{item}{size}")
    return "\n".join(lines) if lines else "未找到匹配文件"


@tool(
    name="move_file",
    description="移动或重命名文件/目录",
    parameters={
        "type": "object",
        "properties": {
            "src": {"type": "string", "description": "源路径"},
            "dst": {"type": "string", "description": "目标路径"},
        },
        "required": ["src", "dst"],
    },
    risk="medium",
)
def move_file(src: str, dst: str) -> str:
    """移动或改名。"""
    s, d = Path(src), Path(dst)
    if not s.exists():
        return f"源文件不存在: {src}"
    d.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(s), str(d))
    return f"已移动 {src} → {dst}"


@tool(
    name="send_file",
    description="把文件复制到共享发送目录并生成下载链接，用于发送文件给用户（返回 /files/ 下载链接）",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "源文件绝对路径"},
        },
        "required": ["path"],
    },
    risk="medium",
)
def send_file(path: str) -> str:
    """复制文件到共享发送目录（data/send_files），返回下载 URL 与本地副本路径。

    文件名冲突时自动追加序号（保留扩展名），避免覆盖已有文件。
    下载 URL 形如 http://127.0.0.1:6661/files/<文件名>，由 main.py 静态挂载 /files 提供。
    """
    from urllib.parse import quote

    src = Path(path)
    if not src.exists():
        return f"文件不存在: {path}"
    if not src.is_file():
        return f"路径是目录，不是文件: {path}"

    send_dir = config.data_dir / "send_files"
    send_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_target(send_dir, src.name)
    try:
        shutil.copy2(str(src), str(target))
    except OSError as e:
        return f"复制文件失败: {e}"

    url_name = quote(target.name)
    return (
        f"已发送文件：{target.name}\n"
        f"下载链接：http://127.0.0.1:6661/files/{url_name}\n"
        f"本地副本：{target}"
    )


def _unique_target(directory: Path, name: str) -> Path:
    """目标路径：同名已存在时追加 (1)(2) 序号，保留扩展名。"""
    candidate = directory / name
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    i = 1
    while True:
        candidate = directory / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1
