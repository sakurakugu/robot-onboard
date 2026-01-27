#!/usr/bin/env python3
"""
机器狗客户端
功能：
- 配置管理（~/sparkrobot/config/robot-chat.toml）
- WebSocket 通信
- 心跳保持
- 接收音频回复（opus）
- 执行动作指令
- 日志记录
"""

import asyncio
import base64
import json
import logging
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse, urlunparse

import websockets
from core.utils import generate_uuid
from core.logger import CNLevelFormatter
from core.utils import get_ipc_path
from websockets import ClientConnection

from core.config import Config

_AUDIO_IMPORT_ERROR: Optional[Exception] = None
try:
    import numpy as np
    import opuslib
    import sounddevice as sd
except Exception as e:
    np = None
    sd = None
    opuslib = None
    _AUDIO_IMPORT_ERROR = e

class RobotClient:
    """机器狗客户端"""

    def __init__(self, workspace: Optional[Path] = None):
        """初始化客户端

        Args:
            workspace: 工作目录，默认为 ~/sparkrobot
        """
        # 配置目录
        if workspace is None:
            workspace = Path.home() / "sparkrobot"
        self.base_dir = workspace
        self.config_dir = self.base_dir / "config"
        self.project_name = "robot-chat"
        self.log_dir = self.base_dir / "logs" / self.project_name

        # 配置文件
        self.global_config_file = self.config_dir / "config.toml"  # 全局配置（uuid等）
        self.config_file = self.config_dir / f"{self.project_name}.toml"  # 机器人对话专用配置

        # 确保目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.config_store = Config.instance(workspace, self.project_name)
        self.config = self.config_store.get()

        # 设置日志
        self._setup_logger()

        # WebSocket 连接（多通道）
        self.ws_business: Optional[ClientConnection] = None
        self.ws_control: Optional[ClientConnection] = None
        self.ws_audio_upload: Optional[ClientConnection] = None
        self.ws_audio_download: Optional[ClientConnection] = None
        self.connected = False
        self.connected_control = False
        self.connected_audio_upload = False
        self.connected_audio_download = False
        self.reconnect_interval = 5  # 秒
        self.heartbeat_interval = 30  # 秒

        # 音频流任务
        self.audio_task: Optional[asyncio.Task] = None
        self.audio_streaming_enabled = bool(self.config.get("audio", {}).get("enable_streaming", True))

        # 后台执行器（用于运行同步的动作操作）
        self._executor = ThreadPoolExecutor(max_workers=1)

        # 子进程控制器（启动 core.py）
        self.interactive_process: Optional[subprocess.Popen] = None

        # IPC（Unix Socket）
        self._ipc_server: Optional[asyncio.AbstractServer] = None

        # 消息处理器
        self.message_handlers: Dict[str, Callable] = {
            "text_response": self._handle_text_response,
            "audio_response": self._handle_audio_response,
            "action_command": self._handle_action_command,
            "control_command": self._handle_control_command,
            "audio_control": self._handle_audio_control,
            "error": self._handle_error,
        }

        # 动作执行器（需要用户自定义）
        self.action_executor: Optional[Callable] = None

        version = self._detect_robot_version()
        if version:
            self.config.setdefault("robot", {})
            self.config["robot"]["version"] = version
            self.config_store.save(self.config)

    def _detect_robot_version(self) -> Optional[str]:
        try:
            result = subprocess.run(
                "grep -oP 'motion-control_\\K[^_]+' /etc/release/*[^rootfs]*.yaml",
                shell=True,
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            out = result.stdout.strip()
            if not out:
                return None
            for line in out.splitlines():
                ver = line.rsplit(":", 1)[-1].strip()
                if ver:
                    return ver
            return None
        except Exception:
            return None


    def _ensure_scheme(self, url: str) -> str:
        if re.match(r"^wss?://", url):
            return url
        return f"ws://{url}"

    def _replace_port_and_path(self, url: str, port: int, path: str) -> str:
        base = self._ensure_scheme(url)
        parsed = urlparse(base)
        host = parsed.hostname or ""
        scheme = parsed.scheme or "ws"
        netloc = f"{host}:{port}"
        return urlunparse((scheme, netloc, path, "", "", ""))

    def _resolve_server_urls(self) -> Dict[str, str]:
        server_cfg = self.config.get("server", {})
        ws_path = server_cfg.get("ws_path") or "/api/v1/conversation/connect"
        business_url = server_cfg.get("business_url") or server_cfg.get("url")
        control_url = server_cfg.get("control_url")
        audio_upload_url = server_cfg.get("audio_upload_url")
        audio_download_url = server_cfg.get("audio_download_url")
        base_url = server_cfg.get("base_url")

        if base_url:
            if not control_url:
                control_url = self._replace_port_and_path(base_url, 9000, ws_path)
            if not business_url:
                business_url = self._replace_port_and_path(base_url, 9001, ws_path)
            if not audio_upload_url:
                audio_upload_url = self._replace_port_and_path(base_url, 9002, ws_path)
            if not audio_download_url:
                audio_download_url = self._replace_port_and_path(base_url, 9003, ws_path)

        if business_url and not control_url:
            control_url = self._replace_port_and_path(business_url, 9000, ws_path)
        if business_url and not audio_upload_url:
            audio_upload_url = self._replace_port_and_path(business_url, 9002, ws_path)
        if business_url and not audio_download_url:
            audio_download_url = self._replace_port_and_path(business_url, 9003, ws_path)

        return {
            "business": business_url or "",
            "control": control_url or "",
            "audio_upload": audio_upload_url or "",
            "audio_download": audio_download_url or "",
        }

    def _append_robot_params(self, url: str, robot_uuid: str) -> str:
        base = self._ensure_scheme(url)
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}robotId={robot_uuid}&role=robot"

    def _setup_logger(self) -> None:
        level = self.config["logging"].get("level", "INFO")
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        formatter = CNLevelFormatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        file_handler = logging.FileHandler(
            self.log_dir / f"robot_client_{time.strftime('%Y%m%d')}.log", encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_formatter = CNLevelFormatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%H:%M:%S.%f"
        )
        console_handler.setFormatter(console_formatter)
        logger = logging.getLogger("RobotClient")
        logger.setLevel(level)
        logger.handlers = []
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        self.logger = logger

    async def _start_ipc_server(self) -> None:
        """启动Unix Socket服务，接收core状态并转发到服务器"""
        # 清理遗留socket文件
        ipc_path = get_ipc_path(self.project_name)

        async def _handle_ipc(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
            # self.logger.info("IPC连接")
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
                        await self.send_status(message)
            except Exception as e:
                self.logger.warning(f"IPC连接异常: {e}")
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        self._ipc_server = await asyncio.start_unix_server(_handle_ipc, path=str(ipc_path))
        self.logger.info(f"IPC服务启动: {ipc_path}")

    async def _stop_ipc_server(self) -> None:
        """停止Unix Socket服务"""
        if self._ipc_server:
            self._ipc_server.close()
            await self._ipc_server.wait_closed()
            self._ipc_server = None
        try:
            ipc_path = get_ipc_path(self.project_name)
            if ipc_path.exists():
                ipc_path.unlink()
        except Exception:
            pass

    async def connect(self) -> bool:
        """连接到服务器"""
        try:
            robot_uuid = self.config["robot"]["uuid"]
            urls = self._resolve_server_urls()

            business_url = urls.get("business")
            if not business_url:
                raise ValueError("未配置业务通道地址（server.business_url 或 server.url）")

            business_full = self._append_robot_params(business_url, robot_uuid)
            self.logger.info(f"正在连接业务通道: {business_full}")
            self.ws_business = await websockets.connect(business_full)
            self.connected = True

            control_url = urls.get("control")
            if control_url:
                control_full = self._append_robot_params(control_url, robot_uuid)
                try:
                    self.logger.info(f"正在连接控制通道: {control_full}")
                    self.ws_control = await websockets.connect(control_full)
                    self.connected_control = True
                except Exception as e:
                    self.logger.warning(f"控制通道连接失败: {e}")

            audio_upload_url = urls.get("audio_upload")
            if audio_upload_url:
                audio_upload_full = self._append_robot_params(audio_upload_url, robot_uuid)
                try:
                    self.logger.info(f"正在连接音频上传通道: {audio_upload_full}")
                    self.ws_audio_upload = await websockets.connect(audio_upload_full)
                    self.connected_audio_upload = True
                except Exception as e:
                    self.logger.warning(f"音频上传通道连接失败: {e}")

            audio_download_url = urls.get("audio_download")
            if audio_download_url:
                audio_download_full = self._append_robot_params(audio_download_url, robot_uuid)
                try:
                    self.logger.info(f"正在连接音频下载通道: {audio_download_full}")
                    self.ws_audio_download = await websockets.connect(audio_download_full)
                    self.connected_audio_download = True
                except Exception as e:
                    self.logger.warning(f"音频下载通道连接失败: {e}")

            self.logger.info(f"已连接到服务器，机器狗UUID: {robot_uuid}")

            # 发送注册消息（业务通道）
            await self.send_register()

            return True

        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            self.connected = False
            return False

    async def disconnect(self) -> None:
        """断开连接"""
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

        # 关闭子进程
        if self.interactive_process and self.interactive_process.poll() is None:
            self.logger.info("正在关闭交互式子进程...")
            try:
                # 发送退出命令 (0)
                self.interactive_process.stdin.write("0\n")
                self.interactive_process.stdin.flush()
                self.interactive_process.wait(timeout=5)
            except Exception as e:
                self.logger.warning(f"子进程未正常退出，强制终止: {e}")
                self.interactive_process.terminate()
                self.interactive_process.wait(timeout=3)
            self.interactive_process = None

        # 关闭线程池
        self._executor.shutdown(wait=False)

    async def send_message(self, message: Dict[str, Any], channel: str = "business") -> None:
        """发送消息到服务器"""
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

    async def send_text(self, text: str) -> None:
        """发送文本消息"""
        message = {
            "type": "text_input",
            "robotId": self.config["robot"]["uuid"],
            "timestamp": int(time.time() * 1000),
            "data": {"text": text},
        }
        await self.send_message(message, channel="business")

    async def send_audio_start(self, session_id: str, frame_duration_ms: int) -> None:
        message = {
            "type": "audio_start",
            "robotId": self.config["robot"]["uuid"],
            "timestamp": int(time.time() * 1000),
            "data": {
                "format": "opus",
                "sampleRate": self.config["audio"].get("sample_rate", 16000),
                "channels": self.config["audio"].get("channels", 1),
                "frameDurationMs": frame_duration_ms,
                "sessionId": session_id,
            },
        }
        await self.send_message(message, channel="audio_upload")

    async def send_audio_chunk(self, session_id: str, seq: int, audio_bytes: bytes, frame_duration_ms: int) -> None:
        message = {
            "type": "audio_chunk",
            "robotId": self.config["robot"]["uuid"],
            "timestamp": int(time.time() * 1000),
            "data": {
                "format": "opus",
                "sampleRate": self.config["audio"].get("sample_rate", 16000),
                "channels": self.config["audio"].get("channels", 1),
                "frameDurationMs": frame_duration_ms,
                "sessionId": session_id,
                "seq": seq,
                "buffer": base64.b64encode(audio_bytes).decode("ascii"),
            },
        }
        await self.send_message(message, channel="audio_upload")

    async def send_audio_end(self, session_id: str, reason: str) -> None:
        message = {
            "type": "audio_end",
            "robotId": self.config["robot"]["uuid"],
            "timestamp": int(time.time() * 1000),
            "data": {
                "sessionId": session_id,
                "reason": reason,
            },
        }
        await self.send_message(message, channel="audio_upload")

    async def send_register(self) -> None:
        """发送注册消息"""
        message = {
            "type": "client_register",
            "robotId": self.config["robot"]["uuid"],
            "timestamp": int(time.time() * 1000),
            "data": {
                "name": self.config["robot"].get("name"),
                "model": self.config["robot"].get("model"),
                "version": self.config["robot"].get("version", "0.0.0"),
                "metadata": {},
            },
        }
        await self.send_message(message, channel="business")

    async def send_heartbeat(self) -> None:
        """发送心跳包"""
        message = {
            "type": "heartbeat",
            "robotId": self.config["robot"]["uuid"],
            "timestamp": int(time.time() * 1000),
            "data": {},
        }
        if self.connected_control:
            await self.send_message(message, channel="control")
        else:
            await self.send_message(message, channel="business")

    async def send_status(self, status_msg: Dict[str, Any]) -> None:
        """发送状态信息（统一格式）"""
        message = {
            "type": "status",
            "robot_id": self.config["robot"]["uuid"],
            "seq": status_msg.get("seq"),
            "timestamp": int(time.time() * 1000),
            "data": status_msg.get("data", {}),
        }
        await self.send_message(message, channel="control")

    def _parse_action_format(self, text: str) -> Optional[Dict[str, Any]]:
        """解析动作格式 {{action=xxx}} 或 {{action=xxx,param=value}}

        Args:
            text: 要解析的文本

        Returns:
            包含 action 和 parameters 的字典，如果不匹配则返回 None
        """
        # 正则匹配 {{action=动作名称,参数...}}
        pattern = r"^\{\{action=([a-zA-Z_][a-zA-Z0-9_]*)((?:,[a-zA-Z_][a-zA-Z0-9_]*=[^,}]+)*)\}\}$"
        match = re.match(pattern, text)

        if not match:
            return None

        action = match.group(1)
        params_str = match.group(2)
        parameters = {}

        # 解析参数
        if params_str:
            param_pairs = params_str[1:].split(",")  # 去掉开头的逗号
            for pair in param_pairs:
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    # 尝试转换为数字
                    try:
                        if "." in value:
                            parameters[key] = float(value)
                        else:
                            parameters[key] = int(value)
                    except ValueError:
                        parameters[key] = value

        return {"action": action, "parameters": parameters}

    async def _handle_text_response(self, data: Dict[str, Any]) -> None:
        """处理文本响应"""
        text = data.get("text", "")
        self.logger.info(f"收到文本响应: {text}")

        # 检测是否是动作格式
        action_data = self._parse_action_format(text)
        if action_data:
            action = action_data["action"]
            parameters = action_data["parameters"]
            self.logger.info(f"检测到动作格式: action={action}, parameters={parameters}")

            # 执行动作（在后台线程中运行）
            if self.action_executor:
                try:
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(self._executor, self.action_executor, action, parameters)
                    if result:
                        self.logger.info(f"动作 {action} 执行成功")
                    else:
                        self.logger.warning(f"动作 {action} 执行失败或不支持")
                except Exception as e:
                    self.logger.error(f"执行动作 {action} 时出错: {e}")
            else:
                self.logger.warning("未设置动作执行器，无法执行动作")

            # 是动作格式，不处理音频，直接返回
            return

    async def _audio_capture_loop(self) -> None:
        """采集麦克风音频并通过Opus上传"""
        audio_cfg = self.config.get("audio", {})

        if np is None or sd is None or opuslib is None:
            detail = f" (导入错误: {_AUDIO_IMPORT_ERROR})" if _AUDIO_IMPORT_ERROR else ""
            self.logger.warning(f"缺少音频依赖，请安装: numpy sounddevice opuslib{detail}")
            return

        sample_rate = int(audio_cfg.get("sample_rate", 16000))
        channels = int(audio_cfg.get("channels", 1))
        frame_duration_ms = int(audio_cfg.get("frame_duration_ms", 20))
        frame_size = int(sample_rate * frame_duration_ms / 1000)
        vad_threshold = float(audio_cfg.get("vad_threshold", 0.015))
        vad_silence_ms = int(audio_cfg.get("vad_silence_ms", 800))
        max_segment_ms = int(audio_cfg.get("max_segment_ms", 10000))
        silence_frames_limit = max(1, int(vad_silence_ms / frame_duration_ms))
        max_frames = max(1, int(max_segment_ms / frame_duration_ms))
        input_device = audio_cfg.get("input_device")

        encoder = opuslib.Encoder(sample_rate, channels, opuslib.APPLICATION_VOIP)

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        def callback(indata, frames, time_info, status):
            if status:
                self.logger.debug(f"音频采集状态: {status}")
            data = indata.copy()
            try:
                loop.call_soon_threadsafe(queue.put_nowait, data)
            except Exception:
                # 队列满时丢弃，避免报错刷屏
                pass

        stream = None
        session_id: Optional[str] = None
        seq = 0
        silence_frames = 0
        frames_in_segment = 0

        try:
            while self.connected:
                if not self.audio_streaming_enabled:
                    if session_id is not None:
                        await self.send_audio_end(session_id, "manual")
                        session_id = None
                        seq = 0
                        silence_frames = 0
                        frames_in_segment = 0
                    if stream:
                        try:
                            stream.stop()
                            stream.close()
                        except Exception:
                            pass
                        stream = None
                    await asyncio.sleep(0.5)
                    continue

                if not self.connected_audio_upload:
                    if stream:
                        try:
                            stream.stop()
                            stream.close()
                        except Exception:
                            pass
                        stream = None
                    await asyncio.sleep(0.5)
                    continue

                if stream is None:
                    stream = sd.InputStream(
                        samplerate=sample_rate,
                        channels=channels,
                        dtype="int16",
                        blocksize=frame_size,
                        callback=callback,
                        device=input_device if input_device else None,
                    )
                    stream.start()
                    self.logger.info("麦克风采集已启动")

                try:
                    pcm_block = await queue.get()
                except asyncio.CancelledError:
                    break

                pcm = np.reshape(pcm_block, (-1,))
                rms = float(np.sqrt(np.mean(pcm.astype(np.float32) ** 2))) / 32768.0
                is_voice = rms >= vad_threshold

                if is_voice:
                    if session_id is None:
                        session_id = generate_uuid()
                        seq = 0
                        silence_frames = 0
                        frames_in_segment = 0
                        await self.send_audio_start(session_id, frame_duration_ms)
                        self.logger.debug(f"音频会话开始: {session_id}")

                    opus_bytes = encoder.encode(pcm.tobytes(), frame_size)
                    await self.send_audio_chunk(session_id, seq, opus_bytes, frame_duration_ms)
                    seq += 1
                    frames_in_segment += 1
                    silence_frames = 0

                    if frames_in_segment >= max_frames:
                        await self.send_audio_end(session_id, "max_length")
                        self.logger.debug(f"音频会话结束(长度): {session_id}")
                        session_id = None
                else:
                    if session_id is not None:
                        silence_frames += 1
                        if silence_frames >= silence_frames_limit:
                            await self.send_audio_end(session_id, "silence")
                            self.logger.debug(f"音频会话结束(静音): {session_id}")
                            session_id = None
                            seq = 0
                            silence_frames = 0
                            frames_in_segment = 0

        finally:
            if session_id is not None:
                await self.send_audio_end(session_id, "manual")
            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            self.logger.info("麦克风采集已停止")

    async def _handle_audio_control(self, data: Dict[str, Any]) -> None:
        """处理麦克风开关控制"""
        enabled = bool(data.get("enabled", True))
        self.audio_streaming_enabled = enabled
        self.logger.info(f"麦克风采集{'开启' if enabled else '关闭'}")

    async def _handle_audio_response(self, data: Dict[str, Any]) -> None:
        """处理音频响应"""
        audio_format = data.get("format", "webm")
        audio_buffer = data.get("buffer", "")
        duration = data.get("duration", 0)

        self.logger.info(f"收到音频响应: format={audio_format}, duration={duration}s")

        try:
            if audio_format not in ("webm", "mp3", "opus"):
                self.logger.error(f"不支持的音频格式: {audio_format}")
                return
            audio_data = base64.b64decode(audio_buffer)

            ts = int(time.time())
            if audio_format == "webm":
                audio_file = self.log_dir / f"audio_{ts}.webm"
            elif audio_format == "mp3":
                audio_file = self.log_dir / f"audio_{ts}.mp3"
            else:
                audio_file = self.log_dir / f"audio_{ts}.opus"
            with open(audio_file, "wb") as f:
                f.write(audio_data)
            self.logger.info(f"音频已保存: {audio_file}")

            try:
                subprocess.Popen(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_file)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self.logger.info("音频播放已启动（音箱）")
            except Exception as e:
                self.logger.debug(f"音频播放启动失败: {e}")

        except Exception as e:
            self.logger.error(f"处理音频失败: {e}")

    async def _handle_action_command(self, data: Dict[str, Any]) -> None:
        """处理动作指令"""
        action = data.get("action", "")
        parameters = data.get("parameters", {})
        safety_checked = data.get("safetyChecked", False)

        self.logger.info(f"收到动作指令: action={action}, parameters={parameters}")

        # 执行动作（在后台线程中运行，避免阻塞事件循环）
        if self.action_executor:
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(self._executor, self.action_executor, action, parameters)
                self.logger.info(f"动作执行结果: {result}")
            except Exception as e:
                self.logger.error(f"执行动作失败: {e}")
        else:
            self.logger.warning("未设置动作执行器，跳过动作执行")

    async def _handle_control_command(self, data: Dict[str, Any]) -> None:
        """处理控制指令（摇杆/急停）"""
        command = data.get("command")
        mode = data.get("mode", "move")
        channel = data.get("channel")
        x = float(data.get("x", 0) or 0)
        y = float(data.get("y", 0) or 0)
        speed = float(data.get("speed", 5) or 5)

        self.logger.debug(
            f"收到控制指令: command={command}, mode={mode}, channel={channel}, x={x}, y={y}, speed={speed}"
        )

        if not command:
            return

        if command == "estop":
            self.send_command_to_process(json.dumps({"type": "estop"}))
            return

        # 归一化速度倍率（1-10）
        speed_ratio = max(0.0, min(1.0, speed / 10.0))

        if command == "joystick":
            if mode == "pose" or channel == "pose":
                max_roll = 0.5
                max_pitch = 0.5
                roll_rate = y * max_roll * speed_ratio
                pitch_rate = -x * max_pitch * speed_ratio
                payload = {
                    "type": "attitude",
                    "roll_rate": roll_rate,
                    "pitch_rate": pitch_rate,
                    "yaw_rate": 0.0,
                    "height_vel": 0.0,
                }
                self.send_command_to_process(json.dumps(payload))
                return

            # move 模式
            max_vx = 0.6
            max_vy = 0.4
            max_yaw = 0.6

            if channel == "look":
                payload = {
                    "type": "move",
                    "vx": 0.0,
                    "vy": 0.0,
                    "yaw_rate": y * max_yaw * speed_ratio,
                }
                self.send_command_to_process(json.dumps(payload))
                return

            payload = {
                "type": "move",
                "vx": x * max_vx * speed_ratio,
                "vy": y * max_vy * speed_ratio,
                "yaw_rate": 0.0,
            }
            self.send_command_to_process(json.dumps(payload))
            return

        if command == "joystick_stop":
            if mode == "pose" or channel == "pose":
                self.send_command_to_process(
                    json.dumps(
                        {"type": "attitude", "roll_rate": 0.0, "pitch_rate": 0.0, "yaw_rate": 0.0, "height_vel": 0.0}
                    )
                )
                return

            self.send_command_to_process(json.dumps({"type": "move", "vx": 0.0, "vy": 0.0, "yaw_rate": 0.0}))
            return

    async def _handle_error(self, data: Dict[str, Any]) -> None:
        """处理错误消息"""
        code = data.get("code", "")
        message = data.get("message", "")
        self.logger.error(f"服务器错误: {code} - {message}")

    async def _receive_loop(self, channel: str, ws: ClientConnection) -> None:
        """接收消息循环"""
        while self.connected:
            try:
                message_str = await ws.recv()
                message = json.loads(message_str)

                msg_type = message.get("type")
                data = message.get("data", {})

                # 调用相应的处理器
                handler = self.message_handlers.get(msg_type)
                if handler:
                    await handler(data)
                else:
                    self.logger.warning(f"未知的消息类型: {msg_type}")

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

    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        interval = self.config["server"].get("heartbeat_interval", 30)
        while self.connected:
            await asyncio.sleep(interval)
            if self.connected:
                await self.send_heartbeat()

    async def run(self) -> None:
        """运行客户端（自动重连）"""
        self.logger.info("机器狗客户端启动")

        # 启动IPC服务
        await self._start_ipc_server()

        while True:
            try:
                # 尝试连接
                if not self.connected:
                    success = await self.connect()
                    if not success:
                        reconnect_interval = self.config["server"].get("reconnect_interval", 5)
                        self.logger.info(f"{reconnect_interval} 秒后重试连接...")
                        await asyncio.sleep(reconnect_interval)
                        continue

                # 启动接收和心跳循环
                tasks = []
                if self.ws_business and self.connected:
                    tasks.append(asyncio.create_task(self._receive_loop("business", self.ws_business)))
                if self.ws_control and self.connected_control:
                    tasks.append(asyncio.create_task(self._receive_loop("control", self.ws_control)))
                if self.ws_audio_download and self.connected_audio_download:
                    tasks.append(asyncio.create_task(self._receive_loop("audio_download", self.ws_audio_download)))

                if not self.audio_task or self.audio_task.done():
                    self.audio_task = asyncio.create_task(self._audio_capture_loop())
                tasks.append(self.audio_task)

                heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                tasks.append(heartbeat_task)

                # 等待任务完成
                await asyncio.gather(*tasks)

            except KeyboardInterrupt:
                self.logger.info("收到中断信号，正在退出...")
                break
            except Exception as e:
                self.logger.error(f"运行时错误: {e}")
                self.connected = False

            finally:
                if self.ws_business or self.ws_control or self.ws_audio_download or self.ws_audio_upload:
                    await self.disconnect()

        # 退出前停止IPC
        await self._stop_ipc_server()

    def set_action_executor(self, executor: Callable) -> None:
        """设置动作执行器

        Args:
            executor: 异步函数，签名为 async def executor(action: str, parameters: dict) -> bool
        """
        self.action_executor = executor

    def start_interactive_process(self, script_path: str) -> bool:
        """启动交互式子进程

        Args:
            script_path: modules/control/__main__.py 的路径

        Returns:
            启动成功返回 True
        """
        try:
            self.logger.info(f"正在启动交互式子进程: {script_path}")
            self.interactive_process = subprocess.Popen(
                ["python3", script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            # 等待子进程初始化
            time.sleep(5)

            if self.interactive_process.poll() is not None:
                self.logger.error("子进程启动失败")
                return False

            self.logger.info("交互式子进程启动成功")
            return True

        except Exception as e:
            self.logger.error(f"启动交互式子进程失败: {e}")
            return False

    def send_command_to_process(self, command: str) -> bool:
        """向子进程发送命令

        Args:
            command: 要发送的命令（数字）

        Returns:
            发送成功返回 True
        """
        if not self.interactive_process or self.interactive_process.poll() is not None:
            self.logger.error("子进程未运行")
            return False

        try:
            self.interactive_process.stdin.write(f"{command}\n")
            self.interactive_process.stdin.flush()
            return True
        except Exception as e:
            self.logger.error(f"发送命令失败: {e}")
            return False


async def main():
    """主函数"""
    client = RobotClient()

    # 获取 core.py 的路径
    script_dir = Path(__file__).parent
    interactive_script = script_dir / "modules" / "control" / "__main__.py"

    if not interactive_script.exists():
        client.logger.error(f"找不到交互式脚本: {interactive_script}")
        return

    # 启动交互式子进程
    if not client.start_interactive_process(str(interactive_script)):
        client.logger.error("无法启动交互式子进程")
        return

    # 动作到命令的映射
    action_map = {
        "stand_up": "1",  # 站立
        "sit_down": "2",  # 趴下
        "walk_forward": "3",  # 前进
        "walk_backward": "4",  # 后退
        "turn_left": "7",  # 左转
        "turn_right": "8",  # 右转
        "dance": "9",  # 跳跃（用于舞蹈）
        "jump": "9",  # 向上跳
        "front_jump": "10",  # 向前跳
        "backflip": "11",  # 后空翻
        "shake_hand": "12",  # 握手
        "nod": "13",  # 姿态控制（用于点头）
        "wave": "13",  # 姿态控制（用于挥手）
        "two_leg_stand": "14",  # 双腿站立
    }

    def action_executor(action: str, parameters: dict) -> bool:
        """同步动作执行函数（在线程池中运行）"""
        try:
            client.logger.debug(f"开始执行动作: {action}")

            # 映射动作到命令数字
            command = action_map.get(action)
            if not command:
                client.logger.warning(f"不支持的动作: {action}")
                return False

            # 发送命令到子进程
            success = client.send_command_to_process(command)
            if not success:
                client.logger.error(f"发送命令 {command} 失败")
                return False

            # 等待动作完成（根据动作类型设置不同的等待时间）
            if action in ["walk_forward", "walk_backward", "turn_left", "turn_right"]:
                wait_time = 2.5  # 移动类动作
            elif action in ["shake_hand", "nod", "wave"]:
                wait_time = 4.5  # 姿态动作
            elif action == "dance":
                wait_time = 5  # 跳跃动作
            else:
                wait_time = 3.5  # 其他动作

            time.sleep(wait_time)
            client.logger.debug(f"动作 {action} 执行完成")
            return True

        except Exception as e:
            client.logger.error(f"执行动作 {action} 时出错: {e}", exc_info=True)
            return False

    client.set_action_executor(action_executor)

    # 运行客户端
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\n客户端已停止")


if __name__ == "__main__":
    asyncio.run(main())
