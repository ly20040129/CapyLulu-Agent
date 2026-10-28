"""用户登录 / 认证 / 用量统计（零新依赖，本地单机自用，无权限隔离）。

身份模型：
- users.json           账号存储：{uid: {name, pass_hash, salt, created, last_login}}
- auth/current.json    当前登录态（唯一持久登录态，pet.py 共享身份锚点）
- usage.json           用量聚合：{owner: {tool: {count, tokens}}}
- token                hmac-sha256 自签名（payload exp + 签名，URL 安全 base64），7 天有效

未登录统一视为 "default" 身份，不影响既有单用户数据。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from loguru import logger

from .config import config

USERS_FILE = config.data_dir / "users.json"  # 账号存储：{uid: {...}}
CURRENT_FILE = config.data_dir / "auth" / "current.json"  # 当前登录态（pet.py 共享）
USAGE_FILE = config.data_dir / "usage.json"  # 用量聚合：{owner: {tool: {count, tokens}}}
TOKEN_TTL = 7 * 86400  # token 有效期 7 天

_secret_bytes: bytes | None = None  # 签名密钥缓存（进程内）
_current: dict | None = None  # 内存登录态缓存（current.json 为唯一持久来源）


def refresh_paths() -> None:
    """数据目录迁移后刷新模块内路径常量。"""
    global USERS_FILE, CURRENT_FILE, USAGE_FILE, _secret_bytes
    USERS_FILE = config.data_dir / "users.json"
    CURRENT_FILE = config.data_dir / "auth" / "current.json"
    USAGE_FILE = config.data_dir / "usage.json"
    _secret_bytes = None


def _now_str() -> str:
    """当前时间字符串。"""
    return time.strftime("%Y-%m-%d %H:%M:%S")


def hash_password(pwd: str, salt: str = "") -> str:
    """sha256(pwd + salt) 十六进制；注册时生成随机 salt 一并存储。"""
    return hashlib.sha256(f"{pwd}{salt}".encode("utf-8")).hexdigest()


def _load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    try:
        data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"[Auth] users.json 损坏，按空账号处理：{USERS_FILE}")
        return {}
    return data if isinstance(data, dict) else {}


def _save_users(users: dict) -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_current() -> dict | None:
    if not CURRENT_FILE.exists():
        return None
    try:
        data = json.loads(CURRENT_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _save_current(data: dict) -> None:
    global _current
    CURRENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CURRENT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _current = data


def _load_usage() -> dict:
    if not USAGE_FILE.exists():
        return {}
    try:
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"[Auth] usage.json 损坏，按空统计处理：{USAGE_FILE}")
        return {}
    return data if isinstance(data, dict) else {}


def _secret_key() -> bytes:
    """读取/生成持久化签名密钥（data/auth/secret.key），进程内缓存。"""
    global _secret_bytes
    if _secret_bytes:
        return _secret_bytes
    key_file = CURRENT_FILE.parent / "secret.key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if not key_file.exists():
        key_file.write_bytes(secrets.token_bytes(32))
        logger.info(f"[Auth] 已生成签名密钥：{key_file}")
    _secret_bytes = key_file.read_bytes()
    return _secret_bytes


def sign_token(uid: str, name: str, expires_in: int = TOKEN_TTL) -> str:
    """hmac-sha256 自签名 token（无第三方 JWT 依赖）：payload(exp) + 签名，URL 安全 base64。"""
    payload = json.dumps(
        {"uid": uid, "name": name, "exp": int(time.time()) + expires_in},
        separators=(",", ":"),
        ensure_ascii=False,
    )
    sig = hmac.new(_secret_key(), payload.encode("utf-8"), hashlib.sha256).digest()
    body = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("utf-8")
    sigs = base64.urlsafe_b64encode(sig).decode("utf-8")
    return f"{body}.{sigs}"


def verify_token(token: str) -> dict | None:
    """校验 token：签名 + 有效期，返回 {uid, name}；非法返回 None。"""
    try:
        body, sigs = (token or "").rsplit(".", 1)
        payload = base64.urlsafe_b64decode(body.encode("utf-8")).decode("utf-8")
        sig = base64.urlsafe_b64decode(sigs.encode("utf-8"))
        expect = hmac.new(_secret_key(), payload.encode("utf-8"), hashlib.sha256).digest()
        if not hmac.compare_digest(expect, sig):
            return None
        data = json.loads(payload)
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return {"uid": str(data.get("uid", "")), "name": str(data.get("name", ""))}
    except Exception:  # noqa: BLE001
        return None


def register(name: str, password: str) -> dict:
    """创建本地账号，返回 {ok, uid, name}；重名报错。"""
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "用户名不能为空"}
    if not password:
        return {"ok": False, "error": "密码不能为空"}
    users = _load_users()
    for u in users.values():
        if u.get("name") == name:
            return {"ok": False, "error": f"用户已存在：{name}"}
    salt = secrets.token_hex(8)
    uid = "u_" + secrets.token_hex(6)
    users[uid] = {
        "name": name,
        "pass_hash": hash_password(password, salt),
        "salt": salt,
        "created": _now_str(),
        "last_login": "",
    }
    _save_users(users)
    logger.info(f"[Auth] 已注册用户：{name}（{uid}）")
    return {"ok": True, "uid": uid, "name": name}


def login(name: str, password: str) -> dict:
    """校验密码，签发 token，写 current.json，返回 {ok, uid, name, token, expires}。"""
    name = (name or "").strip()
    if not name or not password:
        return {"ok": False, "error": "用户名和密码不能为空"}
    users = _load_users()
    for uid, u in users.items():
        if u.get("name") != name:
            continue
        if u.get("pass_hash") != hash_password(password, u.get("salt", "")):
            return {"ok": False, "error": "密码错误"}
        token = sign_token(uid, u["name"])
        expires = int(time.time()) + TOKEN_TTL
        current = {"uid": uid, "name": u["name"], "token": token,
                   "expires": expires, "login_at": _now_str()}
        _save_current(current)
        u["last_login"] = _now_str()
        _save_users(users)
        logger.info(f"[Auth] 用户登录：{name}")
        return {"ok": True, "uid": uid, "name": u["name"], "token": token, "expires": expires}
    return {"ok": False, "error": f"用户不存在：{name}"}


def logout() -> dict:
    """清除 current.json 与内存登录态。"""
    global _current
    _current = None
    if CURRENT_FILE.exists():
        CURRENT_FILE.unlink()
        logger.info("[Auth] 已退出登录")
    return {"ok": True, "message": "已退出登录"}


def current_user() -> dict | None:
    """读取当前登录态（current.json），返回 {uid, name}；未登录 / 过期返回 None。"""
    data = _current if _current else _load_current()
    if not data:
        return None
    if int(data.get("expires") or 0) < int(time.time()):
        return None
    return {"uid": str(data.get("uid", "")), "name": str(data.get("name", ""))}


def add_usage(owner: str, tool: str, tokens: int) -> None:
    """用量计量：写 data/usage.json {owner: {tool: {count, tokens}}}，增量聚合。"""
    owner = (owner or "default").strip() or "default"
    tool = (tool or "unknown").strip() or "unknown"
    tokens = max(0, int(tokens or 0))
    data = _load_usage()
    row = data.setdefault(owner, {}).setdefault(tool, {"count": 0, "tokens": 0})
    row["count"] = int(row.get("count", 0)) + 1
    row["tokens"] = int(row.get("tokens", 0)) + tokens
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def usage_stats() -> list[dict]:
    """用量统计：按 owner 聚合的工具调用次数与 token 消耗。"""
    data = _load_usage()
    rows = []
    for owner in sorted(data.keys()):
        tools = data[owner]
        count = sum(int(r.get("count", 0)) for r in tools.values())
        tokens = sum(int(r.get("tokens", 0)) for r in tools.values())
        rows.append({"owner": owner, "count": count, "tokens": tokens, "tools": tools})
    return rows
