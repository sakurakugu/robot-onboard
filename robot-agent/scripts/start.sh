#!/bin/bash

# Robot Agent 启动脚本
# 功能：启动机器狗客户端
#
# 使用方法：
# cd ~/sparkrobot/robot-agent/scripts/ # 进入目录
# chmod +x start.sh                    # 赋予启动脚本执行权限
# sudo ./start.sh                      # 运行启动脚本

set -e

# 颜色定义
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 切换到该软件所在目录（脚本的父目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
cd "$APP_DIR"

# 定义进程名称
PROCESS_NAME="robot-agent"

# 检查 systemd 服务是否在运行
SERVICE_NAME="${PROCESS_NAME}.service"
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "${BLUE}检测到 $SERVICE_NAME 正在运行，请先停止它: sudo systemctl stop $SERVICE_NAME${NC}"
    exit 1
fi

# 定义路径
WORKSPACE_DIR="$HOME/sparkrobot"
PID_DIR="$WORKSPACE_DIR/logs/pid"
LOG_DIR="$WORKSPACE_DIR/logs/${PROCESS_NAME}"

# 创建目录
mkdir -p "$PID_DIR"
mkdir -p "$LOG_DIR"

# 检查是否已运行
PID_FILE="$PID_DIR/${PROCESS_NAME}.pid"
SCRIPT_NAME="main.py"

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

# 防止 PID 文件丢失但进程仍在跑的情况
# 使用完整路径避免误检测其他服务的 main.py
EXISTING_PID=$(pgrep -f "robot-agent.*${SCRIPT_NAME}" 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    echo -e "${BLUE}发现已运行的 ${PROCESS_NAME} 进程 (PID: $EXISTING_PID)${NC}"
    echo -e "${BLUE}请先停止该进程，或使用 stop.sh 脚本${NC}"
    exit 1
fi

echo -e "${BLUE}正在启动 ${PROCESS_NAME}...${NC}"
echo -e "${BLUE}配置文件位置: $WORKSPACE_DIR/config/config.toml${NC}"
echo -e "${BLUE}日志文件位置: $LOG_DIR${NC}"

# 运行Python客户端
exec -a "$PROCESS_NAME" python3 src/main.py &
echo $! > "$PID_FILE"

echo -e "${BLUE}${PROCESS_NAME} 启动成功 (PID: $(cat $PID_FILE))${NC}"
