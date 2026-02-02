import asyncio
from typing import Any, Awaitable, Callable, Dict, cast

from sparkrobot_common import 生成UUID

try:
    import os
    if os.name == "nt":
        dll_path = r"C:\Software\Deps\C++\vcpkg\installed\x64-windows\bin"
        os.add_dll_directory(dll_path)

    import numpy as np
    import opuslib as opuslib
    import sounddevice as sd
except ImportError as e:
    raise ImportError(f"缺少音频依赖，请安装: numpy sounddevice opuslib (导入错误: {e})") from e

from sparkrobot_common import get_logger

class AudioCapture:
    def __init__(
        self,
        config: Dict[str, Any],
        is_connected: Callable[[], bool],
        is_upload_connected: Callable[[], bool],
        send_audio_start: Callable[[str, int], Awaitable[None]],
        send_audio_chunk: Callable[[str, int, bytes, int], Awaitable[None]],
        send_audio_end: Callable[[str, str], Awaitable[None]],
    ):
        self.config = config
        self.logger = get_logger("robot-agent")
        self.is_connected = is_connected
        self.is_upload_connected = is_upload_connected
        self.发送音频开始 = send_audio_start
        self.发送音频数据块 = send_audio_chunk
        self.发送音频结束 = send_audio_end
        self.audio_streaming_enabled = bool(config.get("audio", {}).get("enable_streaming", True))

    async def 开始采集(self) -> None:
        """ 运行音频捕获循环 """
        audio_cfg = self.config.get("audio", {})
        np_module = cast(Any, np)
        sd_module = cast(Any, sd)
        opus_module = cast(Any, opuslib)
        settings = self._读取配置(audio_cfg)
        await self._采集循环(settings, np_module, sd_module, opus_module)

    def _读取配置(self, audio_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """ 构建音频捕获设置 """
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

    async def _采集循环(self, settings: Dict[str, Any], np_module, sd_module, opus_module) -> None:
        """ 音频捕获循环 """
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
            while self.is_connected() and (not self.audio_streaming_enabled or self.is_upload_connected()):
                if self._需要暂停音频流():
                    stream = await self._暂停音频流(stream, state)
                    await asyncio.sleep(0.5)
                    continue

                stream = self._确保音频流已启动(stream, settings, callback, sd_module)
                pcm_block = await self._读取音频块(queue)
                if pcm_block is None:
                    break
                await self._处理音频块(pcm_block, settings, state, encoder, np_module)
        finally:
            await self._清理音频流(stream, state)

    def _需要暂停音频流(self) -> bool:
        """ 检查是否需要暂停音频流 """
        return not self.audio_streaming_enabled or not self.is_upload_connected()

    async def _暂停音频流(self, stream, state: Dict[str, Any]):
        """ 暂停音频流 """
        session_id = state["session_id"]
        if session_id is not None:
            await self.发送音频结束(session_id, "manual")
            state.update({"session_id": None, "seq": 0, "silence_frames": 0, "frames_in_segment": 0})
        return self._停止音频流(stream)

    def _确保音频流已启动(self, stream, settings: Dict[str, Any], callback, sd_module):
        """ 确保音频流已启动 """
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

    async def _读取音频块(self, queue: asyncio.Queue):
        """ 从队列读取音频块 """
        try:
            return await queue.get()
        except asyncio.CancelledError:
            return None

    async def _处理音频块(
        self, pcm_block, settings: Dict[str, Any], state: Dict[str, Any], encoder, np_module
    ) -> None:
        """ 处理音频块 """
        pcm = np_module.reshape(pcm_block, (-1,))
        rms = float(np_module.sqrt(np_module.mean(pcm.astype(np_module.float32) ** 2))) / 32768.0
        if rms >= settings["vad_threshold"]:
            await self._处理语音块(pcm, settings, state, encoder)
        else:
            await self._处理静音块(settings, state)

    async def _处理语音块(self, pcm, settings: Dict[str, Any], state: Dict[str, Any], encoder) -> None:
        """ 处理语音块 """
        session_id = state["session_id"]
        if session_id is None:
            session_id = 生成UUID()
            state["session_id"] = session_id
            state["seq"] = 0
            state["silence_frames"] = 0
            state["frames_in_segment"] = 0
            await self.发送音频开始(session_id, settings["frame_duration_ms"])
            self.logger.debug(f"音频会话开始: {session_id}")

        opus_bytes = encoder.encode(pcm.tobytes(), settings["frame_size"])
        await self.发送音频数据块(session_id, state["seq"], opus_bytes, settings["frame_duration_ms"])
        state["seq"] += 1
        state["frames_in_segment"] += 1
        state["silence_frames"] = 0

        if state["frames_in_segment"] >= settings["max_frames"]:
            await self.发送音频结束(session_id, "max_length")
            self.logger.debug(f"音频会话结束(长度): {session_id}")
            state["session_id"] = None

    async def _处理静音块(self, settings: Dict[str, Any], state: Dict[str, Any]) -> None:
        """ 处理静音块 """
        session_id = state["session_id"]
        if session_id is None:
            return
        state["silence_frames"] += 1
        if state["silence_frames"] >= settings["silence_frames_limit"]:
            await self.发送音频结束(session_id, "silence")
            self.logger.debug(f"音频会话结束(静音): {session_id}")
            state.update({"session_id": None, "seq": 0, "silence_frames": 0, "frames_in_segment": 0})

    def _停止音频流(self, stream):
        """ 停止音频流 """
        if stream:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        return None

    async def _清理音频流(self, stream, state: Dict[str, Any]) -> None:
        """ 清理音频流 """
        session_id = state["session_id"]
        if session_id is not None:
            await self.发送音频结束(session_id, "manual")
        self._停止音频流(stream)
        self.logger.info("麦克风采集已停止")
