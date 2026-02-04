import base64
import hashlib
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from sparkrobot_common import WORKSPACE_DIR, get_logger

logger = get_logger("robot-agent")

class AudioPlaybackManager:
    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._last_hash: Optional[str] = None
        self._last_time: float = 0.0

    def _计算哈希值(self, buf_b64: str) -> str:
        """ 计算音频数据的哈希值 """
        return hashlib.sha256(buf_b64.encode("utf-8")).hexdigest()

    def 停止(self) -> None:
        """ 停止当前音频播放 """
        try:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
                self._proc.wait(timeout=2)
                logger.info("已停止当前音频播放")
        except Exception:
            try:
                if self._proc:
                    self._proc.kill()
            except Exception:
                pass
        finally:
            self._proc = None

    def 播放(self, data: Dict[str, Any]) -> None:
        """ 播放音频数据 """
        audio_format = data.get("format", "mp3")
        audio_buffer = data.get("buffer", "")
        duration = float(data.get("duration", 0) or 0)

        logger.info(f"收到音频响应: format={audio_format}, duration={duration}s")
        try:
            if audio_format not in ("webm", "mp3", "opus"):
                logger.error(f"不支持的音频格式: {audio_format}")
                return

            h = self._计算哈希值(audio_buffer)
            now = time.time()
            if self._last_hash == h and (now - self._last_time) < 3.0:
                logger.info("检测到短时间内重复的音频，跳过播放")
                return

            audio_data = base64.b64decode(audio_buffer)

            workspace_dir = WORKSPACE_DIR
            media_root = workspace_dir / ".cache" / "tts"
            try:
                media_root.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

            ts = int(now)
            if audio_format == "webm":
                audio_file = media_root / f"tts_{ts}.webm"
            elif audio_format == "mp3":
                audio_file = media_root / f"tts_{ts}.mp3"
            else:
                audio_file = media_root / f"tts_{ts}.opus"
            with open(audio_file, "wb") as f:
                f.write(audio_data)
            logger.info(f"音频已保存: {audio_file}")

            self.停止()
            try:
                self._proc = subprocess.Popen(
                    ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_file)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._last_hash = h
                self._last_time = now
                logger.info("音频播放已启动（音箱）")
            except Exception as e:
                logger.debug(f"音频播放启动失败: {e}")
        except Exception as e:
            logger.error(f"处理音频失败: {e}")


_manager = AudioPlaybackManager()

def 处理音频响应并播放(data: Dict[str, Any]) -> None:
    """ 处理音频响应并播放 """
    _manager.播放(data)


def 停止当前音频播放() -> None:
    """ 停止当前音频播放 """
    _manager.停止()
