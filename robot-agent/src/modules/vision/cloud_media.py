"""云端正式视频推流模块

使用 ffmpeg 将机器狗本地 RTSP 拉流后，推送到云端 MediaMTX。
是否维持这条链路由上层传入的允许函数决定：
- 常驻模式下，机器人连上云端后会持续推流
- 按需模式下，仅在存在有效观看租约时才推流
"""

import asyncio
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from typing import IO, Any, Callable, Optional
from urllib.parse import urlsplit, urlunsplit

from sparkrobot_common import DEFAULT_SERVER_ADDR, get_logger

MEDIA_PUBLISH_BASE_URL_AUTO = "follow_server"

logger = get_logger("robot-agent")


@dataclass(frozen=True)
class 推流配置:
    """推流配置快照"""

    ffmpeg_path: str
    source_rtsp_url: str
    publish_url: str
    rtsp_transport: str
    ffmpeg_loglevel: str

    @property
    def 启动命令(self) -> list[str]:
        return [
            self.ffmpeg_path,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            self.ffmpeg_loglevel,
            "-rtsp_transport",
            self.rtsp_transport,
            "-i",
            self.source_rtsp_url,
            "-map",
            "0:v:0",
            "-c:v",
            "copy",
            "-an",
            "-f",
            "rtsp",
            "-rtsp_transport",
            self.rtsp_transport,
            self.publish_url,
        ]

    @property
    def 签名(self) -> tuple[str, ...]:
        return tuple(self.启动命令)


class 云端媒体推流管理器:
    """维持 ffmpeg 到云端 MediaMTX 的正式视频推流。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._process: Optional[subprocess.Popen[bytes]] = None
        self._current_signature: Optional[tuple[str, ...]] = None
        self._stderr_file: Optional[IO[bytes]] = None

    def 更新配置(self, config: dict[str, Any]) -> None:
        """更新推流配置快照。"""
        self._config = config

    async def 服务循环(self, 允许推流: Callable[[], bool]) -> None:
        """持续维护推流进程。"""
        try:
            while True:
                config = self._解析推流配置()
                if config is None or not 允许推流():
                    await self.停止()
                    await asyncio.sleep(2)
                    continue

                if self._process is None:
                    self._启动进程(config)
                    await asyncio.sleep(2)
                    continue

                if self._current_signature != config.签名:
                    logger.info("云端媒体推流配置已变更，准备重启 ffmpeg")
                    await self.停止()
                    continue

                exit_code = self._process.poll()
                if exit_code is not None:
                    error_output = self._读取最近错误输出()
                    if error_output:
                        logger.warning(f"云端媒体推流进程已退出，退出码: {exit_code}，最近错误输出:\n{error_output}")
                    else:
                        logger.warning(f"云端媒体推流进程已退出，退出码: {exit_code}，5 秒后重试")
                    await self.停止()
                    await asyncio.sleep(5)
                    continue

                await asyncio.sleep(2)
        except asyncio.CancelledError:
            raise
        finally:
            await self.停止()

    async def 停止(self) -> None:
        """停止当前推流进程。"""
        process = self._process
        self._process = None
        self._current_signature = None

        if process is None:
            return

        if process.poll() is None:
            logger.info("正在停止云端媒体推流进程")
            process.terminate()
            try:
                await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=5)
            except asyncio.TimeoutError:
                logger.warning("云端媒体推流进程退出超时，准备强制终止")
                process.kill()
                await asyncio.wait_for(asyncio.to_thread(process.wait), timeout=5)

        self._关闭错误输出文件()

    def _启动进程(self, config: 推流配置) -> None:
        command = config.启动命令
        log_command = shlex.join(self._脱敏命令(command))
        stderr_file = tempfile.TemporaryFile()
        self._关闭错误输出文件()
        self._stderr_file = stderr_file

        try:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=stderr_file,
            )
            self._current_signature = config.签名
            logger.info(f"云端媒体推流已启动: {log_command}")
        except FileNotFoundError as exc:
            self._process = None
            self._current_signature = None
            self._关闭错误输出文件()
            logger.error(f"启动 ffmpeg 失败，未找到可执行文件: {config.ffmpeg_path}", exc_info=exc)
        except Exception as exc:
            self._process = None
            self._current_signature = None
            self._关闭错误输出文件()
            logger.error(f"启动云端媒体推流失败: {exc}", exc_info=True)

    def _解析推流配置(self) -> Optional[推流配置]:
        media_cfg = self._config.get("media", {})
        if not bool(media_cfg.get("enable_cloud_streaming", True)):
            return None

        robot_cfg = self._config.get("robot", {})
        robot_uuid = str(robot_cfg.get("uuid", "")).strip()
        if not robot_uuid:
            logger.warning("机器人 UUID 为空，暂不启动云端媒体推流")
            return None

        server_cfg = self._config.get("server", {})
        source_rtsp_url = str(media_cfg.get("source_rtsp_url", "rtsp://127.0.0.1:8554/test")).strip()
        publish_base_url = self._解析推流基地址(
            str(media_cfg.get("publish_base_url", "")).strip(),
            str(server_cfg.get("server_url", "")).strip(),
        )
        stream_path_prefix = str(media_cfg.get("stream_path_prefix", "robots")).strip().strip("/")
        publish_user = str(media_cfg.get("publish_user", "")).strip()
        publish_pass = str(media_cfg.get("publish_pass", "")).strip()
        ffmpeg_path = str(media_cfg.get("ffmpeg_path", "ffmpeg")).strip() or "ffmpeg"
        rtsp_transport = str(media_cfg.get("rtsp_transport", "tcp")).strip().lower() or "tcp"
        ffmpeg_loglevel = str(media_cfg.get("ffmpeg_loglevel", "warning")).strip().lower() or "warning"

        if not source_rtsp_url or not publish_base_url:
            logger.warning("云端媒体推流配置不完整，缺少 source_rtsp_url 或 publish_base_url")
            return None

        if rtsp_transport not in {"tcp", "udp"}:
            rtsp_transport = "tcp"

        publish_path = f"{stream_path_prefix}/{robot_uuid}" if stream_path_prefix else robot_uuid

        return 推流配置(
            ffmpeg_path=ffmpeg_path,
            source_rtsp_url=source_rtsp_url,
            publish_url=self._拼接发布地址(publish_base_url, publish_user, publish_pass, publish_path),
            rtsp_transport=rtsp_transport,
            ffmpeg_loglevel=ffmpeg_loglevel,
        )

    def _拼接发布地址(self, base_url: str, user: str, password: str, publish_path: str) -> str:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"rtsp", "rtsps"}:
            parsed = urlsplit(f"rtsp://{base_url}")

        hostname = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        auth = ""
        if user:
            auth = user
            if password:
                auth = f"{auth}:{password}"
            auth = f"{auth}@"

        netloc = f"{auth}{hostname}{port}"
        base_path = parsed.path.rstrip("/")
        full_path = f"{base_path}/{publish_path}" if base_path else f"/{publish_path}"
        return urlunsplit((parsed.scheme, netloc, full_path, "", ""))

    def _脱敏命令(self, command: list[str]) -> list[str]:
        sanitized = list(command)
        if sanitized:
            sanitized[-1] = self._脱敏地址(sanitized[-1])
        return sanitized

    def _脱敏地址(self, url: str) -> str:
        parsed = urlsplit(url)
        if not parsed.password:
            return url
        username = parsed.username or ""
        hostname = parsed.hostname or ""
        port = f":{parsed.port}" if parsed.port else ""
        netloc = f"{username}:***@{hostname}{port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))

    def _读取最近错误输出(self, max_bytes: int = 8192) -> str:
        stderr_file = self._stderr_file
        if stderr_file is None:
            return ""

        try:
            stderr_file.flush()
            stderr_file.seek(0, 2)
            file_size = stderr_file.tell()
            stderr_file.seek(max(0, file_size - max_bytes))
            raw = stderr_file.read()
        except Exception:
            return ""

        if not raw:
            return ""

        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return ""
        return "\n".join(text.splitlines()[-20:])

    def _关闭错误输出文件(self) -> None:
        stderr_file = self._stderr_file
        self._stderr_file = None
        if stderr_file is None:
            return
        try:
            stderr_file.close()
        except Exception:
            pass

    def _解析推流基地址(self, publish_base_url: str, server_url: str) -> str:
        if not self._使用服务地址推导推流地址(publish_base_url):
            return publish_base_url

        derived_publish_base_url = self._从服务地址推导推流地址(server_url)
        if derived_publish_base_url:
            return derived_publish_base_url

        legacy_default_publish_base_url = f"rtsp://{DEFAULT_SERVER_ADDR}:8554"
        if publish_base_url == legacy_default_publish_base_url:
            return legacy_default_publish_base_url
        return publish_base_url

    def _使用服务地址推导推流地址(self, publish_base_url: str) -> bool:
        if not publish_base_url:
            return True

        normalized_publish_base_url = publish_base_url.strip().lower()
        legacy_default_publish_base_url = f"rtsp://{DEFAULT_SERVER_ADDR}:8554"
        return normalized_publish_base_url in {
            MEDIA_PUBLISH_BASE_URL_AUTO.lower(),
            legacy_default_publish_base_url.lower(),
        }

    def _从服务地址推导推流地址(self, server_url: str) -> str:
        normalized_server_url = server_url.strip()
        if not normalized_server_url:
            return ""

        parsed_server_url = urlsplit(normalized_server_url)
        if not parsed_server_url.scheme:
            parsed_server_url = urlsplit(f"ws://{normalized_server_url}")

        hostname = parsed_server_url.hostname or ""
        if not hostname:
            return ""

        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        return f"rtsp://{hostname}:8554"
