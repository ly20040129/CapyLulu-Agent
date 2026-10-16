"""知识库工具：建库 / 导入文档 / 检索 / 问答（注册进主 registry）。"""
from __future__ import annotations

from ..kb import ask, index as kb_index
from ..kb import store as kb_store
from .registry import tool


@tool(
    name="kb_create",
    description="新建本地知识库（data/kb/<库名>/）。用于把一批资料沉淀为可检索问答的库。",
    parameters={
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "知识库名称"},
        },
        "required": ["name"],
    },
    risk="low",
)
def kb_create(name: str = "") -> str:
    if not (name or "").strip():
        return "知识库名称不能为空。"
    try:
        r = kb_store.create_kb(name)
        return r.get("message", str(r))
    except Exception as exc:  # noqa: BLE001
        return f"创建知识库失败：{exc}"


@tool(
    name="kb_add_doc",
    description=(
        "向知识库导入文档：支持本地路径（src_path，含 pdf，需 pypdf）或直接文本（content）。"
        "导入时自动切块并建索引。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "kb": {"type": "string", "description": "目标知识库名称（不存在会自动创建）"},
            "src_path": {"type": "string", "description": "本地文件绝对路径（txt/md/csv/json/pdf 等）"},
            "name": {"type": "string", "description": "文档显示名（留空取文件名）"},
            "content": {"type": "string", "description": "直接传入文档文本（txt/md/csv/json 等）"},
        },
        "required": ["kb"],
    },
    risk="low",
)
def kb_add_doc(kb: str = "", src_path: str = "", name: str = "", content: str = "") -> str:
    if not (kb or "").strip():
        return "请指定知识库名称。"
    if not (src_path or content or ""):
        return "请提供 src_path（本地路径）或 content（文本内容）。"
    try:
        r = kb_store.add_doc(kb, name=name,
                             src_path=src_path or None,
                             content=content if content else None)
        return r.get("message", str(r))
    except FileNotFoundError as exc:
        return f"导入失败：{exc}"
    except Exception as exc:  # noqa: BLE001
        return f"导入失败：{exc}"


@tool(
    name="kb_search",
    description="按关键词检索知识库文档块（top-k，带来源引用）。kb 留空则跨全部知识库检索。",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索关键词 / 问题"},
            "kb": {"type": "string", "description": "限定知识库名（留空检索全部库）"},
            "top_k": {"type": "integer", "description": "返回条数上限（默认 5）"},
        },
        "required": ["query"],
    },
    risk="low",
)
def kb_search(query: str = "", kb: str = "", top_k: int = 5) -> str:
    if not (query or "").strip():
        return "请输入检索关键词。"
    try:
        hits = kb_index.search(kb=kb, query=query, top_k=top_k)
        if not hits:
            return f"知识库中未找到与「{query}」相关的内容。"
        lines = [f"找到 {len(hits)} 条相关文档块（按相关度排序）："]
        for h in hits:
            lines.append(f"- [{h['source']}]（相关度 {h['score']}）：{(h.get('text') or '')[:120]}")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"知识库检索失败：{exc}"


@tool(
    name="kb_ask",
    description="基于知识库问答：检索 top-k 相关块 + LLM 生成回答（LLM 不可用时降级返回片段与来源）。",
    parameters={
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "要问的问题"},
            "kb": {"type": "string", "description": "限定知识库名（留空检索全部库）"},
            "top_k": {"type": "integer", "description": "检索片段数（默认 5）"},
        },
        "required": ["question"],
    },
    risk="low",
)
def kb_ask(question: str = "", kb: str = "", top_k: int = 5) -> str:
    if not (question or "").strip():
        return "请输入问题。"
    try:
        r = ask.ask(kb=kb, question=question, top_k=top_k)
        if r.get("mode") == "empty":
            return r.get("answer", "未找到相关片段。")
        lines = [r.get("answer", "")]
        lines.append("")
        lines.append("来源：")
        for i, s in enumerate(r.get("sources", []), 1):
            lines.append(f"[来源 {i}] {s.get('source', '')}：{s.get('snippet', '')[:80]}")
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"知识库问答失败：{exc}"
