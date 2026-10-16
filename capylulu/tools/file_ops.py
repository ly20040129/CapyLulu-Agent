"""文件操作工具"""
import shutil
from pathlib import Path

from .registry import tool


@tool(
    name="read_file",
    description="读取指定路径的文件内容",
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
    """读文本，超 8000 字截断。"""
    p = Path(path)
    if not p.exists():
        return f"文件不存在: {path}"
    if p.is_dir():
        return f"路径是目录，不是文件: {path}"
    content = p.read_text(encoding="utf-8", errors="replace")
    if len(content) > 8000:
        content = content[:8000] + "\n...(内容过长已截断)"
    return content


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
    """覆盖写入，自动建父目录。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"已写入 {len(content)} 字符到 {path}"


@tool(
    name="list_dir",
    description="列出目录下的文件和子目录",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径，默认当前目录"},
        },
    },
    risk="low",
)
def list_dir(path: str = ".") -> str:
    """列出一层目录，标注文件/文件夹。"""
    p = Path(path)
    if not p.exists():
        return f"目录不存在: {path}"
    if not p.is_dir():
        return f"不是目录: {path}"
    items = []
    for item in sorted(p.iterdir()):
        prefix = "[目录] " if item.is_dir() else "[文件] "
        size = ""
        if item.is_file():
            try:
                size = f" ({item.stat().st_size} bytes)"
            except OSError:
                pass
        items.append(f"{prefix}{item.name}{size}")
    return "\n".join(items) if items else "(空目录)"


@tool(
    name="search_files",
    description="按文件名关键词搜索目录下的文件（递归）",
    parameters={
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "搜索目录"},
            "keyword": {"type": "string", "description": "文件名关键词"},
        },
        "required": ["directory", "keyword"],
    },
    risk="low",
)
def search_files(directory: str, keyword: str) -> str:
    """文件名模糊搜索，最多 50 条。"""
    p = Path(directory)
    if not p.exists():
        return f"目录不存在: {directory}"
    matches = []
    for item in p.rglob(f"*{keyword}*"):
        matches.append(str(item))
        if len(matches) >= 50:
            matches.append("...(结果过多已截断)")
            break
    return "\n".join(matches) if matches else "未找到匹配文件"


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
