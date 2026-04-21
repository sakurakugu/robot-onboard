from typing import Any, Callable

from src.modules.transport.protocol import (
    构建SDK模式响应消息,
    构建任务状态消息,
    构建传感器状态消息,
    构建地图响应消息,
    构建地图状态消息,
    构建安装包下载响应消息,
    构建导航响应消息,
    构建导航状态消息,
    构建巡逻响应消息,
    构建心跳消息,
    构建拍照响应消息,
    构建文本输入消息,
    构建日志标记响应消息,
    构建机器人摘要消息,
    构建机器人注册消息,
    构建激光扫描消息,
    构建状态消息,
    构建配置响应消息,
    构建音量响应消息,
    构建音频帧消息,
    构建音频开始消息,
    构建音频结束消息,
)
from src.modules.transport.ws_manager import WebSocketManager


class 消息发送器:
    """负责构建并发送所有出站 WebSocket 消息。"""

    def __init__(
        self,
        ws_manager: WebSocketManager,
        获取配置: Callable[[], dict[str, Any]],
        获取版本信息: Callable[[], dict[str, str]],
    ) -> None:
        self.ws_manager = ws_manager
        self._获取配置 = 获取配置
        self._获取版本信息 = 获取版本信息

    def _当前配置(self) -> dict[str, Any]:
        return self._获取配置()

    def _机器人UUID(self) -> str:
        return str(self._当前配置()["robot"]["uuid"])

    async def 发送消息(self, message: dict[str, Any], channel: str = "business") -> None:
        """发送消息到服务器。"""
        await self.ws_manager.发送消息(message, channel=channel)

    async def 发送文本(self, text: str) -> None:
        message = 构建文本输入消息(self._机器人UUID(), text)
        await self.发送消息(message, channel="business")

    async def 发送音频开始(self, session_id: str, frame_duration_ms: int) -> None:
        """发送音频开始消息。"""
        config = self._当前配置()
        audio_cfg = config.get("audio", {})
        message = 构建音频开始消息(
            self._机器人UUID(),
            session_id,
            frame_duration_ms,
            int(audio_cfg.get("sample_rate", 16000)),
            int(audio_cfg.get("channels", 1)),
        )
        await self.发送消息(message, channel="audio_upload")

    async def 发送音频数据块(self, session_id: str, seq: int, audio_bytes: bytes, frame_duration_ms: int) -> None:
        """发送音频数据块消息。"""
        config = self._当前配置()
        audio_cfg = config.get("audio", {})
        message = 构建音频帧消息(
            self._机器人UUID(),
            session_id,
            seq,
            audio_bytes,
            frame_duration_ms,
            int(audio_cfg.get("sample_rate", 16000)),
            int(audio_cfg.get("channels", 1)),
        )
        await self.发送消息(message, channel="audio_upload")

    async def 发送音频结束(self, session_id: str, reason: str) -> None:
        """发送音频结束消息。"""
        message = 构建音频结束消息(self._机器人UUID(), session_id, reason)
        await self.发送消息(message, channel="audio_upload")

    async def 发送注册(self) -> None:
        """发送注册消息。"""
        config = self._当前配置()
        robot_cfg = config["robot"]
        version_info = self._获取版本信息()
        agent_version = version_info.get("agent_version", "unknown")
        message = 构建机器人注册消息(
            robot_cfg["uuid"],
            robot_cfg["name"],
            robot_cfg["model"],
            agent_version,
            version_info,
        )
        await self.发送消息(message, channel="business")

    async def 发送心跳(self) -> None:
        """发送心跳消息。"""
        message = 构建心跳消息(self._机器人UUID())
        await self.发送消息(message, channel="business")

    async def 发送状态(self, status_msg: dict[str, Any]) -> None:
        """发送状态消息。"""
        message = 构建状态消息(
            self._机器人UUID(), status_msg.get("seq"), status_msg.get("data", {})
        )
        await self.发送消息(message, channel="business")

    async def 发送运行时摘要(self, summary: dict[str, Any]) -> None:
        """发送运行时摘要与分项状态。"""
        await self.发送消息(构建机器人摘要消息(self._机器人UUID(), summary), channel="business")

        navigation = summary.get("navigation", {})
        if isinstance(navigation, dict):
            await self.发送消息(构建导航状态消息(self._机器人UUID(), navigation), channel="business")

        mapping = summary.get("mapping", {})
        if isinstance(mapping, dict):
            await self.发送消息(构建地图状态消息(self._机器人UUID(), mapping), channel="business")

        task = summary.get("task", {})
        if isinstance(task, dict):
            await self.发送消息(构建任务状态消息(self._机器人UUID(), task), channel="business")

        lidar = summary.get("lidar", {})
        if isinstance(lidar, dict):
            await self.发送消息(
                构建传感器状态消息(
                    self._机器人UUID(),
                    {
                        "lidar": lidar,
                    },
                ),
                channel="business",
            )

    async def 发送激光扫描(self, scan: dict[str, Any]) -> None:
        """发送激光扫描消息。"""
        await self.发送消息(构建激光扫描消息(self._机器人UUID(), scan), channel="business")

    async def 发送拍照响应(
        self, request_id: str, success: bool, image: str | None = None, error: str | None = None
    ) -> None:
        """发送拍照响应消息。"""
        message = 构建拍照响应消息(self._机器人UUID(), request_id, success, image, error)
        await self.发送消息(message, channel="business")

    async def 发送音量响应(
        self, request_id: str, success: bool, data: dict[str, Any] | None = None, error: str | None = None
    ) -> None:
        """发送音量响应消息。"""
        message = 构建音量响应消息(self._机器人UUID(), request_id, success, data, error)
        await self.发送消息(message, channel="business")

    async def 发送配置响应(
        self, request_id: str, success: bool, data: dict[str, Any] | None = None, error: str | None = None
    ) -> None:
        """发送配置响应消息。"""
        message = 构建配置响应消息(self._机器人UUID(), request_id, success, data, error)
        await self.发送消息(message, channel="business")

    async def 发送导航响应(
        self,
        request_id: str,
        success: bool,
        data: dict[str, Any] | None = None,
        error: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """发送导航响应消息。"""
        message = 构建导航响应消息(self._机器人UUID(), request_id, success, data, error, error_code)
        await self.发送消息(message, channel="business")

    async def 发送地图响应(
        self,
        request_id: str,
        success: bool,
        data: dict[str, Any] | None = None,
        error: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """发送地图响应消息。"""
        message = 构建地图响应消息(self._机器人UUID(), request_id, success, data, error, error_code)
        await self.发送消息(message, channel="business")

    async def 发送巡逻响应(
        self,
        request_id: str,
        success: bool,
        data: dict[str, Any] | None = None,
        error: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """发送巡逻响应消息。"""
        message = 构建巡逻响应消息(self._机器人UUID(), request_id, success, data, error, error_code)
        await self.发送消息(message, channel="business")

    async def 发送SDK模式响应(
        self, request_id: str, success: bool, sdk_mode: bool | None = None, error: str | None = None
    ) -> None:
        """发送 SDK 模式响应消息。"""
        message = 构建SDK模式响应消息(self._机器人UUID(), request_id, success, sdk_mode, error)
        await self.发送消息(message, channel="business")

    async def 发送日志标记响应(
        self, request_id: str, success: bool, marker: str | None = None, error: str | None = None
    ) -> None:
        """发送日志标记响应消息。"""
        message = 构建日志标记响应消息(self._机器人UUID(), request_id, success, marker, error)
        await self.发送消息(message, channel="business")

    async def 发送安装包下载响应(
        self, request_id: str, success: bool, downloaded: list[str] | None = None, error: str | None = None
    ) -> None:
        """发送安装包下载响应消息。"""
        message = 构建安装包下载响应消息(self._机器人UUID(), request_id, success, downloaded, error)
        await self.发送消息(message, channel="business")
