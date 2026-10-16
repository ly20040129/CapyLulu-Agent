"""知识库索引与检索：关键词 / 倒排评分检索 top-k 文档块，带来源引用。

- 中文粗粒度分词（2~4 字窗口 + 英文/数字词）
- TF-IDF 风格评分：score = Σ 词频 × log(1 + N / (1 + 词所在块数))
- 支持单库检索（kb 指定）与跨库检索（kb 为空）
"""
from __future__ import annotations

import math
import re
from collections import Counter

from . import store

_STOPWORDS = {
    "的", "了", "和", "与", "在", "我", "你", "他", "它", "是", "把", "被",
    "给", "对", "从", "到", "用", "做", "这个", "那个", "一下", "一个",
    "然后", "因为", "所以", "以及", "进行", "可以", "我们", "你们", "他们",
    "请问", "如何", "怎么", "什么", "为什么",
}


def tokenize(text: str) -> list[str]:
    """粗粒度分词：2~4 字中文窗口 + 英文/数字词，过滤停用词。"""
    tokens: list[str] = []
    text = re.sub(r"\s+", "", text or "")
    for m in re.finditer(r"[A-Za-z0-9_]{2,}", text):
        tokens.append(m.group(0).lower())
    for n in (2, 3, 4):
        for i in range(len(text) - n + 1):
            seg = text[i:i + n]
            if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", seg) and seg not in _STOPWORDS:
                tokens.append(seg)
    return tokens


def _collect_chunks(kb: str = "") -> list[dict]:
    """收集候选块：指定库只取该库，否则跨全部库。"""
    kbs = [kb] if kb else [k["name"] for k in store.list_kbs()]
    chunks: list[dict] = []
    for name in kbs:
        for c in store.get_chunks(name):
            c = dict(c)
            c["kb"] = name
            chunks.append(c)
    return chunks


def search(kb: str = "", query: str = "", top_k: int = 5) -> list[dict]:
    """按关键词检索知识库，返回 top-k 文档块（含来源引用）。

    返回 [{doc_id, name, chunk_idx, text, kb, score, source}]，按 score 降序。
    """
    query = (query or "").strip()
    top_k = max(1, min(int(top_k or 5), 50))
    terms = set(tokenize(query))
    if not terms:
        return []
    chunks = _collect_chunks(kb)
    if not chunks:
        return []

    n = len(chunks)
    df: Counter = Counter()
    for c in chunks:
        for t in terms:
            if t in c["text"]:
                df[t] += 1
    idf = {t: math.log(1.0 + n / (1.0 + df[t])) for t in terms}

    hits: list[dict] = []
    for c in chunks:
        text = c["text"]
        score = 0.0
        for t in terms:
            cnt = text.count(t)
            if cnt:
                score += cnt * idf[t]
        if score > 0:
            c["score"] = round(score, 4)
            c["source"] = f"{c['kb']}/{c['name']} 第{c['chunk_idx'] + 1}块"
            hits.append(c)
    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:top_k]
