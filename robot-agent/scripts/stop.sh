#!/bin/bash

# Robot Agent 停止脚本

set -e

# 颜色定义
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 定义路径
PROCESS_NAME="robot-agent"
WORKSPACE_DIR="$HOME/sparkrobot"
PID_DIR="$WORKSPACE_DIR/logs/pid"
PID_FILE="$PID_DIR/${PROCESS_NAME}.pid"
SCRIPT_NAME="main.py"

# 检查 systemd 服务是否在运行
SERVICE_NAME="${PROCESS_NAME}.service"
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "${BLUE}检测到 $SERVICE_NAME 正在运行，请先停止它: sudo systemctl stop $SERVICE_NAME${NC}"
    exit 1
fi

# 检查 PID 文件
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" -o comm= | grep -qx "$PROCESS_NAME"; then
        echo -e "${BLUE}正在停止 $PROCESS_NAME (PID: $PID)...${NC}"
        kill $PID
        rm -f "$PID_FILE"
        echo -e "${BLUE}$PROCESS_NAME 已停止${NC}"
        exit 0
    else
        echo -e "${BLUE}进程的 PID 文件已不存在，清理 PID 文件${NC}"
        rm -f "$PID_FILE"
    fi
fi

# 尝试通过进程名查找
EXISTING_PID=$(pgrep -f "$PROCESS_NAME" 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    echo -e "${BLUE}正在停止 $PROCESS_NAME (PID: $EXISTING_PID)...${NC}"
    kill $EXISTING_PID
    echo -e "${BLUE}$PROCESS_NAME 已停止${NC}"
else
    echo -e "${BLUE}$PROCESS_NAME 未运行${NC}"
fi
