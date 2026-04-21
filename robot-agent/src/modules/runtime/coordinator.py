import asyncio
from typing import Any, Awaitable, Callable

from sparkrobot_common import get_logger

from src.modules.transport.protocol import 构建心跳消息

logger = get_logger("robot-agent")


class 客户端运行时协调器:
    """负责客户端主循环、重连和后台任务编排。"""

    def __init__(
        self,
        ws_manager: Any,
        ipc_server: Any,
        ws_control_server: Any,
        media_streamer: Any,
        audio_capture: Any,
        message_sender: Any,
        处理收到的消息: Callable[[dict[str, Any]], Awaitable[None]],
        连接到服务器: Callable[[], Awaitable[bool]],
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
        self.audio_task: asyncio.Task[Any] | None = None
        self._ipc_status_task: asyncio.Task[Any] | None = None
        self._runtime_status_task: asyncio.Task[Any] | None = None
        self._lidar_scan_task: asyncio.Task[Any] | None = None
        self._media_stream_task: asyncio.Task[Any] | None = None
        self._ipc_status_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.initial_reconnect_interval = float(获取初始重连间隔())
        self.max_reconnect_interval = 60.0
        self.current_reconnect_interval = self.initial_reconnect_interval
        self._音频设备缺失已告警 = False

    def 更新初始重连间隔(self, interval: int | float) -> None:
        """更新初始重连间隔配置。"""
        self.initial_reconnect_interval = float(interval)

    async def 处理IPC状态(self, status_msg: dict[str, Any]) -> None:
        """接收 IPC 状态并投递到发送队列。"""
        await self._ipc_status_queue.put(status_msg)

    async def 运行(self) -> None:
        """运行客户端主循环。"""
        logger.info("机器狗客户端启动")
        await self.ipc_server.启动()
        direct_control_task = asyncio.create_task(self.ws_control_server.服务循环(), name="direct-control-ws")
        self._media_stream_task = asyncio.create_task(
            self.media_streamer.服务循环(self._允许云端媒体推流),
            name="cloud-media-stream",
        )
        try:
            while True:
                try:
                    if not await self._确保与服务器连接():
                        continue
                    tasks = self._构建异步任务()

                    if not tasks:
                        await asyncio.sleep(1)
                        continue

                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    should_reconnect = self._是否需要重连(done)

                    if not self.ws_manager.connected:
                        should_reconnect = True
                        logger.info("主连接已断开，准备重连...")

                    if should_reconnect:
                        await self._取消并等待任务(pending)
                        if self._是否有活跃的WebSocket连接():
                            await self._断开连接到服务器(False)
                        logger.info("任务组结束，准备重连...")
                    else:
                        await self._取消并等待任务(pending)
                        logger.debug("部分任务结束，重建任务组")

                except KeyboardInterrupt:
                    logger.info("收到中断信号，正在退出...")
                    break
                except Exception as e:
                    logger.error(f"运行时错误: {e}")
                    self.ws_manager.connected = False
                    if self._是否有活跃的WebSocket连接():
                        await self._断开连接到服务器(False)
        except asyncio.CancelledError:
            logger.info("收到中断信号，正在退出...")
        finally:
            direct_control_task.cancel()
            try:
                await direct_control_task
            except (asyncio.CancelledError, Exception):
                pass
            if self._media_stream_task:
                self._media_stream_task.cancel()
                try:
                    await self._media_stream_task
                except (asyncio.CancelledError, Exception):
                    pass
            await self._断开连接到服务器(True)
            await self.ipc_server.关闭()
            try:
                await self._取消初始化()
            except Exception:
                pass
            logger.info("客户端已关闭")

    async def _确保与服务器连接(self) -> bool:
        """确保与服务器连接。"""
        if self.ws_manager.connected:
            self.current_reconnect_interval = self.initial_reconnect_interval
            return True

        logger.info(f"尝试连接到服务器 (重连间隔: {self.current_reconnect_interval}秒)...")
        success = await self._连接到服务器()
        if success:
            self.current_reconnect_interval = self.initial_reconnect_interval
            logger.info("✓ 连接成功，重连间隔已重置")
            return True

        logger.warning(f"✗ 连接失败，{self.current_reconnect_interval} 秒后重试...")
        await asyncio.sleep(self.current_reconnect_interval)

        old_interval = self.current_reconnect_interval
        self.current_reconnect_interval = min(self.current_reconnect_interval * 2, self.max_reconnect_interval)
        if self.current_reconnect_interval != old_interval:
            logger.info(f"重连间隔已调整: {old_interval}秒 → {self.current_reconnect_interval}秒")
        return False

    def _是否需要重连(self, done_tasks: set[asyncio.Task[Any]]) -> bool:
        for task in done_tasks:
            try:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc:
                    logger.warning(f"子任务异常退出: {exc}")
                    return True
            except Exception as e:
                logger.warning(f"子任务退出: {e}")
                return True
        return False

    async def _取消并等待任务(self, tasks: set[asyncio.Task[Any]]) -> None:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _发送IPC状态循环(self) -> None:
        while True:
            status_msg = await self._ipc_status_queue.get()
            if not self.ws_manager.connected:
                continue
            await self.message_sender.发送状态(status_msg)

    async def _发送运行时状态循环(self) -> None:
        while True:
            if not self.ws_manager.connected:
                await asyncio.sleep(1)
                continue

            try:
                async for summary in self.runtime_client.订阅状态摘要(interval_sec=1.0):
                    if not self.ws_manager.connected:
                        break
                    await self.message_sender.发送运行时摘要(summary)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = self.runtime_client.格式化异常(exc)
                logger.warning(f"订阅运行时状态失败: {error}")
                await asyncio.sleep(5)

    async def _运行音频采集任务(self) -> None:
        while self.ws_manager.connected:
            try:
                await self.audio_capture.开始采集()
                self._音频设备缺失已告警 = False
            except Exception as e:
                if self._是否是音频设备异常(e):
                    if not self._音频设备缺失已告警:
                        logger.error("未检测到可用音频设备，音频采集将持续重试，不影响云端连接")
                        self._音频设备缺失已告警 = True
                    logger.warning(f"音频设备异常: {e}")
                    await asyncio.sleep(5)
                    continue
                logger.warning(f"音频采集任务异常: {e}")
                await asyncio.sleep(2)
                continue
            await asyncio.sleep(0.5)

    async def _发送激光扫描循环(self) -> None:
        last_captured_at: int | None = None
        while True:
            if not self.ws_manager.connected:
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
        return any(p in message for p in patterns)

    def _构建异步任务(self) -> list[asyncio.Task[Any]]:
        """构建要运行的异步任务。"""
        tasks: list[asyncio.Task[Any]] = []
        if self.ws_manager.ws_business and self.ws_manager.connected:
            tasks.append(
                asyncio.create_task(
                    self.ws_manager.接受消息循环("business", self.ws_manager.ws_business, self._处理收到的消息)
                )
            )
        if self.ws_manager.ws_audio_download and self.ws_manager.connected_audio_download:
            tasks.append(
                asyncio.create_task(
                    self.ws_manager.接受消息循环(
                        "audio_download", self.ws_manager.ws_audio_download, self._处理收到的消息
                    )
                )
            )
        if not self.audio_task or self.audio_task.done():
            self.audio_task = asyncio.create_task(self._运行音频采集任务())
        tasks.append(self.audio_task)
        if not self._ipc_status_task or self._ipc_status_task.done():
            self._ipc_status_task = asyncio.create_task(self._发送IPC状态循环())
        tasks.append(self._ipc_status_task)
        if not self._runtime_status_task or self._runtime_status_task.done():
            self._runtime_status_task = asyncio.create_task(self._发送运行时状态循环())
        tasks.append(self._runtime_status_task)
        if not self._lidar_scan_task or self._lidar_scan_task.done():
            self._lidar_scan_task = asyncio.create_task(self._发送激光扫描循环())
        tasks.append(self._lidar_scan_task)
        tasks.append(
            asyncio.create_task(self.ws_manager.发送心跳消息循环(self._获取机器人UUID(), 构建心跳消息))
        )
        return tasks

    def _是否有活跃的WebSocket连接(self) -> bool:
        """检查是否有活动的 WebSocket 连接。"""
        return bool(
            self.ws_manager.ws_business
            or self.ws_manager.ws_audio_download
            or self.ws_manager.ws_audio_upload
        )
