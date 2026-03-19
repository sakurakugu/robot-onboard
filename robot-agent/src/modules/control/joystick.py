import json
from typing import Any, Dict, Optional

from sparkrobot_common import get_logger

logger = get_logger("robot-agent")

class JoystickController:
    """手柄控制器"""

    def __init__(self, process_controller: Any):
        """
        初始化手柄控制器

        Args:
            process_controller: 进程控制器实例
        """
        self.process_controller = process_controller

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
        joystick_raw = data.get("joystick")

        axis0 = 0.0
        axis1 = 0.0
        axis2 = 0.0
        axis3 = 0.0
        if isinstance(joystick_raw, list) and len(joystick_raw) >= 4:
            axis0 = float(joystick_raw[0] or 0)
            axis1 = float(joystick_raw[1] or 0)
            axis2 = float(joystick_raw[2] or 0)
            axis3 = float(joystick_raw[3] or 0)

        logger.debug(
            f"收到控制指令: command={command}, mode={mode}, channel={channel}, x={x}, y={y}, axes={[axis0, axis1, axis2, axis3]}, speed={speed}"
        )

        if not command:
            return

        if command == "estop":
            logger.info("发送紧急停止指令")
            self.process_controller.发送命令(json.dumps({"type": "estop"}))
            return

        # 归一化速度倍率（1-30）
        speed_ratio = max(0.0, min(1.0, speed / 30.0))

        # 优先使用四轴摇杆数据（兼容官方 remote joystick[4] 语义）
        if isinstance(joystick_raw, list) and len(joystick_raw) >= 4:
            if command == "joystick":
                self.处理四轴手柄移动指令(mode, axis0, axis1, axis2, axis3, speed_ratio)
            elif command == "joystick_stop":
                self.处理手柄停止指令(mode, channel)
            return

        if command == "joystick":
            self.处理手柄移动指令(mode, channel, x, y, speed_ratio)
        elif command == "joystick_stop":
            self.处理手柄停止指令(mode, channel)

    def 处理手柄移动指令(self, mode: str, channel: Optional[str], x: float, y: float, speed_ratio: float) -> None:
        """处理手柄移动指令"""
        if mode == "two_leg" or channel == "two_leg":
            max_vx = 3.0
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
        max_vx = 3.0
        max_vy = 1.0
        max_yaw = 3.0

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

    def 处理四轴手柄移动指令(
        self,
        mode: str,
        axis0: float,
        axis1: float,
        axis2: float,
        axis3: float,
        speed_ratio: float,
    ) -> None:
        """处理四轴摇杆指令（[Axis0, Axis1, Axis2, Axis3]）"""
        if mode == "two_leg":
            max_vx = 3.0
            max_yaw = 1.0

            vx = axis0 * max_vx * speed_ratio
            yaw = axis1 * max_yaw * speed_ratio

            if abs(vx) < 0.2:
                vx = 0.0
            if abs(yaw) < 0.2:
                yaw = 0.0

            self.process_controller.发送命令(
                json.dumps({"type": "two_leg", "vx": vx, "yaw_rate": yaw})
            )
            return

        if mode == "pose":
            max_roll = 0.5
            max_pitch = 0.5
            # 右摇杆：Axis2(水平) 控 pitch，Axis3(垂直) 控 roll
            roll_rate = axis3 * max_roll * speed_ratio
            pitch_rate = -axis2 * max_pitch * speed_ratio
            self.process_controller.发送命令(
                json.dumps(
                    {
                        "type": "attitude",
                        "roll_rate": roll_rate,
                        "pitch_rate": pitch_rate,
                        "yaw_rate": 0.0,
                        "height_vel": 0.0,
                    }
                )
            )
            return

        # move 模式：左摇杆控制平移，右摇杆 Axis2 控转向，实现可同时移动+转弯
        # 官方值：
        #       high_vx = 3.0, high_vy = 1.0, high_yaw = 3.0
        #       mid_vx = 2.0, mid_vy = 0.8, mid_yaw = 2.0
        #       low_vx = 1.0, low_vy = 0.5, low_yaw = 1.0
        max_vx = 3.0
        max_vy = 1.0
        max_yaw = 3.0

        vx = axis0 * max_vx * speed_ratio
        vy = axis1 * max_vy * speed_ratio
        # 方向校正：右摇杆上推应为右转，下拉应为左转
        yaw_rate = axis2 * max_yaw * speed_ratio

        if abs(vx) < 0.05:
            vx = 0.0
        if abs(vy) < 0.1:
            vy = 0.0
        if abs(yaw_rate) < 0.02:
            yaw_rate = 0.0

        self.process_controller.发送命令(
            json.dumps({"type": "move", "vx": vx, "vy": vy, "yaw_rate": yaw_rate})
        )

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
