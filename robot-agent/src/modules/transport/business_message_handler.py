import asyncio
import hashlib
import re
import tarfile
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import httpx
from sparkrobot_common import get_logger

from src.modules.actions.mapping import 处理动作指令, 处理文本响应
from src.modules.audio.playback import 停止当前音频播放, 处理音频响应并播放
from src.modules.runtime.runtime_client import 本地运行时客户端
from src.modules.transport.message_sender import 消息发送器
from src.modules.vision import capture_photo

logger = get_logger("robot-agent")


def _解出整包内子包(full_package_path: Path, packages_dir: Path) -> list[str]:
    """将 full 整包内的 packages/*.tar.gz 解到 packages 目录。"""
    extracted: list[str] = []
    with tarfile.open(full_package_path, "r:*") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            member_path = Path(member.name)
            if "packages" not in member_path.parts:
                continue
            if member_path.suffixes[-2:] != [".tar", ".gz"]:
                continue

            target_path = packages_dir / member_path.name
            file_obj = tar.extractfile(member)
            if file_obj is None:
                continue
            target_path.write_bytes(file_obj.read())
            extracted.append(member_path.name)
    return extracted


class 业务消息处理器:
    """负责处理云端下发的业务消息。"""

    def __init__(
        self,
        message_sender: 消息发送器,
        robot_server_client: Any,
        workspace: Path,
        获取配置: Callable[[], dict[str, Any]],
        获取动作执行器: Callable[[], Any],
        提交动作: Callable[[str, dict[str, Any] | None], bool],
        joystick_controller: Any,
        audio_capture: Any,
        sdk_mode_manager: Any,
        runtime_client: 本地运行时客户端,
        设置云端媒体租约到期时间: Callable[[float], None],
    ) -> None:
        self.message_sender = message_sender
        self.robot_server_client = robot_server_client
        self.workspace = workspace
        self._获取配置 = 获取配置
        self._获取动作执行器 = 获取动作执行器
        self._提交动作 = 提交动作
        self.joystick_controller = joystick_controller
        self.audio_capture = audio_capture
        self.sdk_mode_manager = sdk_mode_manager
        self.runtime_client = runtime_client
        self._设置云端媒体租约到期时间 = 设置云端媒体租约到期时间
        self.message_handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "text_response": self.处理文本响应,
            "audio_response": self.处理音频响应并播放,
            "action_command": self.处理动作指令,
            "navigation_command": self.处理导航命令,
            "map_command": self.处理地图命令,
            "patrol_command": self.处理巡逻命令,
            "control_command": self.处理控制指令,
            "audio_control": self.处理音频控制,
            "stop_audio": self.处理停止音频播放,
            "error": self.处理服务器错误,
            "audio_stream_start": self.处理音频流开始,
            "audio_stream_chunk": self.处理音频流数据块,
            "audio_stream_end": self.处理音频流结束,
            "camera_capture": self.处理相机拍照,
            "volume_get": self.处理音量获取,
            "volume_set": self.处理音量设置,
            "volume_mute": self.处理设置静音,
            "config_get": self.处理配置获取,
            "config_update": self.处理配置更新,
            "sdk_mode_set": self.处理SDK模式设置,
            "sdk_mode_get": self.处理SDK模式获取,
            "cloud_stream_control": self.处理云端视频推流控制,
            "log_mark": self.处理日志标记,
            "package_download": self.处理安装包下载,
        }

    def _当前配置(self) -> dict[str, Any]:
        return self._获取配置()

    async def 处理相机拍照(self, data: dict[str, Any]) -> None:
        """处理相机拍照消息。"""
        request_id = data.get("requestId", "")
        logger.info(f"收到拍照请求: {request_id}")

        try:
            loop = asyncio.get_event_loop()
            rtsp_url = "rtsp://127.0.0.1:8554/test"
            image_base64 = await loop.run_in_executor(None, capture_photo, rtsp_url, 5)

            if image_base64:
                await self.message_sender.发送拍照响应(request_id, True, image_base64)
                logger.info(f"拍照成功: {request_id}")
            else:
                await self.message_sender.发送拍照响应(request_id, False, None, "拍照失败")
                logger.error(f"拍照失败: {request_id}")

        except Exception as e:
            logger.error(f"处理拍照请求时出错: {e}", exc_info=True)
            await self.message_sender.发送拍照响应(request_id, False, None, str(e))

    async def 处理导航命令(self, data: dict[str, Any]) -> None:
        """处理导航命令消息。"""
        request_id = str(data.get("requestId", ""))
        logger.info(f"收到导航命令: requestId={request_id}, data={data}")
        try:
            result = await self.runtime_client.执行导航命令(data)
            await self.message_sender.发送导航响应(request_id, True, result)
            logger.info(f"导航命令执行成功: {request_id}")
        except Exception as exc:
            error = self.runtime_client.格式化异常(exc)
            await self.message_sender.发送导航响应(request_id, False, None, error["message"], error["code"])
            logger.error(f"导航命令执行失败: requestId={request_id}, error={error}")

    async def 处理地图命令(self, data: dict[str, Any]) -> None:
        """处理地图命令消息。"""
        request_id = str(data.get("requestId", ""))
        logger.info(f"收到地图命令: requestId={request_id}, data={data}")
        try:
            result = await self.runtime_client.执行地图命令(data)
            await self.message_sender.发送地图响应(request_id, True, result)
            logger.info(f"地图命令执行成功: {request_id}")
        except Exception as exc:
            error = self.runtime_client.格式化异常(exc)
            await self.message_sender.发送地图响应(request_id, False, None, error["message"], error["code"])
            logger.error(f"地图命令执行失败: requestId={request_id}, error={error}")

    async def 处理巡逻命令(self, data: dict[str, Any]) -> None:
        """处理巡逻命令消息。"""
        request_id = str(data.get("requestId", ""))
        logger.info(f"收到巡逻命令: requestId={request_id}, data={data}")
        try:
            result = await self.runtime_client.执行巡逻命令(data)
            await self.message_sender.发送巡逻响应(request_id, True, result)
            logger.info(f"巡逻命令执行成功: {request_id}")
        except Exception as exc:
            error = self.runtime_client.格式化异常(exc)
            await self.message_sender.发送巡逻响应(request_id, False, None, error["message"], error["code"])
            logger.error(f"巡逻命令执行失败: requestId={request_id}, error={error}")

    async def 处理音量获取(self, data: dict[str, Any]) -> None:
        """处理音量获取消息。"""
        request_id = data.get("requestId", "")
        logger.info(f"收到音量获取请求: {request_id}")
        try:
            result = await self.robot_server_client.调用API("GET", "/api/v1/volume")
            if result.get("success"):
                await self.message_sender.发送音量响应(request_id, True, result.get("data"))
                logger.info(f"音量获取成功: {request_id}")
            else:
                await self.message_sender.发送音量响应(request_id, False, None, result.get("error", "获取音量失败"))
                logger.error(f"音量获取失败: {request_id}")
        except Exception as e:
            logger.error(f"处理音量获取请求时出错: {e}", exc_info=True)
            await self.message_sender.发送音量响应(request_id, False, None, str(e))

    async def 处理音量设置(self, data: dict[str, Any]) -> None:
        """处理音量设置消息。"""
        request_id = data.get("requestId", "")
        volume = data.get("volume")
        logger.info(f"收到音量设置请求: {request_id}, 音量: {volume}")
        try:
            result = await self.robot_server_client.调用API("POST", "/api/v1/volume", {"volume": volume})
            if result.get("success"):
                await self.message_sender.发送音量响应(request_id, True, {"message": result.get("message")})
                logger.info(f"音量设置成功: {request_id}")
            else:
                await self.message_sender.发送音量响应(request_id, False, None, result.get("error", "设置音量失败"))
                logger.error(f"音量设置失败: {request_id}")
        except Exception as e:
            logger.error(f"处理音量设置请求时出错: {e}", exc_info=True)
            await self.message_sender.发送音量响应(request_id, False, None, str(e))

    async def 处理设置静音(self, data: dict[str, Any]) -> None:
        """处理设置静音消息。"""
        request_id = data.get("requestId", "")
        mute = data.get("mute")
        logger.info(f"收到设置静音请求: {request_id}, 静音: {mute}")
        try:
            result = await self.robot_server_client.调用API("POST", "/api/v1/volume/mute", {"mute": mute})
            if result.get("success"):
                await self.message_sender.发送音量响应(request_id, True, {"message": result.get("message")})
                logger.info(f"设置静音成功: {request_id}")
            else:
                await self.message_sender.发送音量响应(request_id, False, None, result.get("error", "设置静音失败"))
                logger.error(f"设置静音失败: {request_id}")
        except Exception as e:
            logger.error(f"处理设置静音请求时出错: {e}", exc_info=True)
            await self.message_sender.发送音量响应(request_id, False, None, str(e))

    async def 处理配置获取(self, data: dict[str, Any]) -> None:
        """处理配置获取消息。"""
        request_id = data.get("requestId", "")
        logger.info(f"收到配置获取请求: {request_id}")
        try:
            result = await self.robot_server_client.调用API("GET", "/api/v1/config")
            if result.get("success"):
                await self.message_sender.发送配置响应(request_id, True, result.get("config"))
                logger.info(f"配置获取成功: {request_id}")
            else:
                await self.message_sender.发送配置响应(request_id, False, None, result.get("error", "获取配置失败"))
                logger.error(f"配置获取失败: {request_id}")
        except Exception as e:
            logger.error(f"处理配置获取请求时出错: {e}", exc_info=True)
            await self.message_sender.发送配置响应(request_id, False, None, str(e))

    async def 处理配置更新(self, data: dict[str, Any]) -> None:
        """处理配置更新消息。"""
        request_id = data.get("requestId", "")
        config_data = data.get("config", {})
        logger.info(f"收到配置更新请求: {request_id}")
        try:
            result = await self.robot_server_client.调用API("POST", "/api/v1/config", config_data)
            if result.get("success"):
                await self.message_sender.发送配置响应(
                    request_id,
                    True,
                    {"message": result.get("message"), "results": result.get("results")},
                )
                logger.info(f"配置更新成功: {request_id}")
            else:
                await self.message_sender.发送配置响应(request_id, False, None, result.get("error", "更新配置失败"))
                logger.error(f"配置更新失败: {request_id}")
        except Exception as e:
            logger.error(f"处理配置更新请求时出错: {e}", exc_info=True)
            await self.message_sender.发送配置响应(request_id, False, None, str(e))

    async def 处理SDK模式设置(self, data: dict[str, Any]) -> None:
        """处理 SDK 模式设置消息。"""
        request_id = data.get("requestId", "")
        sdk_mode = data.get("sdkMode")
        logger.info(f"收到SDK模式设置请求: {request_id}, SDK模式: {sdk_mode}")

        if sdk_mode is None:
            await self.message_sender.发送SDK模式响应(request_id, False, None, "sdkMode 参数不能为空")
            return

        success, 当前模式, error = await self.sdk_mode_manager.切换(bool(sdk_mode))
        if success:
            logger.info(f"SDK模式切换成功: {request_id}, 当前模式: {'SDK' if 当前模式 else '遥控'}")
            await self.message_sender.发送SDK模式响应(request_id, True, 当前模式)
            return

        logger.error(f"处理SDK模式设置请求失败: {request_id}, error={error}")
        await self.message_sender.发送SDK模式响应(request_id, False, None, error or "SDK 模式切换失败")

    async def 处理SDK模式获取(self, data: dict[str, Any]) -> None:
        """处理 SDK 模式获取消息。"""
        request_id = data.get("requestId", "")
        logger.info(f"收到SDK模式获取请求: {request_id}")
        try:
            await self.message_sender.发送SDK模式响应(request_id, True, self.sdk_mode_manager.当前是否启用())
            logger.info(f"SDK模式获取成功: {request_id}")
        except Exception as e:
            logger.error(f"处理SDK模式获取请求时出错: {e}", exc_info=True)
            await self.message_sender.发送SDK模式响应(request_id, False, None, str(e))

    async def 处理日志标记(self, data: dict[str, Any]) -> None:
        """处理日志标记消息。"""
        request_id = data.get("requestId", "")
        message = data.get("message", "")
        logger.info(f"收到日志标记请求: {request_id}, 标记信息: {message}")
        try:
            result = await self.robot_server_client.调用API("POST", "/api/v1/logs/mark", {"message": message})
            if result.get("success"):
                await self.message_sender.发送日志标记响应(request_id, True, result.get("marker"))
                logger.info(f"日志标记写入成功: {request_id}")
            else:
                await self.message_sender.发送日志标记响应(request_id, False, None, result.get("error", "写入标记失败"))
                logger.error(f"日志标记写入失败: {request_id}")
        except Exception as e:
            logger.error(f"处理日志标记请求时出错: {e}", exc_info=True)
            await self.message_sender.发送日志标记响应(request_id, False, None, str(e))

    async def 处理安装包下载(self, data: dict[str, Any]) -> None:
        """处理安装包下载消息。"""
        request_id = data.get("requestId", "")
        download_paths: dict[str, str] = data.get("downloadPaths", {})
        hashes: dict[str, str] = data.get("hashes", {})
        package_filenames = {
            "full": "robot-full.tar.gz",
        }

        logger.info(f"收到安装包下载请求: {request_id}, 包含: {list(download_paths.keys())}")

        server_cfg = self._当前配置().get("server", {})
        server_url = str(server_cfg.get("server_url", ""))
        if server_url.startswith("wss://"):
            http_base = "https://" + server_url[6:]
        elif server_url.startswith("ws://"):
            http_base = "http://" + server_url[5:]
        else:
            http_base = re.sub(r"^ws://", "http://", server_url)

        parsed = urlparse(http_base)
        http_base = f"{parsed.scheme}://{parsed.netloc}"

        packages_dir = self.workspace / "packages"
        packages_dir.mkdir(parents=True, exist_ok=True)

        downloaded: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                for pkg_type, rel_path in download_paths.items():
                    if pkg_type not in package_filenames:
                        logger.warning(f"未知包类型: {pkg_type}，跳过")
                        continue

                    download_url = http_base + rel_path
                    target_path = packages_dir / package_filenames[pkg_type]
                    expected_hash = hashes.get(pkg_type, "")

                    logger.info(f"开始下载 {pkg_type}: {download_url}")
                    try:
                        async with client.stream("GET", download_url) as response:
                            response.raise_for_status()
                            sha256 = hashlib.sha256()
                            with open(target_path, "wb") as f:
                                async for chunk in response.aiter_bytes(chunk_size=65536):
                                    f.write(chunk)
                                    sha256.update(chunk)

                        if expected_hash:
                            actual_hash = sha256.hexdigest()
                            if actual_hash.lower() != expected_hash.lower():
                                raise ValueError(f"{pkg_type} 哈希校验失败: 期望 {expected_hash}，实际 {actual_hash}")

                        if pkg_type == "full":
                            extracted = _解出整包内子包(target_path, packages_dir)
                            logger.info(f"full 整包已解出子包: {extracted}")

                        downloaded.append(pkg_type)
                        logger.info(f"{pkg_type} 下载完成: {target_path}")
                    except Exception as e:
                        logger.error(f"下载 {pkg_type} 失败: {e}")
                        raise RuntimeError(f"下载 {pkg_type} 失败: {e}") from e

            await self.message_sender.发送安装包下载响应(request_id, True, downloaded)
            logger.info(f"安装包下载全部完成: {downloaded}")
        except Exception as e:
            logger.error(f"处理安装包下载请求时出错: {e}", exc_info=True)
            await self.message_sender.发送安装包下载响应(request_id, False, downloaded or None, str(e))

    async def 处理文本响应(self, data: dict[str, Any]) -> None:
        """处理文本响应消息。"""
        await 处理文本响应(data, self._提交动作, self._获取动作执行器())

    async def 处理音频控制(self, data: dict[str, Any]) -> None:
        """处理音频控制消息。"""
        if "enabled" in data:
            enabled = bool(data.get("enabled", True))
            self.audio_capture.audio_streaming_enabled = enabled
            logger.info(f"麦克风采集{'开启' if enabled else '关闭'}")

    async def 处理音频响应并播放(self, data: dict[str, Any]) -> None:
        """处理音频响应消息。"""
        处理音频响应并播放(data)

    async def 处理停止音频播放(self, data: dict[str, Any]) -> None:
        """处理停止音频播放消息。"""
        停止当前音频播放()

    async def 处理动作指令(self, data: dict[str, Any]) -> None:
        """处理动作指令消息。"""
        await 处理动作指令(data, self._提交动作, self._获取动作执行器())

    async def 处理控制指令(self, data: dict[str, Any]) -> None:
        """处理控制指令消息。"""
        command = data.get("command", "")
        if command == "action":
            action = data.get("action", "")
            if action:
                self._提交动作(action, data.get("parameters", {}))
            return
        self.joystick_controller.处理命令(data)

    async def 处理服务器错误(self, data: dict[str, Any]) -> None:
        """处理服务器错误消息。"""
        code = data.get("code", "")
        message = data.get("message", "")
        logger.error(f"服务器错误: {code} - {message}")

    async def 处理云端视频推流控制(self, data: dict[str, Any]) -> None:
        """处理云端下发的视频推流租约。"""
        enabled = bool(data.get("enabled", True))
        lease_ttl_ms = data.get("leaseTtlMs", 0)

        try:
            lease_ttl_ms = int(lease_ttl_ms)
        except (TypeError, ValueError):
            lease_ttl_ms = 0

        if not enabled:
            self._设置云端媒体租约到期时间(0.0)
            logger.info("云端视频推流租约已释放")
            return

        if lease_ttl_ms <= 0:
            lease_ttl_ms = 30_000

        self._设置云端媒体租约到期时间(time.monotonic() + (lease_ttl_ms / 1000))
        logger.info(f"云端视频推流租约已续期: {lease_ttl_ms}ms")

    async def 处理音频流开始(self, data: dict[str, Any]) -> None:
        """处理音频流开始消息。"""
        logger.debug("音频流开始")

    async def 处理音频流数据块(self, data: dict[str, Any]) -> None:
        """处理音频流数据块消息。"""
        return None

    async def 处理音频流结束(self, data: dict[str, Any]) -> None:
        """处理音频流结束消息。"""
        logger.debug("音频流结束")

    async def 处理收到的消息(self, message: dict[str, Any]) -> None:
        """根据消息类型分发到对应处理器。"""
        msg_type = message.get("type")
        if not isinstance(msg_type, str):
            logger.warning(f"未知的消息类型: {msg_type}")
            return
        data = message.get("data", {})
        if not isinstance(data, dict):
            data = {}
        handler = self.message_handlers.get(msg_type)
        if handler:
            await handler(data)
        else:
            logger.warning(f"未知的消息类型: {msg_type}")
