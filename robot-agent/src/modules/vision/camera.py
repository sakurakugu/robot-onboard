"""相机拍照模块

使用OpenCV从RTSP流获取图片并转换为base64
"""

import base64
import logging
from typing import Optional

import cv2

logger = logging.getLogger(__name__)


def capture_photo(rtsp_url: str = "rtsp://127.0.0.1:8554/test", timeout: int = 5) -> Optional[str]:
    """从RTSP流捕获一张照片并转换为base64

    Args:
        rtsp_url: RTSP流地址，默认为本地地址
        timeout: 超时时间（秒）

    Returns:
        base64编码的JPEG图片，如果失败返回None
    """
    cap = None
    try:
        logger.info(f"正在连接RTSP流: {rtsp_url}")

        # 打开RTSP流，使用TCP传输
        cap = cv2.VideoCapture(rtsp_url + "?tcp", cv2.CAP_FFMPEG)

        # 设置较短的缓冲区
        if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # 设置超时
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout * 1000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout * 1000)

        if not cap.isOpened():
            logger.error("无法打开RTSP流")
            return None

        # 读取几帧以确保获取到最新的帧
        for _ in range(3):
            ret, frame = cap.read()
            if not ret:
                logger.warning("读取帧失败，继续尝试...")
                continue

        if not ret or frame is None:
            logger.error("无法读取视频帧")
            return None

        logger.info(f"成功捕获图片，分辨率: {frame.shape[1]}x{frame.shape[0]}")

        # 将图片编码为JPEG格式
        ret, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])

        if not ret:
            logger.error("图片编码失败")
            return None

        # 转换为base64
        jpg_as_text = base64.b64encode(buffer.tobytes()).decode("utf-8")

        logger.info(f"图片编码完成，base64长度: {len(jpg_as_text)}")
        return jpg_as_text

    except Exception as e:
        logger.error(f"捕获照片时发生错误: {e}", exc_info=True)
        return None

    finally:
        if cap is not None:
            cap.release()
            logger.debug("已释放相机资源")
