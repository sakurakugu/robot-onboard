#!/bin/bash

# Robot Server 启动脚本
# 功能：启动机器狗配置服务器
#
# 使用方法：
# cd ~/sparkrobot/robot-server/scripts/ # 进入目录
# chmod +x start.sh                     # 赋予启动脚本执行权限
# sudo ./start.sh                       # 运行启动脚本

set -e

# 切换到该软件所在目录（脚本的父目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
cd "$APP_DIR"

# 定义路径
WORKSPACE_DIR="$HOME/sparkrobot"
PID_DIR="$WORKSPACE_DIR/logs/pid"
LOG_DIR="$WORKSPACE_DIR/logs/robot-server"

# 创建目录
mkdir -p "$PID_DIR"
mkdir -p "$LOG_DIR"

# 定义进程名称
PROCESS_NAME="robot-server"

# 检查是否已运行
PID_FILE="$PID_DIR/robot-server.pid"
SCRIPT_NAME="server.py"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID -o args= 2>/dev/null | grep -q "$SCRIPT_NAME"; then
        echo "Robot Server 已在运行 (PID: $PID)"
        exit 1
    else
        echo "清理陈旧的 PID 文件。"
        rm -f "$PID_FILE"
    fi
fi

# 防止 PID 文件丢失但进程仍在跑的情况
EXISTING_PID=$(pgrep -f "$SCRIPT_NAME" 2>/dev/null || true)
if [ -n "$EXISTING_PID" ]; then
    echo "发现已运行的 Robot Server 进程 (PID: $EXISTING_PID)"
    echo "请先停止该进程，或使用 stop.sh 脚本"
    exit 1
fi

echo "正在启动 Robot Server..."
echo "配置文件位置: $WORKSPACE_DIR/config/config.toml"
echo "日志文件位置: $LOG_DIR"

# 运行Python服务器
exec -a "$PROCESS_NAME" python3 main.py &
echo $! > "$PID_FILE"

echo "Robot Server 启动成功 (PID: $(cat $PID_FILE))"
echo "访问 http://0.0.0.0:8080 进行配置"