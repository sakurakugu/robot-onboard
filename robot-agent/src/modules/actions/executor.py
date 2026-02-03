# 该文件是动作执行器模块，负责处理用户输入的动作指令，目前是通过作为子程序进行执行的
import json
import socket
import threading
import time

from sparkrobot_common import ORG_NAME, 获取IPC路径, configure_logger, get_logger

from core.config import Config
from core.dog import sdk

APP_NAME = "robot-agent"
logger = get_logger(APP_NAME)


def _收集机器人状态(app):
    return {
        "battery": app.getBatteryPower(), # 电量
        "mode": app.getCurrentCtrlmode(), # 控制模式
    }

def _循环发送机器人状态(app, robot_uuid, ipc_path):
    seq = 0
    while True:
        try:
            msg = {
                "type": "status",
                "robotId": robot_uuid,
                "seq": seq,
                "timestamp": int(time.time() * 1000), # 毫秒级时间戳
                "data": _收集机器人状态(app),
            }
            seq += 1
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) # type: ignore[attr-defined]
            try:
                s.settimeout(1.0) # 1秒超时
                s.connect(str(ipc_path))
                s.sendall((json.dumps(msg) + "\n").encode("utf-8"))
            finally:
                s.close()
        except socket.timeout:
            logger.warning("状态发送超时")
        except FileNotFoundError:
            logger.warning("IPC服务未就绪")
        except Exception as e:
            logger.exception("状态发送错误: %s", e)
        time.sleep(1) # 1秒发送一次状态

def _启动机器人(app) -> None:
    logger.info("机器人正在站立...")
    app.standUp()
    time.sleep(3)
    logger.info("机器人准备好接收命令。")

def _处理控制指令(app, payload: dict) -> None:
    cmd_type = payload.get("type")
    if cmd_type == "move":
        app.move(
            float(payload.get("vx", 0) or 0),
            float(payload.get("vy", 0) or 0),
            float(payload.get("yaw_rate", 0) or 0),
        )
    elif cmd_type == "two_leg":
        app.twoLegStand(
            float(payload.get("vx", 0) or 0),
            float(payload.get("yaw_rate", 0) or 0),
        )
    elif cmd_type == "attitude":
        app.attitudeControl(
            float(payload.get("roll_rate", 0) or 0),  # 横滚角速度
            float(payload.get("pitch_rate", 0) or 0), # 俯仰角速度
            float(payload.get("yaw_rate", 0) or 0),   # 偏航角速度
            float(payload.get("height_vel", 0) or 0), # 垂直高度速度
        )
    elif cmd_type == "estop":
        app.passive() # 进入紧急趴下模式

# 执行站立动作
def _执行站立动作(app) -> None:
    logger.info("执行中: 站立")
    app.standUp()
    time.sleep(3)

# 执行趴下动作
def _执行趴下动作(app) -> None:
    logger.info("执行中: 趴下")
    app.lieDown()
    time.sleep(3)

# 执行跳跃动作
def _执行跳跃动作(app) -> None:
    logger.info("执行中: 跳跃")
    app.jump()
    time.sleep(4)

# 执行向前跳跃动作
def _执行向前跳跃动作(app) -> None:
    logger.info("执行中: 向前跳跃")
    app.frontJump()
    time.sleep(4)

# 执行后空翻动作
def _执行后空翻动作(app) -> None:
    logger.info("执行中: 后空翻")
    app.backflip()
    time.sleep(4)

# 执行握手动作
def _执行握手动作(app) -> None:
    logger.info("执行中: 握手")
    app.shakeHand()
    time.sleep(4)

# 执行姿态控制动作
def _执行姿态控制动作(app) -> None:
    logger.info("执行中: 姿态控制 (4秒)")
    app.attitudeControl(0.1, 0.1, 0.1, 0.1)
    time.sleep(4)
    app.standUp()
    time.sleep(2)

# 执行双腿站立动作（一次性）
def _执行双腿站立动作_一次性(app) -> None:
    logger.info("执行中: 双腿站立")
    app.twoLegStand(0.0, 0.0)
    time.sleep(4)
    app.cancelTwoLegStand()
    time.sleep(2)

# 执行双腿站立动作
def _执行双腿站立动作(app) -> None:
    logger.info("执行中: 双腿站立")
    app.twoLegStand(0.0, 0.0)

# 退出双腿站立
def _执行退出双腿站立动作(app) -> None:
    logger.info("执行中: 退出双腿站立")
    app.cancelTwoLegStand()
    time.sleep(1)

# 执行退出动作（趴下）
def _执行退出趴下动作(app) -> None:
    logger.info("退出演示。机器人将趴下。")
    app.lieDown()
    time.sleep(3)

# 执行退出动作（站立）
def _执行退出站立动作(app) -> None:
    logger.info("退出演示。机器人将站立。")
    app.standUp()
    time.sleep(3)

# 执行退出动作（先趴下后急停）
def _执行退出停止动作(app) -> None:
    logger.info("退出演示。机器人将先趴下再急停。")
    app.lieDown()
    time.sleep(2)
    app.passive()
    time.sleep(1)

# 执行move动作（带参数的移动控制）
def _执行move动作(app, params: dict) -> None:
    vx = float(params.get("vx", 0) or 0)
    vy = float(params.get("vy", 0) or 0)
    yaw_rate = float(params.get("yaw_rate", 0) or 0)
    duration = float(params.get("duration", 2) or 2)
    
    logger.info(f"执行中: 移动控制 (vx={vx}, vy={vy}, yaw_rate={yaw_rate}, {duration}秒)")
    app.move(vx, vy, yaw_rate)
    time.sleep(duration)
    app.move(0, 0, 0)

# 动作处理映射
ACTION_HANDLERS = {
    "stand_up": _执行站立动作,
    "sit_down": _执行趴下动作,
    "jump": _执行跳跃动作,
    "front_jump": _执行向前跳跃动作,
    "backflip": _执行后空翻动作,
    "shake_hand": _执行握手动作,
    "nod": _执行姿态控制动作,
    "wave": _执行姿态控制动作,
    "dance": _执行姿态控制动作, # 跳舞（TODO: 暂时用姿态控制代替）
    "two_leg_once": _执行双腿站立动作_一次性,
    "two_leg_stand": _执行双腿站立动作,
    "cancel_two_leg_stand": _执行退出双腿站立动作,
    "exit_lie_down": _执行退出趴下动作,
    "exit_stand_up": _执行退出站立动作,
    "exit_stop": _执行退出停止动作,
    "move": None,  # move动作需要特殊处理，带参数
}

EXIT_COMMANDS = {"exit_lie_down", "exit_stand_up", "exit_stop"}

def _解析退出命令(config: dict) -> str:
    behavior = (
        config.get("actions", {})
        .get("exit_behavior", "lie_down")
    )
    if behavior == "stand_up":
        return "exit_stand_up"
    if behavior == "stop":
        return "exit_stop"
    return "exit_lie_down"

# 执行用户选择的动作
def _执行选择的动作(app, choice: str, params: dict = None) -> bool:
    # 特殊处理move动作
    if choice == "move":
        if params:
            _执行move动作(app, params)
        else:
            logger.warning("move动作需要参数（vx, vy, yaw_rate, duration）")
        return False
    
    handler = ACTION_HANDLERS.get(choice)
    if not handler:
        logger.warning("无效的选择。请重试。")
        return False
    handler(app)
    return choice in EXIT_COMMANDS

# 命令循环
def _循环处理用户输入(app, config: dict) -> None:
    while True:
        raw = input().strip() # 从标准输入读取用户输入
        if not raw:
            continue
        # 含参数的控制指令或move动作
        if raw.startswith("{"):
            try:
                payload = json.loads(raw)
                # 检查是否是move动作
                if payload.get("action") == "move":
                    params = payload.get("parameters", {})
                    _执行move动作(app, params)
                else:
                    # 普通控制指令
                    _处理控制指令(app, payload)
                continue
            except Exception as e:
                logger.error(f"解析命令失败: {e}")
                continue
        if raw == "exit":
            raw = _解析退出命令(config)
        if _执行选择的动作(app, raw):
            break


def main():
    try:
        # 初始化配置
        config_store = Config.instance()
        config = config_store.get()
        logging_cfg = config.get("logging", {})
        configure_logger(
            app_name=APP_NAME,
            log_dir=logging_cfg.get("log_dir"),
            level=logging_cfg.get("level", "INFO"),
            max_file_size_mb=logging_cfg.get("max_file_size_mb"),
            log_file_prefix="executor",
        )

        app = sdk.HighLevel()
        sdk_cfg = config.get("sdk", {})
        robot_ip = sdk_cfg.get("robot_ip", "127.0.0.1")
        local_port = int(sdk_cfg.get("local_port", 43988) or 43988)
        app.initRobot(robot_ip, local_port, "127.0.0.1")
        logger.info("机器人连接初始化成功。")

        robot_uuid = config.get("robot", {}).get("uuid", "unknown")
        ipc_path = 获取IPC路径(ORG_NAME, APP_NAME)

        # 启动一个线程，循环发送机器人状态到IPC路径
        threading.Thread(target=_循环发送机器人状态, args=(app, robot_uuid, ipc_path), daemon=True).start()

        _启动机器人(app)
        _循环处理用户输入(app, config)

    except Exception as e:
        logger.error(f"发生意外错误: {e}", exc_info=True)


if __name__ == "__main__":
    main()
