"""遥测后台服务

在机器狗本地运行，以 UDP 方式向运控进程发送心跳，
持续接收遥测数据并缓存最新值，供 HTTP 端点查询。

关键说明：
  - robot-server 运行在机器狗本体上（同一台机器）
  - 运控进程监听 0.0.0.0:8081，收到心跳后将状态推送到心跳来源的 IP:8080
  - 因此必须绑定 UDP 0.0.0.0:8080（与 HTTP 8080 不冲突，协议不同）
  - 心跳发送至 127.0.0.1:8081（本机运控）
  - 任何收到的包都更新在线时间戳（不仅限于 dog_state）
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

# ── 常量 ──────────────────────────────────────────────────────────────────────
DOG_HOST     = "127.0.0.1"
DOG_PORT     = 8081    # 运控进程接收控制命令的 UDP 端口
LISTEN_PORT  = 8080    # 运控回包目标端口（与 HTTP TCP:8080 不冲突）
HEARTBEAT    = json.dumps({"type": "heartbeat", "heartbeat": 1}).encode()
HB_INTERVAL  = 1.0    # 心跳间隔（秒）
OFFLINE_TO   = 5.0    # 超过此秒数未收到任何遥测包则判定离线

# ── 共享状态 ─────────────────────────────────────────────────────────────────
_lock   = threading.Lock()
_cache: dict[str, Any] = {}  # 最新 dog_state 字段
_last_rx_time: float   = 0.0
_started = False


def 获取遥测数据() -> dict[str, Any]:
    """返回最新遥测快照，包含 online 字段。"""
    with _lock:
        snapshot = dict(_cache)
        elapsed = time.time() - _last_rx_time
        snapshot["online"] = _last_rx_time > 0 and elapsed < OFFLINE_TO
    return snapshot


# ── 发送心跳 ─────────────────────────────────────────────────────────────────
def _sender_loop(sock: socket.socket, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            sock.sendto(HEARTBEAT, (DOG_HOST, DOG_PORT))
        except OSError as e:
            logger.warning("遥测心跳发送失败: %s", e)
        stop.wait(HB_INTERVAL)


# ── 接收遥测 ─────────────────────────────────────────────────────────────────
def _receiver_loop(sock: socket.socket, stop: threading.Event) -> None:
    global _last_rx_time
    sock.settimeout(1.0)
    while not stop.is_set():
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            break

        try:
            obj: dict[str, Any] = json.loads(data.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue

        # 任何合法 JSON 包都视为在线证明
        with _lock:
            _last_rx_time = time.time()
            # 只缓存 dog_state 字段（含 power/temp 等关键信息）
            if obj.get("type") == "dog_state":
                _cache.update({k: v for k, v in obj.items() if k != "type"})


# ── 启动 ─────────────────────────────────────────────────────────────────────
_stop_event: threading.Event | None = None


def start() -> None:
    """启动遥测后台线程（幂等，重复调用无效）。"""
    global _started, _stop_event
    if _started:
        return
    _started = True
    _stop_event = threading.Event()

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # 绑定 0.0.0.0:8080（UDP），与 HTTP TCP:8080 不冲突
        sock.bind(("", LISTEN_PORT))
    except OSError as e:
        logger.error("遥测服务绑定 UDP :%d 失败: %s — 请检查端口是否已被其他 UDP 进程占用", LISTEN_PORT, e)
        _started = False
        return

    threading.Thread(
        target=_sender_loop, args=(sock, _stop_event),
        daemon=True, name="遥测-发送器"
    ).start()
    threading.Thread(
        target=_receiver_loop, args=(sock, _stop_event),
        daemon=True, name="遥测-接收器"
    ).start()

    logger.info("遥测服务已启动，UDP 监听 0.0.0.0:%d，心跳目标 %s:%d", LISTEN_PORT, DOG_HOST, DOG_PORT)


def stop() -> None:
    """停止遥测后台线程。"""
    global _started
    if _stop_event:
        _stop_event.set()
    _started = False

