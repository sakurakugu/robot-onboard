import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional, cast
from urllib.parse import urljoin

import websockets
from sparkrobot_common import DEFAULT_SERVER_ADDR, get_logger
from websockets import ClientConnection

业务通道名称 = "business"
音频上传通道名称 = "audio_upload"
音频下载通道名称 = "audio_download"

云端上游名称 = "cloud"
电脑端上游名称 = "studio"


@dataclass
class 上游配置:
    名称: str
    enabled: bool
    server_url: str
    business_url: str
    audio_upload_url: str
    audio_download_url: str
    reconnect_interval: float
    heartbeat_interval: float
    支持音频通道: bool


@dataclass
class 上游连接状态:
    配置: 上游配置
    ws_business: Optional[ClientConnection] = None
    ws_audio_upload: Optional[ClientConnection] = None
    ws_audio_download: Optional[ClientConnection] = None
    connected: bool = False
    connected_audio_upload: bool = False
    connected_audio_download: bool = False
    _重连中通道: set[str] = field(default_factory=set)


class WebSocketManager:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.logger = get_logger("robot-agent")
        self.robot_uuid: Optional[str] = None
        self._上游状态 = self._创建上游状态表()

    @property
    def connected(self) -> bool:
        return self.上游业务已连接(云端上游名称)

    @property
    def connected_audio_upload(self) -> bool:
        return self.通道已连接(云端上游名称, 音频上传通道名称)

    @property
    def connected_audio_download(self) -> bool:
        return self.通道已连接(云端上游名称, 音频下载通道名称)

    @property
    def ws_business(self) -> Optional[ClientConnection]:
        return self.获取通道连接(云端上游名称, 业务通道名称)

    @property
    def ws_audio_upload(self) -> Optional[ClientConnection]:
        return self.获取通道连接(云端上游名称, 音频上传通道名称)

    @property
    def ws_audio_download(self) -> Optional[ClientConnection]:
        return self.获取通道连接(云端上游名称, 音频下载通道名称)

    def 更新配置(self, config: dict[str, Any]) -> None:
        """更新配置快照，并同步各上游的目标地址。"""
        self.config = config
        self._上游状态 = self._创建上游状态表(保留旧状态=self._上游状态)

    def 获取已启用上游(self) -> list[str]:
        return [名称 for 名称, 状态 in self._上游状态.items() if 状态.配置.enabled]

    def 获取已连接业务上游(self) -> list[str]:
        return [名称 for 名称 in self.获取已启用上游() if self.上游业务已连接(名称)]

    def 任一业务已连接(self) -> bool:
        return any(self.上游业务已连接(名称) for 名称 in self.获取已启用上游())

    def 全部已启用业务已连接(self) -> bool:
        已启用上游 = self.获取已启用上游()
        if not 已启用上游:
            return False
        return all(self.上游业务已连接(名称) for 名称 in 已启用上游)

    def 存在缺失的已启用业务连接(self) -> bool:
        return any(not self.上游业务已连接(名称) for 名称 in self.获取已启用上游())

    def 上游支持音频通道(self, upstream: str) -> bool:
        return self._获取上游状态(upstream).配置.支持音频通道

    def 获取上游重连间隔(self, upstream: str) -> float:
        return float(self._获取上游状态(upstream).配置.reconnect_interval)

    def 上游业务已连接(self, upstream: str) -> bool:
        return self.通道已连接(upstream, 业务通道名称)

    def 通道已连接(self, upstream: str, channel: str) -> bool:
        状态 = self._获取上游状态(upstream)
        if channel == 业务通道名称:
            return 状态.connected
        if channel == 音频上传通道名称:
            return 状态.connected_audio_upload
        if channel == 音频下载通道名称:
            return 状态.connected_audio_download
        return False

    def 获取通道连接(self, upstream: str, channel: str) -> Optional[ClientConnection]:
        状态 = self._获取上游状态(upstream)
        if channel == 业务通道名称:
            return 状态.ws_business
        if channel == 音频上传通道名称:
            return 状态.ws_audio_upload
        if channel == 音频下载通道名称:
            return 状态.ws_audio_download
        return None

    async def 连接(self, robot_uuid: str) -> list[str]:
        """连接所有已启用上游，返回本轮新连上的业务上游列表。"""
        self.robot_uuid = robot_uuid
        新连接上游: list[str] = []

        for upstream in (云端上游名称, 电脑端上游名称):
            状态 = self._获取上游状态(upstream)
            if not 状态.配置.enabled:
                if self._上游存在活动连接(状态):
                    await self._断开单个上游(upstream)
                continue

            连接前已连 = 状态.connected
            await self._连接单个上游(upstream, robot_uuid)
            if 状态.connected and not 连接前已连:
                新连接上游.append(upstream)

        return 新连接上游

    async def 断开连接(self, upstream: str | None = None) -> None:
        """断开指定上游或全部上游连接。"""
        if upstream:
            await self._断开单个上游(upstream)
            return

        for 名称 in list(self._上游状态.keys()):
            await self._断开单个上游(名称)
        self.robot_uuid = None
        self.logger.info("已断开所有上游连接")

    async def 发送消息(self, message: dict[str, Any], channel: str = 业务通道名称, upstream: str = 云端上游名称) -> None:
        """发送消息到指定上游通道。"""
        状态 = self._获取上游状态(upstream)
        if not 状态.配置.enabled:
            self.logger.debug(f"上游未启用，忽略发送: upstream={upstream}, channel={channel}")
            return

        ws = self.获取通道连接(upstream, channel)
        is_connected = self.通道已连接(upstream, channel)

        if (not ws or not is_connected) and channel != 业务通道名称 and self.robot_uuid:
            self.logger.info(f"通道未连接，尝试重连: upstream={upstream}, channel={channel}")
            await self._重连单个通道(upstream, channel)
            ws = self.获取通道连接(upstream, channel)
            is_connected = self.通道已连接(upstream, channel)

        if not ws or not is_connected:
            self.logger.warning(f"通道未连接，无法发送消息: upstream={upstream}, channel={channel}")
            return

        try:
            await ws.send(json.dumps(message))
            self.logger.debug(f"发送消息: upstream={upstream}, channel={channel}, type={message.get('type')}")
        except Exception as exc:
            self.logger.error(f"发送消息失败: upstream={upstream}, channel={channel}, error={exc}")
            self._设置通道连接状态(状态, channel, False)
            self._设置通道连接对象(状态, channel, None)

    async def 接受消息循环(
        self,
        upstream: str,
        channel: str,
        ws: ClientConnection,
        on_message: Callable[[dict[str, Any], str, str], Awaitable[None]],
    ) -> None:
        """接收指定上游通道的消息循环。"""
        状态 = self._获取上游状态(upstream)

        while 状态.配置.enabled:
            if self.获取通道连接(upstream, channel) is not ws:
                self.logger.info(f"检测到通道连接已替换，结束旧接收循环: upstream={upstream}, channel={channel}")
                return

            if not self.通道已连接(upstream, channel):
                await asyncio.sleep(1)
                continue

            try:
                message_str = await ws.recv()
                message = json.loads(message_str)
                await on_message(message, upstream, channel)
            except websockets.exceptions.ConnectionClosed as exc:
                self.logger.warning(f"连接已关闭: upstream={upstream}, channel={channel}, code={exc.code}, reason={exc.reason}")
                self._设置通道连接状态(状态, channel, False)
                self._设置通道连接对象(状态, channel, None)

                if channel == 业务通道名称:
                    return

                if 状态.connected and self.robot_uuid:
                    await self._自动重连通道(upstream, channel)
                    新连接 = self.获取通道连接(upstream, channel)
                    if 新连接 and self.通道已连接(upstream, channel):
                        ws = cast(ClientConnection, 新连接)
                        self.logger.info(f"通道已恢复，继续接收消息: upstream={upstream}, channel={channel}")
                        continue
                return
            except Exception as exc:
                self.logger.error(f"接收消息失败: upstream={upstream}, channel={channel}, error={exc}")
                await asyncio.sleep(1)

    async def 发送心跳消息循环(self, upstream: str, robot_uuid: str, 构建心跳消息: Callable[[str], dict[str, Any]]) -> None:
        """持续向指定上游发送心跳。"""
        self.logger.info(f"心跳循环已启动: upstream={upstream}")

        while True:
            状态 = self._获取上游状态(upstream)
            interval = max(1.0, float(状态.配置.heartbeat_interval))
            if 状态.connected:
                message = 构建心跳消息(robot_uuid)
                await self._发送心跳到上游(upstream, message)
            await asyncio.sleep(interval)

    async def _发送心跳到上游(self, upstream: str, message: dict[str, Any]) -> None:
        await self.发送消息(message, channel=业务通道名称, upstream=upstream)
        状态 = self._获取上游状态(upstream)
        if 状态.connected_audio_upload:
            await self.发送消息(message, channel=音频上传通道名称, upstream=upstream)
        if 状态.connected_audio_download:
            await self.发送消息(message, channel=音频下载通道名称, upstream=upstream)

    def _创建上游状态表(self, 保留旧状态: dict[str, 上游连接状态] | None = None) -> dict[str, 上游连接状态]:
        新状态表: dict[str, 上游连接状态] = {}
        for upstream in (云端上游名称, 电脑端上游名称):
            配置 = self._解析上游配置(upstream)
            旧状态 = (保留旧状态 or {}).get(upstream)
            if 旧状态 is None:
                新状态表[upstream] = 上游连接状态(配置=配置)
                continue

            旧状态.配置 = 配置
            新状态表[upstream] = 旧状态
        return 新状态表

    def _解析上游配置(self, upstream: str) -> 上游配置:
        if upstream == 云端上游名称:
            原始配置 = self.config.get("cloud", {})
            enabled = bool(原始配置.get("enabled", True))
            server_url = self._规范化WebSocket服务地址(
                str(原始配置.get("server_url") or "").strip(),
                默认地址=DEFAULT_SERVER_ADDR,
            )
            business_url = self._解析相对地址(server_url, str(原始配置.get("business_url") or "/api/v1/robot/business").strip())
            audio_upload_url = self._解析相对地址(
                server_url,
                str(原始配置.get("audio_upload_url") or "/api/v1/robot/audio/upload").strip(),
            )
            audio_download_url = self._解析相对地址(
                server_url,
                str(原始配置.get("audio_download_url") or "/api/v1/robot/audio/download").strip(),
            )
            reconnect_interval = float(原始配置.get("reconnect_interval", 5))
            heartbeat_interval = float(原始配置.get("heartbeat_interval", 30))
            return 上游配置(
                名称=upstream,
                enabled=enabled,
                server_url=server_url,
                business_url=business_url,
                audio_upload_url=audio_upload_url,
                audio_download_url=audio_download_url,
                reconnect_interval=reconnect_interval,
                heartbeat_interval=heartbeat_interval,
                支持音频通道=True,
            )

        原始配置 = self.config.get("studio", {})
        enabled = bool(原始配置.get("enabled", False))
        server_url = self._规范化WebSocket服务地址(str(原始配置.get("server_url") or "").strip())
        business_url = self._解析相对地址(server_url, str(原始配置.get("business_url") or "/api/v1/web/business").strip())
        reconnect_interval = float(原始配置.get("reconnect_interval", 5))
        heartbeat_interval = float(原始配置.get("heartbeat_interval", 15))
        return 上游配置(
            名称=upstream,
            enabled=enabled,
            server_url=server_url,
            business_url=business_url,
            audio_upload_url="",
            audio_download_url="",
            reconnect_interval=reconnect_interval,
            heartbeat_interval=heartbeat_interval,
            支持音频通道=False,
        )

    def _解析相对地址(self, server_url: str, raw_url: str) -> str:
        if not raw_url:
            return ""
        if raw_url.startswith("/"):
            if not server_url:
                return ""
            return urljoin(self._确保URL有ws或wss头部(server_url), raw_url)
        return raw_url

    def _规范化WebSocket服务地址(self, url: str, 默认地址: str = "") -> str:
        原始地址 = (url or 默认地址).strip().rstrip("/")
        if not 原始地址:
            return ""
        if 原始地址.startswith("wss://") or 原始地址.startswith("ws://"):
            return 原始地址
        if 原始地址.startswith("https://"):
            return f"wss://{原始地址[8:]}"
        if 原始地址.startswith("http://"):
            return f"ws://{原始地址[7:]}"
        return f"ws://{原始地址}"

    def _确保URL有ws或wss头部(self, url: str) -> str:
        return self._规范化WebSocket服务地址(url)

    def _为URL添加机器人参数(self, url: str, robot_uuid: str) -> str:
        base = self._确保URL有ws或wss头部(url)
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}robotId={robot_uuid}&role=robot"

    async def _连接单个上游(self, upstream: str, robot_uuid: str) -> None:
        状态 = self._获取上游状态(upstream)
        if not 状态.配置.enabled:
            return

        if not 状态.connected:
            await self._连接通道(upstream, 业务通道名称, 状态.配置.business_url, robot_uuid)

        if not 状态.connected or not 状态.配置.支持音频通道:
            return

        if not 状态.connected_audio_upload and 状态.配置.audio_upload_url:
            await self._连接通道(upstream, 音频上传通道名称, 状态.配置.audio_upload_url, robot_uuid)

        if not 状态.connected_audio_download and 状态.配置.audio_download_url:
            await self._连接通道(upstream, 音频下载通道名称, 状态.配置.audio_download_url, robot_uuid)

    async def _连接通道(self, upstream: str, channel: str, url: str, robot_uuid: str) -> bool:
        状态 = self._获取上游状态(upstream)
        if not url:
            if channel == 业务通道名称:
                self.logger.warning(f"未配置业务通道地址: upstream={upstream}")
            return False

        full_url = self._为URL添加机器人参数(url, robot_uuid)
        try:
            self.logger.info(f"正在连接通道: upstream={upstream}, channel={channel}, url={full_url}")
            new_ws = await websockets.connect(full_url)
            旧连接 = self.获取通道连接(upstream, channel)
            if 旧连接:
                try:
                    await 旧连接.close()
                except Exception:
                    pass
            self._设置通道连接对象(状态, channel, new_ws)
            self._设置通道连接状态(状态, channel, True)
            self.logger.info(f"通道连接成功: upstream={upstream}, channel={channel}")
            return True
        except Exception as exc:
            self.logger.error(f"连接通道失败: upstream={upstream}, channel={channel}, error={exc}")
            self._设置通道连接状态(状态, channel, False)
            self._设置通道连接对象(状态, channel, None)
            return False

    async def _断开单个上游(self, upstream: str) -> None:
        状态 = self._获取上游状态(upstream)
        for channel in (业务通道名称, 音频上传通道名称, 音频下载通道名称):
            ws = self.获取通道连接(upstream, channel)
            if ws:
                try:
                    await ws.close()
                except Exception:
                    pass
            self._设置通道连接对象(状态, channel, None)
            self._设置通道连接状态(状态, channel, False)
        状态._重连中通道.clear()
        self.logger.info(f"已断开上游连接: upstream={upstream}")

    def _上游存在活动连接(self, 状态: 上游连接状态) -> bool:
        return bool(
            状态.ws_business
            or 状态.ws_audio_upload
            or 状态.ws_audio_download
            or 状态.connected
            or 状态.connected_audio_upload
            or 状态.connected_audio_download
        )

    def _获取上游状态(self, upstream: str) -> 上游连接状态:
        状态 = self._上游状态.get(upstream)
        if 状态 is None:
            raise KeyError(f"未知上游: {upstream}")
        return 状态

    def _设置通道连接状态(self, 状态: 上游连接状态, channel: str, connected: bool) -> None:
        if channel == 业务通道名称:
            状态.connected = connected
            return
        if channel == 音频上传通道名称:
            状态.connected_audio_upload = connected
            return
        if channel == 音频下载通道名称:
            状态.connected_audio_download = connected

    def _设置通道连接对象(
        self,
        状态: 上游连接状态,
        channel: str,
        ws: Optional[ClientConnection],
    ) -> None:
        if channel == 业务通道名称:
            状态.ws_business = ws
            return
        if channel == 音频上传通道名称:
            状态.ws_audio_upload = ws
            return
        if channel == 音频下载通道名称:
            状态.ws_audio_download = ws

    async def _重连单个通道(self, upstream: str, channel: str) -> bool:
        状态 = self._获取上游状态(upstream)
        if not self.robot_uuid:
            self.logger.error(f"无法重连通道，robot_uuid 未设置: upstream={upstream}, channel={channel}")
            return False

        if channel in 状态._重连中通道:
            self.logger.debug(f"通道正在重连中，跳过: upstream={upstream}, channel={channel}")
            return False

        if channel == 音频上传通道名称:
            url = 状态.配置.audio_upload_url
        elif channel == 音频下载通道名称:
            url = 状态.配置.audio_download_url
        else:
            url = 状态.配置.business_url

        状态._重连中通道.add(channel)
        try:
            return await self._连接通道(upstream, channel, url, self.robot_uuid)
        finally:
            状态._重连中通道.discard(channel)

    async def _自动重连通道(self, upstream: str, channel: str) -> None:
        状态 = self._获取上游状态(upstream)
        max_retries = 3
        retry_delay = max(1.0, 状态.配置.reconnect_interval)

        for attempt in range(1, max_retries + 1):
            if not 状态.connected:
                return
            if attempt > 1:
                await asyncio.sleep(retry_delay)
            success = await self._重连单个通道(upstream, channel)
            if success:
                return
