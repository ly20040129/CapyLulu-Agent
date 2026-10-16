"""知识库问答：检索 top-k 块 + LLM 生成回答；LLM 不可用时降级返回片段与来源。"""
from __future__ import annotations

from ..llm import create_llm
from . import index


def _sources(hits: list[dict]) -> list[dict]:
    return [{
        "doc_id": h.get("doc_id", ""),
        "name": h.get("name", ""),
        "chunk_idx": h.get("chunk_idx", 0),
        "score": h.get("score", 0),
        "source": h.get("source", ""),
        "snippet": (h.get("text", "") or "")[:200],
    } for h in hits]


def ask(kb: str = "", question: str = "", top_k: int = 5) -> dict:
    """基于知识库问答。

    返回 {"answer", "sources", "mode"}：mode = llm（LLM 生成）| fallback（降级片段）| empty（无命中）。
    """
    question = (question or "").strip()
    if not question:
        return {"answer": "请输入问题。", "sources": [], "mode": "empty"}
    hits = index.search(kb=kb, query=question, top_k=top_k)
    if not hits:
        return {"answer": "知识库中没有找到与问题相关的片段，请先导入文档或换个问法。",
                "sources": [], "mode": "empty"}

    context = "\n\n".join(
        f"[来源 {i + 1}]（{h['source']}）\n{h['text']}" for i, h in enumerate(hits)
    )
    prompt = (
        "你是知识库问答助手。请只依据提供的片段回答用户问题；若片段不足以回答，"
        "请明确说明缺失哪些信息。回答要简洁，并在相关句末用 [来源 N] 标注依据。\n\n"
        f"问题：{question}\n\n片段：\n{context}\n\n请回答："
    )
    try:
        llm = create_llm()
        resp = llm.chat([{"role": "user", "content": prompt}])
        answer = (resp.get("content") or "").strip()
        if answer:
            return {"answer": answer, "sources": _sources(hits), "mode": "llm"}
    except Exception:  # noqa: BLE001
        pass

    lines = [f"LLM 暂不可用，以下为检索到的相关片段（共 {len(hits)} 条，请结合来源查阅）："]
    for i, h in enumerate(hits):
        lines.append(f"[来源 {i + 1}] {h['source']}：{(h.get('text') or '')[:120]}")
    return {"answer": "\n".join(lines), "sources": _sources(hits), "mode": "fallback"}
