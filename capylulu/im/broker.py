"""IM 消息中心（broker）。

职责：
- 通道配置读写：data/im.json（通道列表：类型/名称/webhook_url/enabled）
- 收件箱：data/im/inbox.json（消息入队 / 出队 / 标记已处理 / 回发日志）
- 消息处理：把收到的消息交给 Leader（agent.run）处理，再把回复经原通道发回。

轮询：不引入调度框架，外部可通过 poll_channels() 周期性调用；
POST /api/im/inbox/incoming 到达时同步 process_pending() 处理即可。
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

from ..config import config
from .channel import IMChannel, create_channel

_DEFAULT_CONFIG = [
    {
        "name": "钉钉机器人",
        "type": "webhook",
        "webhook_url": "",
        "enabled": True,
    },
    {
        "name": "企业微信机器人",
        "type": "webhook",
        "webhook_url": "",
        "enabled": True,
    },
    {
        "name": "本地接收",
        "type": "httpin",
        "enabled": True,
    },
]


class Broker:
    """消息中心：配置 + 收件箱 + 处理。"""

    def __init__(self):
        self._lock = threading.Lock()
        self._channels: dict[str, IMChannel] = {}
        self._cfg_path: Path | None = None
        self._inbox_path: Path | None = None
        self._inbox: list[dict] = []
        self.reload()

    # ---- 路径与持久化 ----
    @property
    def cfg_path(self) -> Path:
        return config.data_dir / "im.json"

    @property
    def inbox_path(self) -> Path:
        return config.data_dir / "im" / "inbox.json"

    def reload(self) -> None:
        """重新加载配置与收件箱（隔离测试时切换 data_dir 后调用）。"""
        cfg = self._load_json(self.cfg_path)
        if not isinstance(cfg, list):
            cfg = []
        self._cfg_path = self.cfg_path
        self._inbox_path = self.inbox_path
        self._channels = {}
        for item in cfg:
            ch = create_channel(item)
            if ch is not None:
                self._channels[ch.name] = ch
        self._inbox = self._load_json(self.inbox_path)
        if not isinstance(self._inbox, list):
            self._inbox = []

    @staticmethod
    def _load_json(path: Path) -> object:
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:  # noqa: BLE001
            return None
        return None

    @staticmethod
    def _save_json(path: Path, obj: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        tmp.replace(path)

    # ---- 通道配置 ----
    def config_list(self) -> list[dict]:
        """通道配置列表（含持久化字段）。"""
        return [ch.to_dict() for ch in self._channels.values()]

    def save_config(self, channels: list[dict]) -> None:
        """整体写回通道配置并重建通道实例。"""
        with self._lock:
            self._channels = {}
            for item in channels:
                ch = create_channel(item)
                if ch is not None:
                    self._channels[ch.name] = ch
            self._save_json(self.cfg_path, self.config_list())

    def add_channel(self, item: dict) -> dict:
        """新增通道（重名返回错误）。"""
        with self._lock:
            name = (item.get("name") or "").strip()
            if not name:
                return {"ok": False, "message": "通道名称不能为空"}
            if name in self._channels:
                return {"ok": False, "message": f"通道「{name}」已存在"}
            ch = create_channel(item)
            if ch is None:
                return {"ok": False, "message": "通道类型无效"}
            self._channels[name] = ch
            self._save_json(self.cfg_path, self.config_list())
            return {"ok": True, "message": f"已新增通道「{name}」"}

    def update_channel(self, name: str, item: dict) -> dict:
        """更新通道配置。"""
        with self._lock:
            if name not in self._channels:
                return {"ok": False, "message": f"通道「{name}」不存在"}
            new_item = self._channels[name].to_dict()
            for k, v in item.items():
                if v is None:
                    continue
                if k == "secret" and not str(v).strip():
                    continue  # secret 留空 = 保持不变（防止前端编辑把已存密钥误清）
                new_item[k] = v
            ch = create_channel(new_item)
            if ch is None:
                return {"ok": False, "message": "通道配置无效"}
            # 重名：移除旧键再插入
            del self._channels[name]
            self._channels[ch.name] = ch
            self._save_json(self.cfg_path, self.config_list())
            return {"ok": True, "message": f"已更新通道「{ch.name}」"}

    def delete_channel(self, name: str) -> dict:
        with self._lock:
            if name not in self._channels:
                return {"ok": False, "message": f"通道「{name}」不存在"}
            del self._channels[name]
            self._save_json(self.cfg_path, self.config_list())
            return {"ok": True, "message": f"已删除通道「{name}」"}

    def get_channel(self, name: str) -> IMChannel | None:
        return self._channels.get(name)

    def enabled_channels(self) -> list[IMChannel]:
        return [ch for ch in self._channels.values() if ch.enabled]

    # ---- 收件箱 ----
    def enqueue(self, channel_name: str, text: str) -> dict:
        """外部消息入队（模拟 IM 服务器推送）。"""
        with self._lock:
            msg = {
                "id": uuid.uuid4().hex[:12],
                "channel": channel_name,
                "direction": "incoming",
                "text": str(text),
                "status": "pending",  # pending / processed / failed
                "reply": "",
                "created_at": self._now(),
                "processed_at": "",
            }
            self._inbox.append(msg)
            self._save_inbox()
            return dict(msg)

    def dequeue(self, channel_name: str | None = None) -> list[dict]:
        """取出未处理消息（poll 语义；默认当前通道均主动 poll 空）。"""
        with self._lock:
            out = [m for m in self._inbox if m.get("status") == "pending" and
                   (channel_name is None or m.get("channel") == channel_name)]
            return [dict(m) for m in out]

    def pending_messages(self) -> list[dict]:
        return self.dequeue()

    def record_reply(self, channel_name: str, text: str, ref_id: str = "") -> None:
        """记录回发日志（本地模拟回发 / 测试用）。"""
        with self._lock:
            self._inbox.append({
                "id": uuid.uuid4().hex[:12],
                "channel": channel_name,
                "direction": "outgoing",
                "text": str(text),
                "status": "sent",
                "reply": "",
                "ref": ref_id,
                "created_at": self._now(),
                "processed_at": "",
            })
            self._save_inbox()

    def mark_processed(self, msg_id: str, reply: str, ok: bool = True) -> None:
        with self._lock:
            for m in self._inbox:
                if m.get("id") == msg_id:
                    m["status"] = "processed" if ok else "failed"
                    m["reply"] = reply
                    m["processed_at"] = self._now()
                    break
            self._save_inbox()

    def list_inbox(self, limit: int = 100) -> list[dict]:
        with self._lock:
            return [dict(m) for m in self._inbox[-int(limit):]]

    def clear_inbox(self) -> int:
        with self._lock:
            n = len(self._inbox)
            self._inbox = []
            self._save_inbox()
            return n

    def _save_inbox(self) -> None:
        self._save_json(self.inbox_path, self._inbox)

    @staticmethod
    def _now() -> str:
        import datetime
        dt = datetime.datetime.now()
        return f"{dt.year}-{dt.month:02d}-{dt.day:02d} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}"

    # ---- 处理 ----
    def process_pending(self) -> dict:
        """把 pending 消息交给 Leader 处理并回发，返回处理统计。

        返回 {"processed": n, "failed": m, "details": [...]}
        """
        details = []
        processed = failed = 0
        for msg in self.pending_messages():
            channel = self.get_channel(msg.get("channel", ""))
            reply = ""
            try:
                from ..ui.common import agent  # 延迟导入避免循环
                reply = agent.run(msg.get("text", ""), [], "自动") or "（无回复）"
            except Exception as e:  # noqa: BLE001
                reply = f"（处理失败：{e}）"
            # 回发：经原通道发回（httpin 为本地模拟回发日志）
            if channel is not None:
                try:
                    send_result = channel.send(reply)
                    ok = bool(send_result.get("ok"))
                except Exception as e:  # noqa: BLE001
                    send_result = {"ok": False, "message": str(e)}
                    ok = False
                if not ok:
                    failed += 1
                    self.mark_processed(msg["id"], f"{reply} | 回发失败: {send_result.get('message', '')}", ok=False)
                else:
                    processed += 1
                    self.mark_processed(msg["id"], reply, ok=True)
                details.append({
                    "id": msg["id"],
                    "channel": msg.get("channel", ""),
                    "text": msg.get("text", ""),
                    "reply": reply,
                    "send_ok": ok,
                })
            else:
                failed += 1
                self.mark_processed(msg["id"], reply + " | 无可用通道", ok=False)
                details.append({"id": msg["id"], "channel": msg.get("channel", ""),
                                "text": msg.get("text", ""), "reply": reply, "send_ok": False})
        return {"processed": processed, "failed": failed, "details": details}

    def poll_channels(self) -> dict:
        """简单轮询：遍历启用通道调用 poll() 并处理。返回处理统计。"""
        pulled = 0
        for ch in self.enabled_channels():
            try:
                for m in ch.poll():
                    if isinstance(m, dict) and m.get("text"):
                        self.enqueue(ch.name, m.get("text"))
                        pulled += 1
            except Exception:  # noqa: BLE001
                continue
        stats = self.process_pending()
        stats["pulled"] = pulled
        return stats


# 全局单例
_broker: Broker | None = None
_broker_lock = threading.Lock()


def get_broker() -> Broker:
    """获取全局 broker（惰性创建）。"""
    global _broker
    if _broker is None:
        with _broker_lock:
            if _broker is None:
                _broker = Broker()
    return _broker
