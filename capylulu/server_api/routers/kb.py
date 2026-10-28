"""知识库 REST 路由：库 CRUD、文档上传/列表/删除、搜索、问答。

- GET/POST /kb：知识库列表 / 新建；
- GET /kb/search：库内全文检索；
- POST /kb/ask：库内问答；
- GET/POST/DELETE /kb/{name}/docs(|/...)：文档列表 / 上传 / 删除；
- DELETE /kb/{name}：删除知识库。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from capylulu.kb import ask, index as kb_index
from capylulu.kb import store as kb_store

router = APIRouter(tags=["kb"])


def _wrap(fn, *args, **kwargs):
    """统一异常包装：FileNotFound→404 / ValueError→400 / RuntimeError→422 / 其他→500。"""
    try:
        return fn(*args, **kwargs)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/kb")
def kb_list() -> dict:
    """知识库列表。"""
    return {"kbs": _wrap(kb_store.list_kbs)}


class KbCreateBody(BaseModel):
    name: str = ""


@router.post("/kb")
def kb_create(body: KbCreateBody) -> dict:
    """新建知识库。"""
    # 前端 kbApi.create 以 JSON body 提交 {"name": ...}；
    # 若声明为 def kb_create(name: str) 会被 FastAPI 当作必填 query 参数，
    # 报 {"detail":[{"loc":["query","name"],"msg":"Field required"}]}。
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="知识库名称不能为空")
    return _wrap(kb_store.create_kb, name)


@router.get("/kb/search")
def kb_search(q: str = Query("", description="检索关键词"),
              kb: str = Query("", description="限定知识库名，留空跨库"),
              top_k: int = Query(5, ge=1, le=50)) -> dict:
    """知识库内全文检索，返回命中片段。"""
    hits = _wrap(kb_index.search, kb, q, top_k)
    return {"query": q, "total": len(hits), "hits": hits}


@router.post("/kb/ask")
def kb_ask(payload: dict) -> dict:
    """基于知识库内容问答（检索 top_k 片段后由 LLM 作答）。"""
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question 不能为空")
    return _wrap(ask.ask, payload.get("kb", ""), question, payload.get("top_k", 5))


@router.get("/kb/{name}/docs")
def kb_docs(name: str) -> dict:
    """指定知识库的文档列表。"""
    return {"kb": name, "docs": _wrap(kb_store.list_docs, name)}


@router.post("/kb/{name}/docs")
def kb_add_doc(name: str, payload: dict) -> dict:
    """上传文档到知识库（支持 src_path / content / content_b64 三种来源）。"""
    doc_name = payload.get("name", "")
    return _wrap(kb_store.add_doc, name,
                 doc_name,
                 payload.get("src_path") or None,
                 payload.get("content") or None,
                 payload.get("content_b64") or None)


@router.delete("/kb/{name}/docs/{doc_id}")
def kb_del_doc(name: str, doc_id: str) -> dict:
    """删除知识库内指定文档。"""
    ok = _wrap(kb_store.delete_doc, name, doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"文档不存在：{doc_id}")
    return {"deleted": True, "doc_id": doc_id}


@router.delete("/kb/{name}")
def kb_delete(name: str) -> dict:
    """删除整个知识库。"""
    ok = _wrap(kb_store.delete_kb, name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"知识库不存在：{name}")
    return {"deleted": True, "name": name}
