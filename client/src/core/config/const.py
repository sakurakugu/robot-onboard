from pathlib import Path

ORG_NAME = "sparkrobot"  # 公司组织名
APP_NAME = "robot-agent" # 这是放置在机器狗身上的代理，用于通过SDK控制机器人，并连接到服务器和APP，因此叫 “机器人-代理”
WORKSPACE_DIR = Path.home() / ORG_NAME

SERVER_ADDR = "192.168.0.108"      # 服务器地址
CONTROLLER_ADDR = "192.168.0.108"  # 手机App地址


__all__ = [
    "ORG_NAME",
    "APP_NAME",
    "WORKSPACE_DIR",
    "SERVER_ADDR",
    "CONTROLLER_ADDR"
]
