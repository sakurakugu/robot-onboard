import asyncio
from typing import Any, Awaitable, Callable

from sparkrobot_common import get_logger

from src.modules.transport.protocol import 构建心跳消息
from src.modules.transport.ws_manager import 业务通道名称, 云端上游名称, 电脑端上游名称, 音频下载通道名称

logger = get_logger("robot-agent")


class 客户端运行时协调器:
    """负责客户端主循环、连接维护和后台任务编排。"""

    def __init__(
        self,
        ws_manager: Any,
        ipc_server: Any,
        ws_control_server: Any,
        media_streamer: Any,
        audio_capture: Any,
        message_sender: Any,
        处理收到的消息: Callable[[dict[str, Any], str, str], Awaitable[None]],
        连接到服务器: Callable[[], Awaitable[list[str]]],
        断开连接到服务器: Callable[[bool], Awaitable[None]],
        取消初始化: Callable[[], Awaitable[None]],
        允许云端媒体推流: Callable[[], bool],
        runtime_client: Any,
        获取机器人UUID: Callable[[], str],
        获取初始重连间隔: Callable[[], int | float],
    ) -> None:
        self.ws_manager = ws_manager
        self.ipc_server = ipc_server
        self.ws_control_server = ws_control_server
        self.media_streamer = media_streamer
        self.audio_capture = audio_capture
        self.message_sender = message_sender
        self._处理收到的消息 = 处理收到的消息
        self._连接到服务器 = 连接到服务器
        self._断开连接到服务器 = 断开连接到服务器
        self._取消初始化 = 取消初始化
        self._允许云端媒体推流 = 允许云端媒体推流
        self.runtime_client = runtime_client
        self._获取机器人UUID = 获取机器人UUID
        self.initial_reconnect_interval = float(获取初始重连间隔())
        self.max_reconnect_interval = 60.0
        self._音频设备缺失已告警 = False

    def 更新初始重连间隔(self, interval: int | float) -> None:
        """更新初始重连间隔配置。"""
        self.initial_reconnect_interval = float(interval)

    async def 处理IPC状态(self, status_msg: dict[str, Any]) -> None:
        """接收 IPC 状态并投递到发送队列。"""
        await self.message_sender.发送状态(status_msg)

    async def 运行(self) -> None:
        """运行客户端主循环。"""
        logger.info("机器狗客户端启动")
        await self.ipc_server.启动()

        direct_control_task = asyncio.create_task(self.ws_control_server.服务循环(), name="direct-control-ws")
        media_task = asyncio.create_task(
            self.media_streamer.服务循环(self._允许云端媒体推流),
            name="cloud-media-stream",
        )

        tasks = [
            asyncio.create_task(self._维护连接循环(), name="maintain-upstreams"),
            asyncio.create_task(self._运行音频采集任务(), name="audio-capture"),
            asyncio.create_task(self._发送运行时状态循环(), name="runtime-summary"),
            asyncio.create_task(self._发送激光扫描循环(), name="lidar-scan"),
        ]

        for upstream in (云端上游名称, 电脑端上游名称):
            tasks.append(asyncio.create_task(self._业务接收循环(upstream), name=f"{upstream}-business-recv"))
            tasks.append(
                asyncio.create_task(
                    self.ws_manager.发送心跳消息循环(upstream, self._获取机器人UUID(), 构建心跳消息),
                    name=f"{upstream}-heartbeat",
                )
            )

        if self.ws_manager.上游支持音频通道(云端上游名称):
            tasks.append(asyncio.create_task(self._音频下载接收循环(云端上游名称), name="cloud-audio-download"))

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在退出...")
        except asyncio.CancelledError:
            logger.info("收到取消信号，正在退出...")
            raise
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

            direct_control_task.cancel()
            media_task.cancel()
            await asyncio.gather(direct_control_task, media_task, return_exceptions=True)

            await self._断开连接到服务器(True)
            await self.ipc_server.关闭()
            try:
                await self._取消初始化()
            except Exception:
                pass
            logger.info("客户端已关闭")

    async def _维护连接循环(self) -> None:
        retry_interval = self.initial_reconnect_interval

        while True:
            if self.ws_manager.全部已启用业务已连接():
                retry_interval = self.initial_reconnect_interval
                await asyncio.sleep(2)
                continue

            if self.ws_manager.任一业务已连接():
                新连接上游 = await self._连接到服务器()
                if 新连接上游:
                    retry_interval = self.initial_reconnect_interval
                await asyncio.sleep(2)
                continue

            logger.info(f"尝试连接上游服务 (重连间隔: {retry_interval}秒)...")
            新连接上游 = await self._连接到服务器()
            if 新连接上游:
                retry_interval = self.initial_reconnect_interval
                logger.info(f"✓ 已连接上游: {', '.join(新连接上游)}")
                await asyncio.sleep(2)
                continue

            logger.warning(f"✗ 尚未连接任何上游，{retry_interval} 秒后重试...")
            await asyncio.sleep(retry_interval)
            retry_interval = min(retry_interval * 2, self.max_reconnect_interval)

    async def _业务接收循环(self, upstream: str) -> None:
        while True:
            if not self.ws_manager.上游业务已连接(upstream):
                await asyncio.sleep(1)
                continue

            ws = self.ws_manager.获取通道连接(upstream, 业务通道名称)
            if ws is None:
                await asyncio.sleep(1)
                continue

            try:
                await self.ws_manager.接受消息循环(upstream, 业务通道名称, ws, self._处理收到的消息)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"业务接收循环异常退出: upstream={upstream}, error={exc}")
            await asyncio.sleep(1)

    async def _音频下载接收循环(self, upstream: str) -> None:
        while True:
            if not self.ws_manager.通道已连接(upstream, 音频下载通道名称):
                await asyncio.sleep(1)
                continue

            ws = self.ws_manager.获取通道连接(upstream, 音频下载通道名称)
            if ws is None:
                await asyncio.sleep(1)
                continue

            try:
                await self.ws_manager.接受消息循环(upstream, 音频下载通道名称, ws, self._处理收到的消息)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"音频下载接收循环异常退出: upstream={upstream}, error={exc}")
            await asyncio.sleep(1)

    async def _发送运行时状态循环(self) -> None:
        while True:
            if not self.ws_manager.任一业务已连接():
                await asyncio.sleep(1)
                continue

            try:
                async for summary in self.runtime_client.订阅状态摘要(interval_sec=1.0):
                    if not self.ws_manager.任一业务已连接():
                        break
                    await self.message_sender.发送运行时摘要(summary)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = self.runtime_client.格式化异常(exc)
                logger.warning(f"订阅运行时状态失败: {error}")
                await asyncio.sleep(5)

    async def _运行音频采集任务(self) -> None:
        while True:
            if not self.ws_manager.connected:
                await asyncio.sleep(1)
                continue

            try:
                await self.audio_capture.开始采集()
                self._音频设备缺失已告警 = False
            except Exception as exc:
                if self._是否是音频设备异常(exc):
                    if not self._音频设备缺失已告警:
                        logger.error("未检测到可用音频设备，音频采集将持续重试，不影响云端连接")
                        self._音频设备缺失已告警 = True
                    logger.warning(f"音频设备异常: {exc}")
                    await asyncio.sleep(5)
                    continue
                logger.warning(f"音频采集任务异常: {exc}")
                await asyncio.sleep(2)
                continue
            await asyncio.sleep(0.5)

    async def _发送激光扫描循环(self) -> None:
        last_captured_at: int | None = None
        while True:
            if not self.ws_manager.上游业务已连接(电脑端上游名称):
                await asyncio.sleep(1)
                continue

            try:
                scan = await self.runtime_client.获取激光扫描()
                if scan.get("available") is not True:
                    await asyncio.sleep(0.5)
                    continue

                captured_at = scan.get("captured_at")
                captured_at_number = int(captured_at) if isinstance(captured_at, (int, float)) else None
                if captured_at_number is None:
                    await asyncio.sleep(0.2)
                    continue

                if captured_at_number != last_captured_at:
                    last_captured_at = captured_at_number
                    await self.message_sender.发送激光扫描(scan)

                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = self.runtime_client.格式化异常(exc)
                logger.warning(f"读取激光扫描失败: {error}")
                await asyncio.sleep(2)

    def _是否是音频设备异常(self, error: Exception) -> bool:
        message = str(error).lower()
        patterns = (
            "error querying device -1",
            "invalid input device",
            "no default input device",
            "device unavailable",
            "device not found",
        )
        return any(pattern in message for pattern in patterns)
