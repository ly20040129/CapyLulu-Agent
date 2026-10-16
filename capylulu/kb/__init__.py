"""知识库（批次5）：库与文档管理 / 索引检索 / 问答。

- store：库 CRUD、文档导入（txt/md/csv/json 文本直入，pdf 走 pypdf）、切块建索引
- index：关键词 / 倒排评分检索 top-k 块（带来源引用）
- ask：检索 + LLM 问答（LLM 不可用降级为片段与来源）
"""
from . import ask, index, store  # noqa: F401

__all__ = ["store", "index", "ask"]
