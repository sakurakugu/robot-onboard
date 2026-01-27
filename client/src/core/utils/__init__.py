import socket
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import uuid6  # python3.11才自带uuid7，需要用第三方库

from core.logger import logger


# 生成uuid7
def generate_uuid() -> str:
    return str(uuid6.uuid7())


# 获取IPC路径
def get_ipc_path(name: str) -> Path:
    ipc_path = Path("/tmp") / "sparkrobot" / f"{name}.sock"
    try:
        if ipc_path.exists():
            ipc_path.unlink()
    except Exception:
        pass
    ipc_path.parent.mkdir(parents=True, exist_ok=True)
    return ipc_path


def execute_concurrently(*actions, _interval: float = 0):
    """并发执行不同机器狗的动作"""
    with ThreadPoolExecutor() as executor:
        futures = []
        for action in actions:
            futures.append(executor.submit(action))  # 提交动作到线程池
            time.sleep(_interval)  # 微小延时，避免瞬时大量请求导致网络拥堵
        for future in futures:
            future.result()  # 等待动作完成


def get_local_ip():
    """通过UDP连接获取本机对外的IP地址"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不会真的建立连接，仅用于获取本机出口IP
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception as e:
        logger.error(f"获取出口IP失败: {e}")
        ip = None
    finally:
        s.close()
    return ip


__all__ = ["execute_concurrently", "get_local_ip"]
