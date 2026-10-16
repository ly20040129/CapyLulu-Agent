"""专项技能运行时：把「技能广场」里的内置技能变成 LLM 可调度的真实工具。

每个技能对应一个 skill_* 工具，注册进工具注册表后，任何 Agent（总代理/管家）都能
按描述在合适的场景调用，实现「AI 可调度技能」。
"""
from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from .registry import tool

# 常见文件类型分组（文件整理用）
_TYPE_GROUPS = {
    "图片": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"},
    "视频": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"},
    "音频": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"},
    "文档": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv"},
    "压缩包": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "代码": {".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".java", ".go", ".c", ".cpp", ".h"},
}

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"}
_TEXT_EXTS = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".py", ".js", ".ts", ".html", ".css", ".xml", ".log"}
_INVOICE_EXTS = {".pdf", ".png", ".jpg", ".jpeg"}
_INVOICE_KW = ("发票", "invoice", "票")


def _safe_dir(directory: str) -> Path | None:
    p = Path(directory)
    if not p.exists() or not p.is_dir():
        return None
    return p


@tool(
    name="skill_organize_files",
    description=(
        "技能-文件整理：把目录下第一层文件按类型（图片/视频/音频/文档/压缩包/代码/其他）"
        "或指定关键字归类到子文件夹。mode=type 按扩展名分组；mode=keyword 按 keywords 分组"
        "（文件名包含任一关键字即归入对应文件夹）。只处理该目录第一层文件，不动子目录。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "要整理的目录绝对路径"},
            "mode": {"type": "string", "description": "type=按类型分组 / keyword=按关键字分组", "enum": ["type", "keyword"]},
            "keywords": {"type": "string", "description": "mode=keyword 时用，逗号分隔的关键字，每个关键字建一个文件夹"},
        },
        "required": ["directory", "mode"],
    },
    risk="medium",
)
def skill_organize_files(directory: str, mode: str = "type", keywords: str = "") -> str:
    root = _safe_dir(directory)
    if root is None:
        return f"目录不存在: {directory}"
    mode = (mode or "type").strip().lower()
    kw = [k.strip() for k in (keywords or "").replace("，", ",").split(",") if k.strip()]
    if mode == "keyword" and not kw:
        return "keyword 模式需要提供 keywords"
    moved: list[str] = []
    for f in root.iterdir():
        if not f.is_file():
            continue
        if mode == "type":
            ext = f.suffix.lower()
            group = next((g for g, exts in _TYPE_GROUPS.items() if ext in exts), "其他")
        else:
            hit = next((k for k in kw if k in f.name), None)
            group = hit or "其他"
        target = root / group
        target.mkdir(exist_ok=True)
        dst = target / f.name
        if dst.exists():
            dst = target / f"{f.stem}_{datetime.now().strftime('%H%M%S')}{f.suffix}"
        shutil.move(str(f), str(dst))
        moved.append(f"{f.name} → {group}/{dst.name}")
    if not moved:
        return f"{directory} 下没有可整理的文件"
    return "整理完成：\n" + "\n".join(moved[:50]) + (("\n...(共 %d 个文件)" % len(moved)) if len(moved) > 50 else "")


@tool(
    name="skill_doc_search",
    description=(
        "技能-文档语义搜索：按关键词在目录中递归检索文档。先匹配文件名，再对 txt/md/csv/json/"
        "yaml/py 等文本类文件搜索正文，返回匹配文件路径与命中片段。适合找包含某主题/关键词的本地资料。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "搜索目录绝对路径"},
            "keyword": {"type": "string", "description": "关键词（必填）"},
        },
        "required": ["directory", "keyword"],
    },
    risk="low",
)
def skill_doc_search(directory: str, keyword: str = "") -> str:
    root = _safe_dir(directory)
    if root is None:
        return f"目录不存在: {directory}"
    keyword = (keyword or "").strip()
    if not keyword:
        return "需要提供 keyword"
    hits: list[str] = []
    for p in root.rglob("*"):
        if p.is_file() and keyword in p.name:
            hits.append(f"[文件名] {p}")
    for p in root.rglob("*"):
        if len(hits) >= 50:
            hits.append("...(结果过多已截断)")
            break
        if p.is_file() and p.suffix.lower() in _TEXT_EXTS:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if keyword in text:
                idx = text.find(keyword)
                start = max(0, idx - 40)
                snippet = text[start: idx + len(keyword) + 40].replace("\n", " ")
                hits.append(f"[正文] {p}\n   …{snippet}…")
    return "\n".join(hits) if hits else f"未找到包含「{keyword}」的文档"


@tool(
    name="skill_image_search",
    description=(
        "技能-图片搜索：按文件名关键词/修改时间在目录中递归搜索图片（jpg/png/gif/webp 等）。"
        "days 填 0 或省略表示不限时间；填 N 表示只看最近 N 天修改的图片。"
        "适合找照片、截图、表情包等本地图片。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "搜索目录绝对路径"},
            "keyword": {"type": "string", "description": "文件名关键词（可省略）"},
            "days": {"type": "integer", "description": "只看最近 N 天修改的图片，0=不限时间"},
        },
        "required": ["directory"],
    },
    risk="low",
)
def skill_image_search(directory: str, keyword: str = "", days: int = 0) -> str:
    root = _safe_dir(directory)
    if root is None:
        return f"目录不存在: {directory}"
    kw = (keyword or "").strip()
    cutoff = None
    try:
        if days and int(days) > 0:
            cutoff = datetime.now() - timedelta(days=int(days))
    except (TypeError, ValueError):
        cutoff = None
    matches: list[str] = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in _IMAGE_EXTS:
            continue
        if kw and kw not in p.name:
            continue
        if cutoff is not None:
            try:
                mtime = datetime.fromtimestamp(p.stat().st_mtime)
            except OSError:
                continue
            if mtime < cutoff:
                continue
        matches.append(str(p))
        if len(matches) >= 50:
            matches.append("...(结果过多已截断)")
            break
    return "\n".join(matches) if matches else "未找到匹配的图片"


@tool(
    name="skill_invoice_scan",
    description=(
        "技能-发票识别：在目录中递归扫描发票文件（文件名含 发票/invoice/票 的 pdf/png/jpg），"
        "返回文件清单（路径/大小/修改时间）。识别票面金额等需要多模态视觉能力，当前先做文件级扫描。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "directory": {"type": "string", "description": "扫描目录绝对路径"},
        },
        "required": ["directory"],
    },
    risk="low",
)
def skill_invoice_scan(directory: str) -> str:
    root = _safe_dir(directory)
    if root is None:
        return f"目录不存在: {directory}"
    rows: list[str] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in _INVOICE_EXTS:
            name = p.name.lower()
            if any(k in name for k in _INVOICE_KW):
                try:
                    size_kb = p.stat().st_size / 1024
                    mtime = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                except OSError:
                    continue
                rows.append(f"{p}  ({size_kb:.0f} KB, {mtime})")
                if len(rows) >= 50:
                    rows.append("...(结果过多已截断)")
                    break
    return "\n".join(rows) if rows else f"{directory} 下未找到发票文件"


@tool(
    name="skill_image_edit",
    description=(
        "技能-图片处理：对单张图片执行缩放(scale 比例 0.1~5) / 裁剪(crop box=left,top,right,bottom) / "
        "格式转换(convert to_format=png/jpg/webp)。输出到原目录，文件名加 _edited 后缀，不覆盖原图。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "图片文件绝对路径"},
            "operation": {"type": "string", "description": "scale=缩放 / crop=裁剪 / convert=格式转换", "enum": ["scale", "crop", "convert"]},
            "scale": {"type": "number", "description": "operation=scale 时缩放比例，如 0.5 缩小一半"},
            "box": {"type": "string", "description": "operation=crop 时裁剪区域 left,top,right,bottom（像素）"},
            "to_format": {"type": "string", "description": "operation=convert 时目标格式 png/jpg/webp"},
        },
        "required": ["path", "operation"],
    },
    risk="medium",
)
def skill_image_edit(path: str, operation: str = "", scale: float = 1.0, box: str = "", to_format: str = "") -> str:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return f"文件不存在: {path}"
    op = (operation or "").strip().lower()
    try:
        from PIL import Image

        img = Image.open(p)
        img.load()
    except Exception as exc:
        return f"无法打开图片（可能不是图片或已损坏）: {exc}"
    out = p.with_name(f"{p.stem}_edited")
    try:
        if op == "scale":
            ratio = float(scale or 1.0)
            if ratio <= 0:
                return "scale 需大于 0"
            img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))))
            out = out.with_suffix(p.suffix)
            img.save(out)
            return f"已缩放为 {img.width}x{img.height}: {out}"
        if op == "crop":
            parts = [int(x.strip()) for x in (box or "").replace("，", ",").split(",")]
            if len(parts) != 4 or parts[0] >= parts[2] or parts[1] >= parts[3]:
                return "crop 需要 box=left,top,right,bottom 且 left<right、top<bottom"
            img = img.crop(tuple(parts))
            out = out.with_suffix(p.suffix)
            img.save(out)
            return f"已裁剪为 {img.width}x{img.height}: {out}"
        if op == "convert":
            fmt = (to_format or "").strip().lstrip(".").lower()
            if fmt not in ("png", "jpg", "jpeg", "webp"):
                return "convert 需要 to_format=png/jpg/webp"
            out = out.with_suffix("." + ("jpeg" if fmt == "jpg" else fmt))
            img.save(out)
            return f"已转换为 {fmt}: {out}"
    except Exception as exc:
        return f"图片处理失败: {exc}"
    return "operation 仅支持 scale / crop / convert"
