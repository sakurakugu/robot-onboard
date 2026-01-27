import base64
import subprocess
import time
from pathlib import Path
from typing import Any, Dict


def handle_audio_response(data: Dict[str, Any], logger, log_dir: Path) -> None:
    audio_format = data.get("format", "webm")
    audio_buffer = data.get("buffer", "")
    duration = data.get("duration", 0)

    logger.info(f"收到音频响应: format={audio_format}, duration={duration}s")

    try:
        if audio_format not in ("webm", "mp3", "opus"):
            logger.error(f"不支持的音频格式: {audio_format}")
            return
        audio_data = base64.b64decode(audio_buffer)

        ts = int(time.time())
        if audio_format == "webm":
            audio_file = log_dir / f"audio_{ts}.webm"
        elif audio_format == "mp3":
            audio_file = log_dir / f"audio_{ts}.mp3"
        else:
            audio_file = log_dir / f"audio_{ts}.opus"
        with open(audio_file, "wb") as f:
            f.write(audio_data)
        logger.info(f"音频已保存: {audio_file}")

        try:
            subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(audio_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.info("音频播放已启动（音箱）")
        except Exception as e:
            logger.debug(f"音频播放启动失败: {e}")
    except Exception as e:
        logger.error(f"处理音频失败: {e}")
