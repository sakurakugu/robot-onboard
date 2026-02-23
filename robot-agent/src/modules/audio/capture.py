import asyncio
import threading
from collections import deque
from typing import Any, Awaitable, Callable, Dict, Optional

import numpy as np_module
import opuslib as opus_module
import sounddevice as sd_module
from sparkrobot_common import 生成UUID, get_logger

logger = get_logger("robot-agent")


class ThreadSafeAudioBuffer:
    """线程安全的音频缓冲区，使用固定大小的环形缓冲区避免队列满的问题"""

    def __init__(self, maxsize: int = 100):
        self._buffer: deque = deque(maxlen=maxsize)
        self._lock = threading.Lock()
        self._event = asyncio.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._closed = False

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """设置事件循环"""
        self._loop = loop

    def put(self, data) -> bool:
        """线程安全地放入数据（从音频回调线程调用）

        使用环形缓冲区，当缓冲区满时会自动丢弃最旧的数据，不会抛出异常
        """
        if self._closed:
            return False
        with self._lock:
            if self._closed:
                return False
            self._buffer.append(data)
        # 安全地通知事件循环有新数据
        if self._loop and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(self._set_event)
            except RuntimeError:
                # 事件循环已关闭
                pass
        return True

    def _set_event(self) -> None:
        """在事件循环中设置事件"""
        if not self._closed:
            self._event.set()

    async def get(self) -> Optional[Any]:
        """异步获取数据（从事件循环调用）"""
        while not self._closed:
            with self._lock:
                if self._buffer:
                    return self._buffer.popleft()
            # 清除事件并等待新数据
            self._event.clear()
            try:
                await asyncio.wait_for(self._event.wait(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                return None
        return None

    def close(self) -> None:
        """关闭缓冲区"""
        self._closed = True
        with self._lock:
            self._buffer.clear()
        if self._loop and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(self._set_event)
            except RuntimeError:
                pass

    def clear(self) -> None:
        """清空缓冲区"""
        with self._lock:
            self._buffer.clear()

    @property
    def qsize(self) -> int:
        """获取当前缓冲区大小"""
        with self._lock:
            return len(self._buffer)


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
        self.检查是否连接 = is_connected
        self.检查是否上传连接 = is_upload_connected
        self.发送音频开始 = send_audio_start
        self.发送音频数据块 = send_audio_chunk
        self.发送音频结束 = send_audio_end
        self.audio_streaming_enabled = bool(config.get("audio", {}).get("enable_streaming", True))
        self._audio_buffer: Optional[ThreadSafeAudioBuffer] = None

    async def 开始采集(self) -> None:
        """ 运行音频捕获循环 """
        audio_cfg = self.config.get("audio", {})
        settings = self._读取配置(audio_cfg)
        await self._采集循环(settings)

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

    async def _采集循环(self, settings: Dict[str, Any]) -> None:
        """ 音频捕获循环 """
        encoder = opus_module.Encoder(settings["sample_rate"], settings["channels"], opus_module.APPLICATION_VOIP)
        loop = asyncio.get_running_loop()

        # 使用线程安全的音频缓冲区替代 asyncio.Queue
        audio_buffer = ThreadSafeAudioBuffer(maxsize=100)
        self._audio_buffer = audio_buffer
        audio_buffer.set_loop(loop)

        def callback(indata, frames, time_info, status):
            if status:
                logger.debug(f"音频采集状态: {status}")
            # 使用线程安全的缓冲区，不会抛出异常
            audio_buffer.put(indata.copy())

        stream = None
        state = {"session_id": None, "seq": 0, "silence_frames": 0, "frames_in_segment": 0}
        try:
            while self.检查是否连接() and (not self.audio_streaming_enabled or self.检查是否上传连接()):
                if self._需要暂停音频流():
                    stream = await self._暂停音频流(stream, state)
                    await asyncio.sleep(0.5)
                    continue

                stream = self._确保音频流已启动(stream, settings, callback)
                pcm_block = await self._读取音频块()
                if pcm_block is None:
                    break
                await self._处理音频块(pcm_block, settings, state, encoder)
        finally:
            await self._清理音频流(stream, state)

    def _需要暂停音频流(self) -> bool:
        """ 检查是否需要暂停音频流 """
        return not self.audio_streaming_enabled or not self.检查是否上传连接()

    async def _暂停音频流(self, stream, state: Dict[str, Any]):
        """ 暂停音频流 """
        session_id = state["session_id"]
        if session_id is not None:
            await self.发送音频结束(session_id, "manual")
            state.update({"session_id": None, "seq": 0, "silence_frames": 0, "frames_in_segment": 0})
        # 清空缓冲区中的旧数据
        if self._audio_buffer:
            self._audio_buffer.clear()
        return self._停止音频流(stream)

    def _确保音频流已启动(self, stream, settings: Dict[str, Any], callback):
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
        logger.info("麦克风采集已启动")
        return stream

    async def _读取音频块(self) -> Optional[Any]:
        """ 从缓冲区读取音频块 """
        if self._audio_buffer is None:
            return None
        try:
            return await self._audio_buffer.get()
        except asyncio.CancelledError:
            return None

    async def _处理音频块(
        self, pcm_block, settings: Dict[str, Any], state: Dict[str, Any], encoder
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
            logger.debug(f"音频会话开始: {session_id}")

        opus_bytes = encoder.encode(pcm.tobytes(), settings["frame_size"])
        await self.发送音频数据块(session_id, state["seq"], opus_bytes, settings["frame_duration_ms"])
        state["seq"] += 1
        state["frames_in_segment"] += 1
        state["silence_frames"] = 0

        if state["frames_in_segment"] >= settings["max_frames"]:
            await self.发送音频结束(session_id, "max_length")
            logger.debug(f"音频会话结束(长度): {session_id}")
            state["session_id"] = None

    async def _处理静音块(self, settings: Dict[str, Any], state: Dict[str, Any]) -> None:
        """ 处理静音块 """
        session_id = state["session_id"]
        if session_id is None:
            return
        state["silence_frames"] += 1
        if state["silence_frames"] >= settings["silence_frames_limit"]:
            await self.发送音频结束(session_id, "silence")
            logger.debug(f"音频会话结束(静音): {session_id}")
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
        # 关闭音频缓冲区
        if self._audio_buffer:
            self._audio_buffer.close()
            self._audio_buffer = None
        logger.info("麦克风采集已停止")
