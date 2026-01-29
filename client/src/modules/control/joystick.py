import json
import logging
from typing import Any, Dict, Optional


class JoystickController:
    """手柄控制器"""

    def __init__(self, process_controller: Any, logger: logging.Logger):
        """
        初始化手柄控制器

        Args:
            process_controller: 进程控制器实例
            logger: 日志记录器
        """
        self.process_controller = process_controller
        self.logger = logger

    def 处理命令(self, data: Dict[str, Any]) -> None:
        """
        处理手柄控制指令

        Args:
            data: 控制指令数据
        """
        command = data.get("command")
        mode = data.get("mode", "move")
        channel = data.get("channel")
        x = float(data.get("x", 0) or 0)
        y = float(data.get("y", 0) or 0)
        speed = float(data.get("speed", 5) or 5)

        self.logger.debug(
            f"收到控制指令: command={command}, mode={mode}, channel={channel}, x={x}, y={y}, speed={speed}"
        )

        if not command:
            return

        if command == "estop":
            self.logger.info("发送紧急停止指令")
            self.process_controller.发送命令(json.dumps({"type": "estop"}))
            return

        # 归一化速度倍率（1-10）
        speed_ratio = max(0.0, min(1.0, speed / 10.0))

        if command == "joystick":
            self.处理手柄移动指令(mode, channel, x, y, speed_ratio)
        elif command == "joystick_stop":
            self.处理手柄停止指令(mode, channel)

    def 处理手柄移动指令(self, mode: str, channel: Optional[str], x: float, y: float, speed_ratio: float) -> None:
        """处理手柄移动指令"""
        if mode == "two_leg" or channel == "two_leg":
            max_vx = 0.5
            max_yaw = 1.0

            vx = x * max_vx * speed_ratio
            yaw = y * max_yaw * speed_ratio

            # 过滤无效值
            if abs(vx) < 0.2:
                vx = 0.0
            if abs(yaw) < 0.2:
                yaw = 0.0

            payload = {
                "type": "two_leg",
                "vx": vx,
                "yaw_rate": yaw,
            }
            self.process_controller.发送命令(json.dumps(payload))
            return

        if mode == "pose" or channel == "pose":
            max_roll = 0.5
            max_pitch = 0.5
            roll_rate = y * max_roll * speed_ratio
            pitch_rate = -x * max_pitch * speed_ratio
            payload = {
                "type": "attitude",
                "roll_rate": roll_rate,
                "pitch_rate": pitch_rate,
                "yaw_rate": 0.0,
                "height_vel": 0.0,
            }
            self.process_controller.发送命令(json.dumps(payload))
            return

        # move 模式
        max_vx = 0.6
        max_vy = 0.4
        max_yaw = 0.6

        if channel == "look":
            yaw_rate = y * max_yaw * speed_ratio
            if abs(yaw_rate) < 0.02:
                yaw_rate = 0.0
            payload = {
                "type": "move",
                "vx": 0.0,
                "vy": 0.0,
                "yaw_rate": yaw_rate,
            }
            self.process_controller.发送命令(json.dumps(payload))
            return

        vx = x * max_vx * speed_ratio
        vy = y * max_vy * speed_ratio

        # 过滤无效的微小移动 (Deadzone)
        if abs(vx) < 0.05:
            vx = 0.0
        if abs(vy) < 0.1:
            vy = 0.0

        payload = {
            "type": "move",
            "vx": vx,
            "vy": vy,
            "yaw_rate": 0.0,
        }
        self.process_controller.发送命令(json.dumps(payload))

    def 处理手柄停止指令(self, mode: str, channel: Optional[str]) -> None:
        """处理手柄停止指令"""
        if mode == "two_leg" or channel == "two_leg":
            self.process_controller.发送命令(
                json.dumps({"type": "two_leg", "vx": 0.0, "yaw_rate": 0.0})
            )
            return

        if mode == "pose" or channel == "pose":
            self.process_controller.发送命令(
                json.dumps(
                    {"type": "attitude", "roll_rate": 0.0, "pitch_rate": 0.0, "yaw_rate": 0.0, "height_vel": 0.0}
                )
            )
            return

        self.process_controller.发送命令(json.dumps({"type": "move", "vx": 0.0, "vy": 0.0, "yaw_rate": 0.0}))
