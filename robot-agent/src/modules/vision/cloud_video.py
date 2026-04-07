"""云端视频抽帧上传模块

通过独立线程从本地 RTSP 拉流，编码为 JPEG 后回调给上层发送。
这样不会阻塞主事件循环，适合作为当前云端视频的过渡实现。
"""

import asyncio
import base64
import logging
import threading
import time
from concurrent.futures import Future
from typing import Any, Callable, Coroutine, Optional

import cv2

logger = logging.getLogger(__name__)


class 云端视频流管理器:
    """管理云端视频抽帧线程。"""

    def __init__(
        self,
        发送视频帧: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
        rtsp_url: str = "rtsp://127.0.0.1:8554/test",
        fps: float = 4.0,
        quality: int = 70,
        max_width: int = 960,
    ) -> None:
        self._发送视频帧 = 发送视频帧
        self._默认_rtsp_url = rtsp_url
        self._fps = max(fps, 0.5)
        self._quality = max(30, min(quality, 90))
        self._max_width = max_width
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._rtsp_url = rtsp_url

    @property
    def 正在运行(self) -> bool:
        """是否已有推流线程在运行。"""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    async def 启动(self, rtsp_url: Optional[str] = None) -> None:
        """启动云端视频抽帧。"""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._rtsp_url = rtsp_url or self._默认_rtsp_url
            self._loop = asyncio.get_running_loop()
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._推流线程主循环,
                name="cloud-video-stream",
                daemon=True,
            )
            self._thread.start()
        logger.info(f"云端视频抽帧已启动: {self._rtsp_url}")

    async def 停止(self) -> None:
        """停止云端视频抽帧。"""
        with self._lock:
            thread = self._thread
            self._stop_event.set()

        if thread is None:
            return

        await asyncio.to_thread(thread.join, 3.0)
        with self._lock:
            if self._thread is thread and not thread.is_alive():
                self._thread = None
                self._loop = None

        if thread.is_alive():
            logger.warning("云端视频抽帧线程未能在超时时间内退出")
            return

        logger.info("云端视频抽帧已停止")

    def _推流线程主循环(self) -> None:
        cap = None
        interval = 1.0 / self._fps
        next_deadline = time.monotonic()

        try:
            while not self._stop_event.is_set():
                if cap is None or not cap.isOpened():
                    cap = self._打开视频流(self._rtsp_url)
                    if cap is None:
                        if self._stop_event.wait(1.0):
                            break
                        next_deadline = time.monotonic()
                        continue

                payload = self._读取并编码视频帧(cap)
                if payload is None:
                    logger.warning("读取云端视频帧失败，准备重连 RTSP")
                    cap.release()
                    cap = None
                    if self._stop_event.wait(1.0):
                        break
                    next_deadline = time.monotonic()
                    continue

                if not self._提交视频帧(payload):
                    logger.warning("提交云端视频帧失败，停止当前推流线程")
                    break

                next_deadline += interval
                wait_seconds = max(0.0, next_deadline - time.monotonic())
                if self._stop_event.wait(wait_seconds):
                    break
                if wait_seconds == 0:
                    next_deadline = time.monotonic()
        finally:
            if cap is not None:
                cap.release()
            with self._lock:
                current = threading.current_thread()
                if self._thread is current:
                    self._thread = None
                    self._loop = None

    def _打开视频流(self, rtsp_url: str):  # type: ignore[no-untyped-def]
        logger.info(f"正在打开云端视频 RTSP 流: {rtsp_url}")
        cap = cv2.VideoCapture(self._拼接_tcp_rtsp_url(rtsp_url), cv2.CAP_FFMPEG)

        if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
            cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
            cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 2000)

        if not cap.isOpened():
            logger.error("无法打开云端视频 RTSP 流")
            cap.release()
            return None

        return cap

    def _读取并编码视频帧(self, cap):  # type: ignore[no-untyped-def]
        ok, frame = cap.read()
        if not ok or frame is None:
            return None

        height, width = frame.shape[:2]
        if self._max_width > 0 and width > self._max_width:
            scale = self._max_width / float(width)
            resized_height = max(1, int(height * scale))
            frame = cv2.resize(frame, (self._max_width, resized_height), interpolation=cv2.INTER_AREA)
            height, width = frame.shape[:2]

        encoded_ok, buffer = cv2.imencode(
            ".jpg",
            frame,
            [cv2.IMWRITE_JPEG_QUALITY, self._quality],
        )
        if not encoded_ok:
            logger.error("编码云端视频帧失败")
            return None

        return {
            "frame": base64.b64encode(buffer.tobytes()).decode("ascii"),
            "width": int(width),
            "height": int(height),
            "capturedAt": int(time.time() * 1000),
        }

    def _提交视频帧(self, payload: dict[str, Any]) -> bool:
        loop = self._loop
        if loop is None or loop.is_closed():
            return False

        try:
            future: Future[None] = asyncio.run_coroutine_threadsafe(self._发送视频帧(payload), loop)
            future.result(timeout=3.0)
            return True
        except Exception as exc:
            logger.error(f"提交云端视频帧失败: {exc}")
            return False

    def _拼接_tcp_rtsp_url(self, rtsp_url: str) -> str:
        separator = "&" if "?" in rtsp_url else "?"
        return f"{rtsp_url}{separator}tcp"
