from pathlib import Path

from sparkrobot_common import 获取项目版本

__version__ = 获取项目版本(Path(__file__).resolve().parents[1], "robot-agent", "0.1.0")

__all__ = ["__version__"]
