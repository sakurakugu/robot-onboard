#!/bin/bash

# Robot Runtime 启动脚本

set -e

BLUE='\033[0;34m'
NC='\033[0m'

PROCESS_NAME="sparkrobot-runtime"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
cd "$APP_DIR"

SERVICE_NAME="${PROCESS_NAME}.service"
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "${BLUE}检测到 $SERVICE_NAME 正在运行，请先停止它: sudo systemctl stop $SERVICE_NAME${NC}"
    exit 1
fi

WORKSPACE_DIR="$HOME/sparkrobot"
PID_DIR="$WORKSPACE_DIR/logs/pid"
LOG_DIR="$WORKSPACE_DIR/logs/${PROCESS_NAME}"
PID_FILE="$PID_DIR/${PROCESS_NAME}.pid"
SCRIPT_NAME="main.py"

mkdir -p "$PID_DIR"
mkdir -p "$LOG_DIR"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID -o args= 2>/dev/null | grep -q "$SCRIPT_NAME"; then
        echo -e "${BLUE}${PROCESS_NAME} 已在运行 (PID: $PID)${NC}"
        exit 1
    else
        echo -e "${BLUE}清理陈旧的 PID 文件。${NC}"
        rm -f "$PID_FILE"
    fi
fi

EXISTING_PID=$(pgrep -f "sparkrobot-runtime.*${SCRIPT_NAME}" 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    echo -e "${BLUE}发现已运行的 ${PROCESS_NAME} 进程 (PID: $EXISTING_PID)${NC}"
    echo -e "${BLUE}请先停止该进程，或使用 stop.sh 脚本${NC}"
    exit 1
fi

echo -e "${BLUE}正在启动 ${PROCESS_NAME}...${NC}"
echo -e "${BLUE}日志文件位置: $LOG_DIR${NC}"

exec -a "$PROCESS_NAME" python3 ./main.py &
echo $! > "$PID_FILE"

echo -e "${BLUE}${PROCESS_NAME} 启动成功 (PID: $(cat $PID_FILE))${NC}"
