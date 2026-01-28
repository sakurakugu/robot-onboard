# 该文件是动作执行器模块，负责处理用户输入的动作指令，目前是通过作为子程序进行执行的
import json
import socket
import threading
import time

from core.config import Config
from core.dog import sdk
from core.logger import configure_logger, logger
from core.utils import get_ipc_path


# 收集机器人状态
def _collect_status(app):
    return {
        "battery": app.getBatteryPower(), # 电量
        "mode": app.getCurrentCtrlmode(), # 控制模式
    }

# 循环发送机器人状态
def _send_status_loop(app, robot_uuid, ipc_path):
    seq = 0
    while True:
        try:
            msg = {
                "type": "status",
                "robot_id": robot_uuid,
                "seq": seq,
                "timestamp": int(time.time() * 1000), # 毫秒级时间戳
                "data": _collect_status(app),
            }
            seq += 1
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                s.settimeout(1.0) # 1秒超时
                s.connect(str(ipc_path))
                s.sendall((json.dumps(msg) + "\n").encode("utf-8"))
            finally:
                s.close()
        except socket.timeout:
            logger.warning("状态发送超时")
        except Exception as e:
            logger.exception("状态发送错误: %s", e)
        time.sleep(1) # 1秒发送一次状态

# 准备机器人
def _prepare_robot(app) -> None:
    logger.info("机器人正在站立...")
    app.standUp()
    time.sleep(3)
    logger.info("机器人准备好接收命令。")

# 处理控制指令
def _handle_control_payload(app, payload: dict) -> None:
    cmd_type = payload.get("type")
    if cmd_type == "move":
        app.move(
            float(payload.get("vx", 0) or 0),
            float(payload.get("vy", 0) or 0),
            float(payload.get("yaw_rate", 0) or 0),
        )
    elif cmd_type == "attitude":
        app.attitudeControl(
            float(payload.get("roll_rate", 0) or 0),
            float(payload.get("pitch_rate", 0) or 0),
            float(payload.get("yaw_rate", 0) or 0),
            float(payload.get("height_vel", 0) or 0),
        )
    elif cmd_type == "estop":
        app.passive()

# 执行站立动作
def _action_stand(app) -> None:
    logger.info("执行中: 站立")
    app.standUp()
    time.sleep(3)

# 执行趴下动作
def _action_lie_down(app) -> None:
    logger.info("执行中: 趴下")
    app.lieDown()
    time.sleep(3)

# 执行前进动作
def _action_forward(app) -> None:
    logger.info("执行中: 前进 (2秒)")
    app.move(0.2, 0, 0)
    time.sleep(2)
    app.move(0, 0, 0)

# 执行后退动作
def _action_backward(app) -> None:
    logger.info("执行中: 后退 (2秒)")
    app.move(-0.2, 0, 0)
    time.sleep(2)
    app.move(0, 0, 0)

# 执行左移动作
def _action_left(app) -> None:
    logger.info("执行中: 左移 (2秒)")
    app.move(0, 0.2, 0)
    time.sleep(2)
    app.move(0, 0, 0)

# 执行右移动作
def _action_right(app) -> None:
    logger.info("执行中: 右移 (2秒)")
    app.move(0, -0.2, 0)
    time.sleep(2)
    app.move(0, 0, 0)

# 执行左转动作
def _action_turn_left(app) -> None:
    logger.info("执行中: 左转 (2秒)")
    app.move(0, 0, 0.3)
    time.sleep(2)
    app.move(0, 0, 0)

# 执行右转动作
def _action_turn_right(app) -> None:
    logger.info("执行中: 右转 (2秒)")
    app.move(0, 0, -0.3)
    time.sleep(2)
    app.move(0, 0, 0)

# 执行跳跃动作
def _action_jump(app) -> None:
    logger.info("执行中: 跳跃")
    app.jump()
    time.sleep(4)

# 执行向前跳跃动作
def _action_front_jump(app) -> None:
    logger.info("执行中: 向前跳跃")
    app.frontJump()
    time.sleep(4)

# 执行后空翻动作
def _action_backflip(app) -> None:
    logger.info("执行中: 后空翻")
    app.backflip()
    time.sleep(4)

# 执行握手动作
def _action_shake(app) -> None:
    logger.info("执行中: 握手")
    app.shakeHand()
    time.sleep(4)

# 执行姿态控制动作
def _action_attitude(app) -> None:
    logger.info("执行中: 姿态控制 (4秒)")
    app.attitudeControl(0.1, 0.1, 0.1, 0.1)
    time.sleep(4)
    app.standUp()
    time.sleep(2)

# 执行双腿站立动作
def _action_two_leg(app) -> None:
    logger.info("执行中: 双腿站立")
    app.twoLegStand(0.0, 0.0)
    time.sleep(4)
    app.cancelTwoLegStand()
    time.sleep(2)

# 执行退出动作
def _action_exit(app) -> None:
    logger.info("退出演示。机器人将趴下。")
    app.lieDown()
    time.sleep(3)

# 动作处理映射
ACTION_HANDLERS = {
    "stand_up": _action_stand,
    "sit_down": _action_lie_down,
    "walk_forward": _action_forward,
    "walk_backward": _action_backward,
    "left": _action_left,
    "right": _action_right,
    "turn_left": _action_turn_left,
    "turn_right": _action_turn_right,
    "jump": _action_jump,
    "front_jump": _action_front_jump,
    "backflip": _action_backflip,
    "shake_hand": _action_shake,
    "nod": _action_attitude,
    "wave": _action_attitude,
    "dance": _action_jump,
    "two_leg_stand": _action_two_leg,
    "exit": _action_exit,
}

# 执行用户选择的动作
def _execute_choice(app, choice: str) -> bool:
    handler = ACTION_HANDLERS.get(choice)
    if not handler:
        logger.warning("无效的选择。请重试。")
        return False
    handler(app)
    return choice == "exit"

# 命令循环
def _command_loop(app) -> None:
    while True:
        raw = input("输入命令: ").strip()
        if not raw:
            continue
        if raw.startswith("{"):
            try:
                payload = json.loads(raw)
                _handle_control_payload(app, payload)
                continue
            except Exception as e:
                logger.error(f"解析控制指令失败: {e}")
                continue
        if _execute_choice(app, raw):
            break
        if raw not in ["stand_up", "sit_down", "exit"]:
            app.standUp()
            time.sleep(2)


def main():
    try:
        # 初始化配置
        config_store = Config.instance()
        config = config_store.get()
        logging_cfg = config.get("logging", {})
        configure_logger(
            log_dir=logging_cfg.get("log_dir"),
            level=logging_cfg.get("level", "INFO"),
            max_file_size_mb=logging_cfg.get("max_file_size_mb"),
        )
        app = sdk.HighLevel()
        sdk_cfg = config.get("sdk", {})
        robot_ip = sdk_cfg.get("robot_ip", "127.0.0.1")
        local_port = int(sdk_cfg.get("local_port", 43988) or 43988)
        app.initRobot(robot_ip, local_port, "127.0.0.1")
        logger.info("机器人连接初始化成功。")

        robot_uuid = config.get("robot", {}).get("uuid", "unknown")
        ipc_path = get_ipc_path("robot-chat")

        # 启动一个线程，循环发送机器人状态到IPC路径
        threading.Thread(target=_send_status_loop, args=(app, robot_uuid, ipc_path), daemon=True).start()

        _prepare_robot(app)
        _command_loop(app)

    except Exception as e:
        logger.error(f"发生意外错误: {e}", exc_info=True)


if __name__ == "__main__":
    main()
