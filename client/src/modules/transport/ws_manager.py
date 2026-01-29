import asyncio
import json
import re
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import urlparse, urlunparse

import websockets
from websockets import ClientConnection


class WebSocketManager:
    def __init__(self, config: Dict[str, Any], logger):
        self.config = config
        self.logger = logger
        self.ws_business: Optional[ClientConnection] = None
        self.ws_control: Optional[ClientConnection] = None
        self.ws_audio_upload: Optional[ClientConnection] = None
        self.ws_audio_download: Optional[ClientConnection] = None
        self.connected = False
        self.connected_control = False
        self.connected_audio_upload = False
        self.connected_audio_download = False

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
        ws_path = server_cfg.get("ws_path") or "/api/v1/conversation/connect"
        business_url = server_cfg.get("business_url") or server_cfg.get("url")
        control_url = server_cfg.get("control_url")
        audio_upload_url = server_cfg.get("audio_upload_url")
        audio_download_url = server_cfg.get("audio_download_url")
        base_url = server_cfg.get("base_url")

        if base_url:
            if not control_url:
                control_url = self._替换URL的端口和路径(base_url, 9000, ws_path)
            if not business_url:
                business_url = self._替换URL的端口和路径(base_url, 9001, ws_path)
            if not audio_upload_url:
                audio_upload_url = self._替换URL的端口和路径(base_url, 9002, ws_path)
            if not audio_download_url:
                audio_download_url = self._替换URL的端口和路径(base_url, 9003, ws_path)

        if business_url and not control_url:
            control_url = self._替换URL的端口和路径(business_url, 9000, ws_path)
        if business_url and not audio_upload_url:
            audio_upload_url = self._替换URL的端口和路径(business_url, 9002, ws_path)
        if business_url and not audio_download_url:
            audio_download_url = self._替换URL的端口和路径(business_url, 9003, ws_path)

        return {
            "business": business_url or "",
            "control": control_url or "",
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
        try:
            urls = self._解析服务器URL配置()
            business_url = urls.get("business")
            if not business_url:
                raise ValueError("未配置业务通道地址（server.business_url 或 server.url）")

            business_full = self._为URL添加机器人参数(business_url, robot_uuid)
            self.logger.info(f"正在连接业务通道: {business_full}")
            self.ws_business = await websockets.connect(business_full)
            self.connected = True

            control_url = urls.get("control")
            if control_url:
                control_full = self._为URL添加机器人参数(control_url, robot_uuid)
                try:
                    self.logger.info(f"正在连接控制通道: {control_full}")
                    self.ws_control = await websockets.connect(control_full)
                    self.connected_control = True
                except Exception as e:
                    self.logger.warning(f"控制通道连接失败: {e}")

            audio_upload_url = urls.get("audio_upload")
            if audio_upload_url:
                audio_upload_full = self._为URL添加机器人参数(audio_upload_url, robot_uuid)
                try:
                    self.logger.info(f"正在连接音频上传通道: {audio_upload_full}")
                    self.ws_audio_upload = await websockets.connect(audio_upload_full)
                    self.connected_audio_upload = True
                except Exception as e:
                    self.logger.warning(f"音频上传通道连接失败: {e}")

            audio_download_url = urls.get("audio_download")
            if audio_download_url:
                audio_download_full = self._为URL添加机器人参数(audio_download_url, robot_uuid)
                try:
                    self.logger.info(f"正在连接音频下载通道: {audio_download_full}")
                    self.ws_audio_download = await websockets.connect(audio_download_full)
                    self.connected_audio_download = True
                except Exception as e:
                    self.logger.warning(f"音频下载通道连接失败: {e}")

            self.logger.info(f"已连接到服务器，机器狗UUID: {robot_uuid}")
            return True
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            self.connected = False
            return False

    async def 断开连接(self) -> None:
        """ 断开所有WebSocket通道 """
        if self.ws_business:
            await self.ws_business.close()
            self.ws_business = None
        if self.ws_control:
            await self.ws_control.close()
            self.ws_control = None
        if self.ws_audio_upload:
            await self.ws_audio_upload.close()
            self.ws_audio_upload = None
        if self.ws_audio_download:
            await self.ws_audio_download.close()
            self.ws_audio_download = None
        self.connected = False
        self.connected_control = False
        self.connected_audio_upload = False
        self.connected_audio_download = False
        self.logger.info("已断开连接")

    async def 发送消息(self, message: Dict[str, Any], channel: str = "business") -> None:
        """ 发送消息到指定通道 """
        ws_map = {
            "business": (self.ws_business, self.connected),
            "control": (self.ws_control, self.connected_control),
            "audio_upload": (self.ws_audio_upload, self.connected_audio_upload),
            "audio_download": (self.ws_audio_download, self.connected_audio_download),
        }
        ws, is_connected = ws_map.get(channel, (None, False))
        if not ws or not is_connected:
            self.logger.warning(f"通道未连接，无法发送消息: {channel}")
            return

        try:
            await ws.send(json.dumps(message))
            self.logger.debug(f"发送消息: {message['type']}")
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
            if channel == "business":
                self.connected = False
            elif channel == "control":
                self.connected_control = False
            elif channel == "audio_upload":
                self.connected_audio_upload = False
            elif channel == "audio_download":
                self.connected_audio_download = False

    async def 接受消息循环(
        self, channel: str, ws: ClientConnection, on_message: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """ 接收指定通道的消息循环 """
        # 当连接关闭时，跳出循环(到时候记得搞局部重连)
        while self.connected:
            try:
                message_str = await ws.recv()
                message = json.loads(message_str)
                await on_message(message)
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning(f"连接已关闭: {channel}")
                if channel == "business":
                    self.connected = False
                elif channel == "control":
                    self.connected_control = False
                elif channel == "audio_download":
                    self.connected_audio_download = False
                break
            except Exception as e:
                self.logger.error(f"接收消息失败({channel}): {e}")
                await asyncio.sleep(1)

    async def 发送心跳消息循环(self, robot_uuid: str, 构建心跳消息: Callable[[str], Dict[str, Any]]) -> None:
        """ 发送心跳消息循环 """
        interval = self.config.get("server", {}).get("heartbeat_interval", 30)
        while self.connected:
            await asyncio.sleep(interval)
            if self.connected:
                message = 构建心跳消息(robot_uuid)
                if self.connected_control:
                    await self.发送消息(message, channel="control")
                else:
                    await self.发送消息(message, channel="business")
