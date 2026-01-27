import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional, cast

from core.utils import generate_uuid

_AUDIO_IMPORT_ERROR: Optional[Exception] = None
np: Optional[Any] = None
sd: Optional[Any] = None
opuslib: Optional[Any] = None
try:
    import numpy as _np
    import opuslib as _opuslib
    import sounddevice as _sd
except Exception as e:
    np = None
    sd = None
    opuslib = None
    _AUDIO_IMPORT_ERROR = e
else:
    np = _np
    sd = _sd
    opuslib = _opuslib


class AudioCapture:
    def __init__(
        self,
        config: Dict[str, Any],
        logger,
        is_connected: Callable[[], bool],
        is_upload_connected: Callable[[], bool],
        send_audio_start: Callable[[str, int], Awaitable[None]],
        send_audio_chunk: Callable[[str, int, bytes, int], Awaitable[None]],
        send_audio_end: Callable[[str, str], Awaitable[None]],
    ):
        self.config = config
        self.logger = logger
        self.is_connected = is_connected
        self.is_upload_connected = is_upload_connected
        self.send_audio_start = send_audio_start
        self.send_audio_chunk = send_audio_chunk
        self.send_audio_end = send_audio_end
        self.audio_streaming_enabled = bool(config.get("audio", {}).get("enable_streaming", True))

    async def run(self) -> None:
        audio_cfg = self.config.get("audio", {})
        if not self._audio_ready():
            return
        np_module = cast(Any, np)
        sd_module = cast(Any, sd)
        opus_module = cast(Any, opuslib)
        settings = self._build_settings(audio_cfg)
        await self._capture_loop(settings, np_module, sd_module, opus_module)

    def _audio_ready(self) -> bool:
        if np is None or sd is None or opuslib is None:
            detail = f" (导入错误: {_AUDIO_IMPORT_ERROR})" if _AUDIO_IMPORT_ERROR else ""
            self.logger.warning(f"缺少音频依赖，请安装: numpy sounddevice opuslib{detail}")
            return False
        return True

    def _build_settings(self, audio_cfg: Dict[str, Any]) -> Dict[str, Any]:
        sample_rate = int(audio_cfg.get("sample_rate", 16000))
        channels = int(audio_cfg.get("channels", 1))
        frame_duration_ms = int(audio_cfg.get("frame_duration_ms", 20))
        frame_size = int(sample_rate * frame_duration_ms / 1000)
        vad_threshold = float(audio_cfg.get("vad_threshold", 0.015))
        vad_silence_ms = int(audio_cfg.get("vad_silence_ms", 800))
        max_segment_ms = int(audio_cfg.get("max_segment_ms", 10000))
        return {
            "sample_rate": sample_rate,
            "channels": channels,
            "frame_duration_ms": frame_duration_ms,
            "frame_size": frame_size,
            "vad_threshold": vad_threshold,
            "silence_frames_limit": max(1, int(vad_silence_ms / frame_duration_ms)),
            "max_frames": max(1, int(max_segment_ms / frame_duration_ms)),
            "input_device": audio_cfg.get("input_device"),
        }

    async def _capture_loop(self, settings: Dict[str, Any], np_module, sd_module, opus_module) -> None:
        encoder = opus_module.Encoder(settings["sample_rate"], settings["channels"], opus_module.APPLICATION_VOIP)
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)

        def callback(indata, frames, time_info, status):
            if status:
                self.logger.debug(f"音频采集状态: {status}")
            data = indata.copy()
            try:
                loop.call_soon_threadsafe(queue.put_nowait, data)
            except Exception:
                pass

        stream = None
        state = {"session_id": None, "seq": 0, "silence_frames": 0, "frames_in_segment": 0}
        try:
            while self.is_connected():
                if self._should_pause_streaming():
                    stream = await self._pause_stream(stream, state)
                    await asyncio.sleep(0.5)
                    continue

                stream = self._ensure_stream(stream, settings, callback, sd_module)
                pcm_block = await self._read_block(queue)
                if pcm_block is None:
                    break
                await self._handle_block(pcm_block, settings, state, encoder, np_module)
        finally:
            await self._cleanup(stream, state)

    def _should_pause_streaming(self) -> bool:
        return not self.audio_streaming_enabled or not self.is_upload_connected()

    async def _pause_stream(self, stream, state: Dict[str, Any]):
        session_id = state["session_id"]
        if session_id is not None:
            await self.send_audio_end(session_id, "manual")
            state.update({"session_id": None, "seq": 0, "silence_frames": 0, "frames_in_segment": 0})
        return self._stop_stream(stream)

    def _ensure_stream(self, stream, settings: Dict[str, Any], callback, sd_module):
        if stream is not None:
            return stream
        stream = sd_module.InputStream(
            samplerate=settings["sample_rate"],
            channels=settings["channels"],
            dtype="int16",
            blocksize=settings["frame_size"],
            callback=callback,
            device=settings["input_device"] if settings["input_device"] else None,
        )
        stream.start()
        self.logger.info("麦克风采集已启动")
        return stream

    async def _read_block(self, queue: asyncio.Queue):
        try:
            return await queue.get()
        except asyncio.CancelledError:
            return None

    async def _handle_block(
        self, pcm_block, settings: Dict[str, Any], state: Dict[str, Any], encoder, np_module
    ) -> None:
        pcm = np_module.reshape(pcm_block, (-1,))
        rms = float(np_module.sqrt(np_module.mean(pcm.astype(np_module.float32) ** 2))) / 32768.0
        if rms >= settings["vad_threshold"]:
            await self._handle_voice(pcm, settings, state, encoder)
        else:
            await self._handle_silence(settings, state)

    async def _handle_voice(self, pcm, settings: Dict[str, Any], state: Dict[str, Any], encoder) -> None:
        session_id = state["session_id"]
        if session_id is None:
            session_id = generate_uuid()
            state["session_id"] = session_id
            state["seq"] = 0
            state["silence_frames"] = 0
            state["frames_in_segment"] = 0
            await self.send_audio_start(session_id, settings["frame_duration_ms"])
            self.logger.debug(f"音频会话开始: {session_id}")

        opus_bytes = encoder.encode(pcm.tobytes(), settings["frame_size"])
        await self.send_audio_chunk(session_id, state["seq"], opus_bytes, settings["frame_duration_ms"])
        state["seq"] += 1
        state["frames_in_segment"] += 1
        state["silence_frames"] = 0

        if state["frames_in_segment"] >= settings["max_frames"]:
            await self.send_audio_end(session_id, "max_length")
            self.logger.debug(f"音频会话结束(长度): {session_id}")
            state["session_id"] = None

    async def _handle_silence(self, settings: Dict[str, Any], state: Dict[str, Any]) -> None:
        session_id = state["session_id"]
        if session_id is None:
            return
        state["silence_frames"] += 1
        if state["silence_frames"] >= settings["silence_frames_limit"]:
            await self.send_audio_end(session_id, "silence")
            self.logger.debug(f"音频会话结束(静音): {session_id}")
            state.update({"session_id": None, "seq": 0, "silence_frames": 0, "frames_in_segment": 0})

    def _stop_stream(self, stream):
        if stream:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        return None

    async def _cleanup(self, stream, state: Dict[str, Any]) -> None:
        session_id = state["session_id"]
        if session_id is not None:
            await self.send_audio_end(session_id, "manual")
        self._stop_stream(stream)
        self.logger.info("麦克风采集已停止")
