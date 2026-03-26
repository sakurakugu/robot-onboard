"""视觉模块"""

from .camera import capture_photo
from .target_tracker import (
    从参数解析目标框,
    归一化目标框,
    打开视频流,
    读取最新视频帧,
    静态目标跟踪器,
)

__all__ = ["capture_photo", "从参数解析目标框", "打开视频流", "归一化目标框", "读取最新视频帧", "静态目标跟踪器"]
