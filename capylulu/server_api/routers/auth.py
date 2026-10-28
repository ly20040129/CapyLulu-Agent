"""用户认证：注册 / 登录 / 退出 / 当前用户 / 用量统计。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from capylulu import auth

router = APIRouter(tags=["auth"])


class AuthBody(BaseModel):
    name: str = ""
    password: str = ""


@router.post("/auth/register")
def register(body: AuthBody) -> dict:
    """创建本地账号（重复报错）。"""
    result = auth.register(body.name, body.password)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "注册失败"))
    return result


@router.post("/auth/login")
def login(body: AuthBody) -> dict:
    """校验密码，签发 token，写 current.json。"""
    result = auth.login(body.name, body.password)
    if not result.get("ok"):
        raise HTTPException(status_code=401, detail=result.get("error", "登录失败"))
    return result


@router.post("/auth/logout")
def logout() -> dict:
    """清除登录态。"""
    return auth.logout()


@router.get("/auth/me")
def me() -> dict:
    """返回当前用户 {uid, name} 或 {user: null}。"""
    return {"user": auth.current_user()}


@router.get("/auth/stats")
def stats() -> dict:
    """用量统计：按 owner 聚合的工具调用次数与 token 消耗。"""
    return {"items": auth.usage_stats()}
