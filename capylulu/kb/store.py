"""知识库：库与文档管理（data/kb/<库名>/）。

- 库管理：新建 / 删除 / 列表（meta.json 记录元信息，docs/ 存文档原文）
- 文档导入：txt / md / csv / json / yml / log / py 等文本类直接入库；
  pdf 优先用 pypdf 解析（环境已安装 6.x），未安装时抛出明确错误提示安装 pypdf。
- 导入时文本切块（chunk），并重建库内 index.json（块级索引，供 index.py 检索）。

全部数据位于 <data_dir>/kb/ 下，不触碰系统路径；refresh_paths() 与其它模块对齐。
"""
from __future__ import annotations

import base64
import io
import json
import re
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path

from ..config import config

KB_ROOT: Path = config.data_dir / "kb"

_TEXT_EXTS = {
    ".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".log",
    ".py", ".js", ".ts", ".html", ".xml", ".ini", ".toml",
    ".sh", ".ps1", ".conf", ".svg",
}


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global KB_ROOT
    KB_ROOT = config.data_dir / "kb"


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _safe_name(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r'[\\/:*?"<>|\r\n]+', "_", text)
    return text[:80]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def _kb_dir(kb: str) -> Path:
    kb = _safe_name(kb)
    d = KB_ROOT / kb
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta_path(kb_dir: Path) -> Path:
    return kb_dir / "meta.json"


def _docs_dir(kb_dir: Path) -> Path:
    d = kb_dir / "docs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_path(kb_dir: Path) -> Path:
    return kb_dir / "index.json"


def _read_json(p: Path, default) -> dict | list | None:
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def _write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------- 库管理 ----------------

def list_kbs() -> list[dict]:
    """列出全部知识库及统计信息。"""
    if not KB_ROOT.exists():
        return []
    rows: list[dict] = []
    for d in sorted(KB_ROOT.iterdir()):
        if not d.is_dir():
            continue
        meta = _read_json(_meta_path(d), None)
        if not isinstance(meta, dict):
            continue
        docs = meta.get("docs", [])
        rows.append({
            "name": meta.get("name", d.name),
            "doc_count": len(docs),
            "chunk_count": sum(int(x.get("chunk_count", 0)) for x in docs),
            "created_at": meta.get("created_at", ""),
            "updated_at": meta.get("updated_at", ""),
        })
    return rows


def create_kb(name: str) -> dict:
    """新建知识库。库名已存在时直接返回现有库信息。"""
    name = (name or "").strip()
    if not name:
        raise ValueError("知识库名称不能为空")
    d = _kb_dir(name)
    meta_path = _meta_path(d)
    meta = _read_json(meta_path, None)
    if isinstance(meta, dict):
        return {"name": meta.get("name", name), "created": False, "message": f"知识库「{name}」已存在"}
    _docs_dir(d)
    _write_json(meta_path, {
        "name": _safe_name(name),
        "created_at": now_str(),
        "updated_at": now_str(),
        "docs": [],
    })
    _write_json(_index_path(d), {"chunks": []})
    return {"name": _safe_name(name), "created": True, "message": f"知识库「{name}」已创建"}


def delete_kb(name: str) -> bool:
    """删除知识库（仅限 KB_ROOT 内目录，防路径逃逸）。"""
    name = _safe_name(name)
    d = (KB_ROOT / name).resolve()
    if not str(d).startswith(str(KB_ROOT.resolve())) or not d.is_dir():
        return False
    if d == KB_ROOT.resolve():
        return False
    shutil.rmtree(d, ignore_errors=True)
    return not d.exists()


# ---------------- 文档管理 ----------------

def list_docs(kb: str) -> list[dict]:
    """列出库内文档。"""
    meta = _read_json(_meta_path(_kb_dir(kb)), None)
    if not isinstance(meta, dict):
        return []
    return list(meta.get("docs", []))


def get_chunks(kb: str) -> list[dict]:
    """读取库内全部文本块（index.json）。"""
    idx = _read_json(_index_path(_kb_dir(kb)), None)
    if not isinstance(idx, dict):
        return []
    return list(idx.get("chunks", []))


def _parse_pdf_bytes(data: bytes) -> str:
    """用 pypdf 解析 PDF；未安装时给出明确错误。"""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "未安装 pypdf，无法解析 PDF。请先执行：pip install pypdf，"
            "或改用 txt / md / csv / json 等文本格式导入。"
        ) from exc
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text = "\n".join(pages).strip()
    if not text:
        raise RuntimeError("PDF 无可提取文本（可能是扫描件），请使用 OCR 后转为文本再导入。")
    return text


def _read_doc_text(name: str, src_path: Path | None = None,
                   content: str | None = None, content_b64: str | None = None) -> str:
    """按来源读取文档原始文本（文本类直读 / pdf 走 pypdf）。"""
    ext = Path(name).suffix.lower()
    if src_path is not None:
        p = Path(src_path)
        if not p.exists():
            raise FileNotFoundError(f"文件不存在：{p}")
        data = p.read_bytes()
        if ext == ".pdf":
            return _parse_pdf_bytes(data)
        return data.decode("utf-8", errors="replace")
    if content_b64:
        data = base64.b64decode(content_b64)
        if ext == ".pdf":
            return _parse_pdf_bytes(data)
        return data.decode("utf-8", errors="replace")
    if content is not None:
        if ext == ".pdf":
            return _parse_pdf_bytes(content.encode("utf-8"))
        return str(content)
    raise ValueError("缺少文档内容：请提供 src_path / content / content_b64 之一")


def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    """按固定窗口切块（带重叠，保留上下文连续性）。"""
    text = (text or "").strip()
    if not text:
        return []
    size = max(50, int(size or 500))
    overlap = min(size // 2, max(0, int(overlap or 50)))
    chunks: list[str] = []
    n = len(text)
    i = 0
    while i < n:
        end = min(i + size, n)
        chunks.append(text[i:end])
        if end >= n:
            break
        i = max(i + 1, end - overlap)
    return chunks


def add_doc(kb: str, name: str = "", src_path: str | Path | None = None,
            content: str | None = None, content_b64: str | None = None) -> dict:
    """导入文档：文本直接入库 / pdf 走 pypdf；切块并重建索引。"""
    if not (kb or "").strip():
        raise ValueError("知识库名称不能为空")
    create_kb(kb)
    d = _kb_dir(kb)
    meta = _read_json(_meta_path(d), None) or {"docs": []}

    if src_path is not None:
        p = Path(src_path)
        name = (name or p.name).strip()
    name = _safe_name(name or "doc")
    if not Path(name).suffix:
        name = name + ".txt"

    text = _read_doc_text(name, src_path=Path(src_path) if src_path else None,
                          content=content, content_b64=content_b64)
    if not text.strip():
        raise ValueError(f"文档「{name}」内容为空，无法导入")

    chunks = chunk_text(text)
    doc_id = _new_id("doc")
    safe = _safe_name(name)
    doc_file = _docs_dir(d) / f"{doc_id}_{safe}"
    doc_file.write_text(text, encoding="utf-8")

    docs = [x for x in meta.get("docs", [])]
    docs.append({
        "doc_id": doc_id,
        "name": name,
        "size": len(text.encode("utf-8")),
        "chunk_count": len(chunks),
        "ext": Path(name).suffix.lower(),
        "imported_at": now_str(),
    })
    meta["docs"] = docs
    meta["updated_at"] = now_str()
    _write_json(_meta_path(d), meta)
    rebuild_index(kb)
    return {"doc_id": doc_id, "name": name, "chunk_count": len(chunks),
            "size": len(text.encode("utf-8")), "message": f"文档「{name}」已导入（{len(chunks)} 块）"}


def rebuild_index(kb: str) -> None:
    """全量重建库内块索引（遍历 docs 原文重切，保证与文档一致）。"""
    d = _kb_dir(kb)
    chunks: list[dict] = []
    for rec in list_docs(kb):
        doc_file = _docs_dir(d) / f"{rec['doc_id']}_{_safe_name(rec['name'])}"
        if not doc_file.exists():
            continue
        text = doc_file.read_text(encoding="utf-8", errors="replace")
        for i, c in enumerate(chunk_text(text)):
            chunks.append({
                "doc_id": rec["doc_id"],
                "chunk_idx": i,
                "text": c,
                "name": rec["name"],
            })
    _write_json(_index_path(d), {"chunks": chunks})


def delete_doc(kb: str, doc_id: str) -> bool:
    """删除库内文档并重建索引。"""
    d = _kb_dir(kb)
    meta = _read_json(_meta_path(d), None) or {"docs": []}
    docs = list(meta.get("docs", []))
    target = next((x for x in docs if x.get("doc_id") == doc_id), None)
    if target is None:
        return False
    docs = [x for x in docs if x.get("doc_id") != doc_id]
    doc_file = _docs_dir(d) / f"{target['doc_id']}_{_safe_name(target['name'])}"
    if doc_file.exists():
        doc_file.unlink()
    meta["docs"] = docs
    meta["updated_at"] = now_str()
    _write_json(_meta_path(d), meta)
    rebuild_index(kb)
    return True
