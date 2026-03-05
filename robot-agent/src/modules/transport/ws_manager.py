import asyncio
import json
import re
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import websockets
from sparkrobot_common import DEFAULT_SERVER_ADDR, get_logger
from websockets import ClientConnection


class WebSocketManager:
    # 通道名称 -> 连接状态属性名
    _CHANNEL_STATUS_ATTRS: Dict[str, str] = {
        "business": "connected",
        "audio_upload": "connected_audio_upload",
        "audio_download": "connected_audio_download",
    }
    # 二级通道配置（不含business）: 通道名称 -> (ws属性名, url配置键)
    _SECONDARY_CHANNEL_CONFIG: Dict[str, tuple] = {
        "audio_upload": ("ws_audio_upload", "audio_upload"),
        "audio_download": ("ws_audio_download", "audio_download"),
    }

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger("robot-agent")
        self.ws_business: Optional[ClientConnection] = None
        self.ws_audio_upload: Optional[ClientConnection] = None
        self.ws_audio_download: Optional[ClientConnection] = None
        self.connected = False
        self.connected_audio_upload = False
        self.connected_audio_download = False
        self.robot_uuid: Optional[str] = None
        self._reconnecting_channels: set = set()  # 正在重连的通道

    def _设置通道连接状态(self, channel: str, connected: bool) -> None:
        """设置指定通道的连接状态"""
        attr = self._CHANNEL_STATUS_ATTRS.get(channel)
        if attr:
            setattr(self, attr, connected)

    def _确保URL有ws或wss头部(self, url: str) -> str:
        """ _ensure_scheme """
        if re.match(r"^wss?://", url):
            return url
        return f"ws://{url}"

    def _替换URL的端口和路径(self, url: str, port: int, path: str) -> str:
        """ _replace_port_and_path """
        base = self._确保URL有ws或wss头部(url)
        parsed = urlparse(base)
        host = parsed.hostname or ""
        scheme = parsed.scheme or "ws"
        netloc = f"{host}:{port}"
        return urlunparse((scheme, netloc, path, "", "", ""))

    def _解析服务器URL配置(self) -> Dict[str, str]:
        """ _resolve_server_urls """
        server_cfg = self.config.get("server", {})
        server_url = server_cfg.get("server_url") or f"ws://{DEFAULT_SERVER_ADDR}:9000"

        business_url = server_cfg.get("business_url") or server_cfg.get("url")
        if business_url and business_url.startswith("/"):
            business_url = urljoin(server_url, business_url)

        audio_upload_url = server_cfg.get("audio_upload_url")
        if audio_upload_url and audio_upload_url.startswith("/"):
            audio_upload_url = urljoin(server_url, audio_upload_url)

        audio_download_url = server_cfg.get("audio_download_url")
        if audio_download_url and audio_download_url.startswith("/"):
            audio_download_url = urljoin(server_url, audio_download_url)

        # 如果未配置，使用business_url作为所有通道的URL
        if business_url:
            if not audio_upload_url:
                audio_upload_url = business_url
            if not audio_download_url:
                audio_download_url = business_url

        return {
            "business": business_url or "",
            "audio_upload": audio_upload_url or "",
            "audio_download": audio_download_url or "",
        }

    def _为URL添加机器人参数(self, url: str, robot_uuid: str) -> str:
        """ _append_robot_params """
        base = self._确保URL有ws或wss头部(url)
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}robotId={robot_uuid}&role=robot"

    async def 连接(self, robot_uuid: str) -> bool:
        """ 连接所有WebSocket通道 """
        self.robot_uuid = robot_uuid
        try:
            urls = self._解析服务器URL配置()
            business_url = urls.get("business")
            if not business_url:
                raise ValueError("未配置业务通道地址（server.business_url 或 server.url）")

            business_full = self._为URL添加机器人参数(business_url, robot_uuid)
            self.logger.info(f"正在连接业务通道: {business_full}")
            self.ws_business = await websockets.connect(business_full)
            self.connected = True
            self.logger.info("✓ 业务通道连接成功")

            audio_upload_url = urls.get("audio_upload")
            if audio_upload_url:
                audio_upload_full = self._为URL添加机器人参数(audio_upload_url, robot_uuid)
                try:
                    self.logger.info(f"正在连接音频上传通道: {audio_upload_full}")
                    self.ws_audio_upload = await websockets.connect(audio_upload_full)
                    self.connected_audio_upload = True
                    self.logger.info("✓ 音频上传通道连接成功")
                except Exception as e:
                    self.logger.warning(f"✗ 音频上传通道连接失败: {e}")

            audio_download_url = urls.get("audio_download")
            if audio_download_url:
                audio_download_full = self._为URL添加机器人参数(audio_download_url, robot_uuid)
                try:
                    self.logger.info(f"正在连接音频下载通道: {audio_download_full}")
                    self.ws_audio_download = await websockets.connect(audio_download_full)
                    self.connected_audio_download = True
                    self.logger.info("✓ 音频下载通道连接成功")
                except Exception as e:
                    self.logger.warning(f"✗ 音频下载通道连接失败: {e}")

            connected_count = sum([
                self.connected,
                self.connected_audio_upload,
                self.connected_audio_download
            ])
            self.logger.info(f"已连接到服务器，机器狗UUID: {robot_uuid}，成功通道: {connected_count}/3")
            return True
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            self.connected = False
            return False

    async def 断开连接(self) -> None:
        """ 断开所有WebSocket通道 """
        _ws_attrs = [
            ("ws_business", "connected"),
            ("ws_audio_upload", "connected_audio_upload"),
            ("ws_audio_download", "connected_audio_download"),
        ]
        for ws_attr, connected_attr in _ws_attrs:
            ws = getattr(self, ws_attr)
            if ws:
                await ws.close()
                setattr(self, ws_attr, None)
            setattr(self, connected_attr, False)
        self.robot_uuid = None
        self._reconnecting_channels.clear()
        self.logger.info("已断开连接")

    async def 发送消息(self, message: Dict[str, Any], channel: str = "business") -> None:
        """ 发送消息到指定通道 """
        ws_map = {
            "business": (self.ws_business, self.connected),
            "audio_upload": (self.ws_audio_upload, self.connected_audio_upload),
            "audio_download": (self.ws_audio_download, self.connected_audio_download),
        }
        ws, is_connected = ws_map.get(channel, (None, False))

        # 如果通道未连接且可以重连（非业务通道或有robot_uuid），尝试重连
        if (not ws or not is_connected) and self.robot_uuid and channel != "business":
            self.logger.info(f"通道 {channel} 未连接，尝试重连...")
            reconnected = await self._重连单个通道(channel)
            if reconnected:
                # 重新获取连接
                ws, is_connected = ws_map.get(channel, (None, False))
                ws_map = {
                    "business": (self.ws_business, self.connected),
                    "audio_upload": (self.ws_audio_upload, self.connected_audio_upload),
                    "audio_download": (self.ws_audio_download, self.connected_audio_download),
                }
                ws, is_connected = ws_map.get(channel, (None, False))

        if not ws or not is_connected:
            self.logger.warning(f"通道未连接，无法发送消息: {channel}")
            return

        try:
            await ws.send(json.dumps(message))
            self.logger.debug(f"发送消息到 {channel}: {message['type']}")
        except Exception as e:
            self.logger.error(f"发送消息失败({channel}): {e}")
            self._设置通道连接状态(channel, False)

    async def 接受消息循环(
        self, channel: str, ws: ClientConnection, on_message: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """ 接收指定通道的消息循环 """
        # 获取通道状态的引用
        status_map = {
            "business": lambda: self.connected,
            "audio_upload": lambda: self.connected_audio_upload,
            "audio_download": lambda: self.connected_audio_download,
        }

        get_status = status_map.get(channel, lambda: self.connected)

        while self.connected:
            # 如果当前通道状态变为未连接（可能被其他地方断开），退出循环
            if not get_status():
                self.logger.info(f"通道 {channel} 已标记为断开，退出接收循环")
                break

            try:
                message_str = await ws.recv()
                message = json.loads(message_str)
                await on_message(message)
            except websockets.exceptions.ConnectionClosed as e:
                self.logger.warning(f"连接已关闭: {channel}, code={e.code}, reason={e.reason}")
                self._设置通道连接状态(channel, False)
                if channel == "business":
                    self.logger.info("业务通道断开，主连接将触发重连")

                # 如果不是主连接断开，尝试重连该通道（不阻塞当前循环）
                if channel != "business" and self.connected and self.robot_uuid:
                    self.logger.info(f"尝试后台重连通道: {channel}")
                    asyncio.create_task(self._自动重连通道(channel, on_message))
                # 不要 break，让任务正常结束但不触发外层重连
                return
            except Exception as e:
                self.logger.error(f"接收消息失败({channel}): {e}")
                await asyncio.sleep(1)

    async def 发送心跳消息循环(self, robot_uuid: str, 构建心跳消息: Callable[[str], Dict[str, Any]]) -> None:
        """ 发送心跳消息循环 """
        interval = self.config.get("server", {}).get("heartbeat_interval", 30)
        self.logger.info(f"心跳循环已启动，间隔: {interval}秒")

        # 连接建立后立即发送首次心跳，避免等待
        if self.connected:
            message = 构建心跳消息(robot_uuid)
            await self._发送心跳到所有通道(message)

        while self.connected:
            await asyncio.sleep(interval)
            if self.connected:
                message = 构建心跳消息(robot_uuid)
                await self._发送心跳到所有通道(message)

    async def _发送心跳到所有通道(self, message: Dict[str, Any]) -> None:
        """ 发送心跳到所有已连接的通道，确保每个通道的 lastActiveAt 都得到刷新 """
        sent_channels = []

        channel_checks = [
            ("business", self.connected),
            ("audio_upload", self.connected_audio_upload),
            ("audio_download", self.connected_audio_download),
        ]

        for channel, is_connected in channel_checks:
            if is_connected:
                try:
                    await self.发送消息(message, channel=channel)
                    sent_channels.append(channel)
                except Exception as e:
                    self.logger.warning(f"发送心跳到 {channel} 通道失败: {e}")

        if sent_channels:
            self.logger.debug(f"已发送心跳到通道: {', '.join(sent_channels)}")

    async def _重连单个通道(self, channel: str) -> bool:
        """ 重连单个通道 """
        if not self.robot_uuid:
            self.logger.error(f"无法重连 {channel}，robot_uuid 未设置")
            return False

        # 防止重复重连
        if channel in self._reconnecting_channels:
            self.logger.debug(f"通道 {channel} 正在重连中，跳过")
            return False

        if channel not in self._SECONDARY_CHANNEL_CONFIG:
            self.logger.warning(f"不支持重连通道: {channel}")
            return False

        self._reconnecting_channels.add(channel)
        ws_attr, url_key = self._SECONDARY_CHANNEL_CONFIG[channel]
        try:
            urls = self._解析服务器URL配置()
            url = urls.get(url_key)
            if not url:
                self.logger.warning(f"未配置{channel}通道地址")
                return False

            full_url = self._为URL添加机器人参数(url, self.robot_uuid)
            self.logger.info(f"重连{channel}通道: {full_url}")

            old_ws = getattr(self, ws_attr)
            if old_ws:
                try:
                    await old_ws.close()
                except Exception:
                    pass

            new_ws = await websockets.connect(full_url)
            setattr(self, ws_attr, new_ws)
            self._设置通道连接状态(channel, True)
            self.logger.info(f"{channel}通道重连成功")
            return True

        except Exception as e:
            self.logger.error(f"重连通道 {channel} 失败: {e}")
            return False
        finally:
            self._reconnecting_channels.discard(channel)

    async def _自动重连通道(self, channel: str, on_message: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """ 自动重连通道并重启接收循环 """
        max_retries = 3
        retry_delay = 5  # 秒

        # 防止重复重连
        if channel in self._reconnecting_channels:
            self.logger.debug(f"通道 {channel} 已在重连中，跳过")
            return

        self._reconnecting_channels.add(channel)

        try:
            for attempt in range(1, max_retries + 1):
                if not self.connected:
                    self.logger.info(f"主连接已断开，停止重连 {channel}")
                    return

                self.logger.info(f"尝试重连 {channel} (第 {attempt}/{max_retries} 次，间隔: {retry_delay}秒)")

                # 等待一段时间再重连，避免立即重连导致的循环
                if attempt > 1:
                    await asyncio.sleep(retry_delay)
                else:
                    # 第一次重连也稍微等待一下，避免服务器还没准备好
                    await asyncio.sleep(1)

                if not self.connected:
                    self.logger.info(f"主连接已断开，停止重连 {channel}")
                    return

                success = await self._重连单个通道(channel)
                if success:
                    # 重连成功，重启接收循环
                    ws_attr = self._SECONDARY_CHANNEL_CONFIG.get(channel, ("",))[0]
                    ws = getattr(self, ws_attr, None) if ws_attr else None
                    if ws:
                        self.logger.info(f"✓ 通道 {channel} 重连成功，重启接收循环")
                        # 创建新的接收循环任务
                        asyncio.create_task(self.接受消息循环(channel, ws, on_message))
                    return

                if attempt < max_retries:
                    self.logger.warning(f"✗ 重连 {channel} 失败，{retry_delay} 秒后重试...")

            self.logger.error(f"✗ 重连 {channel} 失败，已达到最大重试次数 ({max_retries})")
        finally:
            self._reconnecting_channels.discard(channel)
