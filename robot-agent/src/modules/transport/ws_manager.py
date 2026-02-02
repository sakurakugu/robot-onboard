import asyncio
import json
import re
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import urlparse, urlunparse

import websockets
from websockets import ClientConnection

from sparkrobot_common import get_logger


class WebSocketManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = get_logger("robot-agent")
        self.ws_business: Optional[ClientConnection] = None
        self.ws_control: Optional[ClientConnection] = None
        self.ws_audio_upload: Optional[ClientConnection] = None
        self.ws_audio_download: Optional[ClientConnection] = None
        self.connected = False
        self.connected_control = False
        self.connected_audio_upload = False
        self.connected_audio_download = False
        self.robot_uuid: Optional[str] = None
        self._reconnecting_channels: set = set()  # 正在重连的通道

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
        ws_path = server_cfg.get("ws_path") or "/api/v1/interaction/connect"
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
        self.robot_uuid = None
        self._reconnecting_channels.clear()
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
        
        # 如果通道未连接且可以重连（非业务通道或有robot_uuid），尝试重连
        if (not ws or not is_connected) and self.robot_uuid and channel != "business":
            self.logger.info(f"通道 {channel} 未连接，尝试重连...")
            reconnected = await self._重连单个通道(channel)
            if reconnected:
                # 重新获取连接
                ws, is_connected = ws_map.get(channel, (None, False))
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
            self.logger.debug(f"发送消息到 {channel}: {message['type']}")
        except Exception as e:
            self.logger.error(f"发送消息失败({channel}): {e}")
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
        # 获取通道状态的引用
        status_map = {
            "business": lambda: self.connected,
            "control": lambda: self.connected_control,
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
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning(f"连接已关闭: {channel}")
                if channel == "business":
                    self.connected = False
                elif channel == "control":
                    self.connected_control = False
                elif channel == "audio_upload":
                    self.connected_audio_upload = False
                elif channel == "audio_download":
                    self.connected_audio_download = False
                
                # 如果不是主连接断开，尝试重连该通道
                if channel != "business" and self.connected and self.robot_uuid:
                    self.logger.info(f"尝试重连通道: {channel}")
                    asyncio.create_task(self._自动重连通道(channel, on_message))
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
                
                # 为 audio_upload 通道也发送心跳
                if self.connected_audio_upload:
                    await self.发送消息(message, channel="audio_upload")
                
                # 为 audio_download 通道也发送心跳
                if self.connected_audio_download:
                    await self.发送消息(message, channel="audio_download")
    
    async def _重连单个通道(self, channel: str) -> bool:
        """ 重连单个通道 """
        if not self.robot_uuid:
            self.logger.error(f"无法重连 {channel}，robot_uuid 未设置")
            return False
        
        # 防止重复重连
        if channel in self._reconnecting_channels:
            self.logger.debug(f"通道 {channel} 正在重连中，跳过")
            return False
        
        self._reconnecting_channels.add(channel)
        
        try:
            urls = self._解析服务器URL配置()
            
            if channel == "control":
                control_url = urls.get("control")
                if not control_url:
                    self.logger.warning("未配置控制通道地址")
                    return False
                control_full = self._为URL添加机器人参数(control_url, self.robot_uuid)
                self.logger.info(f"重连控制通道: {control_full}")
                if self.ws_control:
                    try:
                        await self.ws_control.close()
                    except:
                        pass
                self.ws_control = await websockets.connect(control_full)
                self.connected_control = True
                self.logger.info("控制通道重连成功")
                return True
                
            elif channel == "audio_upload":
                audio_upload_url = urls.get("audio_upload")
                if not audio_upload_url:
                    self.logger.warning("未配置音频上传通道地址")
                    return False
                audio_upload_full = self._为URL添加机器人参数(audio_upload_url, self.robot_uuid)
                self.logger.info(f"重连音频上传通道: {audio_upload_full}")
                if self.ws_audio_upload:
                    try:
                        await self.ws_audio_upload.close()
                    except:
                        pass
                self.ws_audio_upload = await websockets.connect(audio_upload_full)
                self.connected_audio_upload = True
                self.logger.info("音频上传通道重连成功")
                return True
                
            elif channel == "audio_download":
                audio_download_url = urls.get("audio_download")
                if not audio_download_url:
                    self.logger.warning("未配置音频下载通道地址")
                    return False
                audio_download_full = self._为URL添加机器人参数(audio_download_url, self.robot_uuid)
                self.logger.info(f"重连音频下载通道: {audio_download_full}")
                if self.ws_audio_download:
                    try:
                        await self.ws_audio_download.close()
                    except:
                        pass
                self.ws_audio_download = await websockets.connect(audio_download_full)
                self.connected_audio_download = True
                self.logger.info("音频下载通道重连成功")
                return True
            
            else:
                self.logger.warning(f"不支持重连通道: {channel}")
                return False
                
        except Exception as e:
            self.logger.error(f"重连通道 {channel} 失败: {e}")
            return False
        finally:
            self._reconnecting_channels.discard(channel)
    
    async def _自动重连通道(self, channel: str, on_message: Callable[[Dict[str, Any]], Awaitable[None]]) -> None:
        """ 自动重连通道并重启接收循环 """
        max_retries = 3
        retry_delay = 5  # 秒
        
        for attempt in range(1, max_retries + 1):
            self.logger.info(f"尝试重连 {channel} (第 {attempt}/{max_retries} 次)")
            await asyncio.sleep(retry_delay)
            
            if not self.connected:
                self.logger.info(f"主连接已断开，停止重连 {channel}")
                return
            
            success = await self._重连单个通道(channel)
            if success:
                # 重连成功，重启接收循环
                ws_map = {
                    "control": self.ws_control,
                    "audio_upload": self.ws_audio_upload,
                    "audio_download": self.ws_audio_download,
                }
                ws = ws_map.get(channel)
                if ws:
                    self.logger.info(f"重启 {channel} 接收循环")
                    asyncio.create_task(self.接受消息循环(channel, ws, on_message))
                return
            
            if attempt < max_retries:
                self.logger.warning(f"重连 {channel} 失败，{retry_delay} 秒后重试...")
        
        self.logger.error(f"重连 {channel} 失败，已达到最大重试次数")
