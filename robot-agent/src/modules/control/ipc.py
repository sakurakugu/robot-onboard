import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, Optional

from sparkrobot_common import ORG_NAME, 获取IPC路径


class IpcServer:
    def __init__(self, project_name: str, logger, on_status: Callable[[Dict[str, Any]], Awaitable[None]]):
        self.project_name = project_name
        self.logger = logger
        self.on_status = on_status
        self._server: Optional[asyncio.AbstractServer] = None

    async def 启动(self) -> None:
        try:
            ipc_path = 获取IPC路径(ORG_NAME, self.project_name)
            if ipc_path.exists():
                ipc_path.unlink()
        except Exception:
            pass

        async def _handle_ipc(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            try:
                while True:
                    line = await reader.readline()
                    if not line:
                        break
                    try:
                        message = json.loads(line.decode("utf-8").strip())
                    except Exception:
                        continue
                    if isinstance(message, dict) and message.get("type") == "status":
                        await self.on_status(message)
            except Exception as e:
                self.logger.warning(f"IPC连接异常: {e}")
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        self._server = await asyncio.start_unix_server(_handle_ipc, path=str(ipc_path))
        self.logger.info(f"IPC服务启动: {ipc_path}")

    async def 关闭(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        try:
            ipc_path = 获取IPC路径(ORG_NAME, self.project_name)
            if ipc_path.exists():
                ipc_path.unlink()
        except Exception:
            pass
