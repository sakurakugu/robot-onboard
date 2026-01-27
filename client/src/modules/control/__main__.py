import json
import socket
import time
from core.utils import get_ipc_path
from core.config import Config
from core.dog import sdk

# 万一出现重名的“core文件夹、core.py”等，就添加这个
# from pathlib import Path
# import sys
# sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

def main():
    """运行交互式演示的主函数。"""
    try:
        app = sdk.HighLevel()
        # 仿真/本地测试时本地IP和机器人IP都使用 127.0.0.1
        app.initRobot("127.0.0.1", 43988, "127.0.0.1")
        print("机器人连接初始化成功。")

        config_store = Config.instance()
        robot_uuid = config_store.get().get("robot", {}).get("uuid", "unknown")
        ipc_path = get_ipc_path("robot-chat")
        ipc_path.parent.mkdir(parents=True, exist_ok=True)

        # 后台状态上报（每1秒）
        seq = 0

        def _收集状态():
            # 从SDK获取当前状态
            """
            | 返回值 | 说明 |
            |------|------|
            | 0 | 设备趴下，电机进入阻尼状态 |
            | 1 | 站立状态/打招呼状态 |
            | 10 | 设备趴下，短时间后电机进入自由状态 |
            | 18 | 移动状态 |
            | 21 | 动作状态(姿态模式、跳跃模式、双腿站立等) |
            | 51 | 趴下状态 |
            """
            return {
                "battery": app.getBatteryPower(),  # 电池电量（%）
                "voltage": None,  # 电压（V）
                "temperature": None,  # 温度（℃）
                "mode": app.getCurrentCtrlmode(),  # 控制模式
            }

        def _send_status_loop():
            nonlocal seq
            while True:
                try:
                    msg = {
                        "type": "status",
                        "robot_id": robot_uuid,
                        "seq": seq,
                        "timestamp": time.time(),
                        "data": _收集状态(),
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
                    # IPC不可用时忽略，稍后重试
                    pass
                time.sleep(1)

        import threading

        threading.Thread(target=_send_status_loop, daemon=True).start()

        # 通常需要先站立
        print("机器人正在站立...")
        app.standUp()
        time.sleep(3)
        print("机器人准备好接收命令。")

        while True:
            # print_menu()
            raw = input("输入命令编号: ").strip()
            if not raw:
                continue

            if raw.startswith("{"):
                try:
                    payload = json.loads(raw)
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
                    continue
                except Exception as e:
                    print(f"解析控制指令失败: {e}")
                    continue

            choice = raw

            if choice == "1":
                print("执行中: 站立")  # 站起来
                app.standUp()
                time.sleep(3)
            elif choice == "2":
                print("执行中: 趴下")  # 坐下
                app.lieDown()
                time.sleep(3)
            elif choice == "3":
                print("执行中: 前进 (2秒)")
                app.move(0.2, 0, 0)
                time.sleep(2)
                app.move(0, 0, 0)  # 停止
            elif choice == "4":
                print("执行中: 后退 (2秒)")
                app.move(-0.2, 0, 0)
                time.sleep(2)
                app.move(0, 0, 0)  # 停止
            elif choice == "5":
                print("执行中: 左移 (2秒)")
                app.move(0, 0.2, 0)
                time.sleep(2)
                app.move(0, 0, 0)  # 停止
            elif choice == "6":
                print("执行中: 右移 (2秒)")
                app.move(0, -0.2, 0)
                time.sleep(2)
                app.move(0, 0, 0)  # 停止
            elif choice == "7":
                print("执行中: 左转 (2秒)")
                app.move(0, 0, 0.3)
                time.sleep(2)
                app.move(0, 0, 0)  # 停止
            elif choice == "8":
                print("执行中: 右转 (2秒)")
                app.move(0, 0, -0.3)
                time.sleep(2)
                app.move(0, 0, 0)  # 停止
            elif choice == "9":
                print("执行中: 跳跃")  # 向上跳
                app.jump()
                time.sleep(4)
            elif choice == "10":
                print("执行中: 向前跳跃")
                app.frontJump()
                time.sleep(4)
            elif choice == "11":
                print("执行中: 后空翻")
                app.backflip()
                time.sleep(4)
            elif choice == "12":
                print("执行中: 握手")  # 打招呼
                app.shakeHand()
                time.sleep(4)
            elif choice == "13":
                print("执行中: 姿态控制 (4秒)")
                app.attitudeControl(0.1, 0.1, 0.1, 0.1)
                time.sleep(4)
                app.standUp()  # 返回稳定状态
                time.sleep(2)
            elif choice == "14":
                print("执行中: 双腿站立")
                app.twoLegStand(0.0, 0.0)
                time.sleep(4)
                app.cancelTwoLegStand()
                time.sleep(2)
            elif choice == "0":
                print("退出演示。机器人将趴下。")
                app.lieDown()
                time.sleep(3)
                break
            else:
                print("无效的选择。请重试。")

            # 确保大多数动作后机器人处于稳定的站立状态
            if choice not in ["1", "2", "0"]:
                app.standUp()
                time.sleep(2)

    except Exception as e:
        print(f"发生意外错误: {e}")


if __name__ == "__main__":
    main()
