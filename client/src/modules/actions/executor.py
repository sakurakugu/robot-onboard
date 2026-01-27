import json
import socket
import threading
import time

from core.config import Config
from core.dog import sdk
from core.utils import get_ipc_path

# 万一出现重名的“core文件夹、core.py”等，就添加这个
# from pathlib import Path
# import sys
# sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def _collect_status(app):
    return {
        "battery": app.getBatteryPower(),
        "voltage": None,
        "temperature": None,
        "mode": app.getCurrentCtrlmode(),
    }


def _send_status_loop(app, robot_uuid, ipc_path):
    seq = 0
    while True:
        try:
            msg = {
                "type": "status",
                "robot_id": robot_uuid,
                "seq": seq,
                "timestamp": time.time(),
                "data": _collect_status(app),
            }
            seq += 1
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                s.settimeout(1.0)
                s.connect(str(ipc_path))
                s.sendall((json.dumps(msg) + "\n").encode("utf-8"))
            finally:
                s.close()
        except Exception:
            pass
        time.sleep(1)


def _prepare_robot(app) -> None:
    print("机器人正在站立...")
    app.standUp()
    time.sleep(3)
    print("机器人准备好接收命令。")


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


def _action_stand(app) -> None:
    print("执行中: 站立")
    app.standUp()
    time.sleep(3)


def _action_lie_down(app) -> None:
    print("执行中: 趴下")
    app.lieDown()
    time.sleep(3)


def _action_forward(app) -> None:
    print("执行中: 前进 (2秒)")
    app.move(0.2, 0, 0)
    time.sleep(2)
    app.move(0, 0, 0)


def _action_backward(app) -> None:
    print("执行中: 后退 (2秒)")
    app.move(-0.2, 0, 0)
    time.sleep(2)
    app.move(0, 0, 0)


def _action_left(app) -> None:
    print("执行中: 左移 (2秒)")
    app.move(0, 0.2, 0)
    time.sleep(2)
    app.move(0, 0, 0)


def _action_right(app) -> None:
    print("执行中: 右移 (2秒)")
    app.move(0, -0.2, 0)
    time.sleep(2)
    app.move(0, 0, 0)


def _action_turn_left(app) -> None:
    print("执行中: 左转 (2秒)")
    app.move(0, 0, 0.3)
    time.sleep(2)
    app.move(0, 0, 0)


def _action_turn_right(app) -> None:
    print("执行中: 右转 (2秒)")
    app.move(0, 0, -0.3)
    time.sleep(2)
    app.move(0, 0, 0)


def _action_jump(app) -> None:
    print("执行中: 跳跃")
    app.jump()
    time.sleep(4)


def _action_front_jump(app) -> None:
    print("执行中: 向前跳跃")
    app.frontJump()
    time.sleep(4)


def _action_backflip(app) -> None:
    print("执行中: 后空翻")
    app.backflip()
    time.sleep(4)


def _action_shake(app) -> None:
    print("执行中: 握手")
    app.shakeHand()
    time.sleep(4)


def _action_attitude(app) -> None:
    print("执行中: 姿态控制 (4秒)")
    app.attitudeControl(0.1, 0.1, 0.1, 0.1)
    time.sleep(4)
    app.standUp()
    time.sleep(2)


def _action_two_leg(app) -> None:
    print("执行中: 双腿站立")
    app.twoLegStand(0.0, 0.0)
    time.sleep(4)
    app.cancelTwoLegStand()
    time.sleep(2)


def _action_exit(app) -> None:
    print("退出演示。机器人将趴下。")
    app.lieDown()
    time.sleep(3)


ACTION_HANDLERS = {
    "1": _action_stand,
    "2": _action_lie_down,
    "3": _action_forward,
    "4": _action_backward,
    "5": _action_left,
    "6": _action_right,
    "7": _action_turn_left,
    "8": _action_turn_right,
    "9": _action_jump,
    "10": _action_front_jump,
    "11": _action_backflip,
    "12": _action_shake,
    "13": _action_attitude,
    "14": _action_two_leg,
    "0": _action_exit,
}


def _execute_choice(app, choice: str) -> bool:
    handler = ACTION_HANDLERS.get(choice)
    if not handler:
        print("无效的选择。请重试。")
        return False
    handler(app)
    return choice == "0"


def _command_loop(app) -> None:
    while True:
        raw = input("输入命令编号: ").strip()
        if not raw:
            continue
        if raw.startswith("{"):
            try:
                payload = json.loads(raw)
                _handle_control_payload(app, payload)
                continue
            except Exception as e:
                print(f"解析控制指令失败: {e}")
                continue
        if _execute_choice(app, raw):
            break
        if raw not in ["1", "2", "0"]:
            app.standUp()
            time.sleep(2)


def main():
    try:
        app = sdk.HighLevel()
        app.initRobot("127.0.0.1", 43988, "127.0.0.1")
        print("机器人连接初始化成功。")

        config_store = Config.instance()
        robot_uuid = config_store.get().get("robot", {}).get("uuid", "unknown")
        ipc_path = get_ipc_path("robot-chat")
        ipc_path.parent.mkdir(parents=True, exist_ok=True)

        threading.Thread(target=_send_status_loop, args=(app, robot_uuid, ipc_path), daemon=True).start()

        _prepare_robot(app)
        _command_loop(app)

    except Exception as e:
        print(f"发生意外错误: {e}")


if __name__ == "__main__":
    main()
