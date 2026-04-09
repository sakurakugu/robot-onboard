from typing import Any

from sparkrobot_common import 格式化运行时IPC异常, 运行时IPC客户端


def 格式化运行时异常(exc: Exception) -> dict[str, Any]:
    """把运行时调用异常转换为统一错误结构。"""
    return 格式化运行时IPC异常(exc)


def _创建客户端() -> 运行时IPC客户端:
    """创建运行时 IPC 客户端。"""
    return 运行时IPC客户端()


async def 获取运行时探活结果() -> dict[str, Any]:
    """获取运行时探活结果。"""
    client = _创建客户端()
    try:
        data = await client.探活()
        return {
            "reachable": True,
            "socket_path": str(client.socket_path),
            "runtime": data,
        }
    except Exception as exc:
        return {
            "reachable": False,
            "socket_path": str(client.socket_path),
            "error": 格式化运行时异常(exc),
        }


async def 获取运行时摘要() -> dict[str, Any]:
    """获取运行时状态摘要。"""
    client = _创建客户端()
    return await client.获取摘要()


async def 获取运行时完整状态() -> dict[str, Any]:
    """获取运行时完整状态。"""
    client = _创建客户端()
    return await client.获取完整状态()
