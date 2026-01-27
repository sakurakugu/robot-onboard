#!/bin/bash
# 启动机器狗客户端
# 可以设置为开机自启动

cd "$(dirname "$0")"
cd ../src

# 定义路径
WORKSPACE_DIR="$HOME/sparkrobot"
PID_DIR="$WORKSPACE_DIR/logs/pid"

# 创建目录
mkdir -p "$PID_DIR"

# 检查是否已运行
PID_FILE="$PID_DIR/robot-chat.pid"
SCRIPT_NAME="main.py"
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID -o args= | grep -q "$SCRIPT_NAME"; then
        echo "客户端已在运行 (PID: $PID)"
        exit 1
    else
        echo "清理陈旧的 PID 文件。"
        rm -f "$PID_FILE"
    fi
fi

# 防止 PID 文件丢失但进程仍在跑的情况
EXISTING_PID=$(pgrep -f "$SCRIPT_NAME")
if [ -n "$EXISTING_PID" ] && [ "$EXISTING_PID" != "$$" ]; then
    echo "检测到已有同名进程运行中 (PID: $EXISTING_PID)，请先停止它。"
    exit 1
fi

echo "正在启动机器狗客户端..."
python3 main.py
