#!/bin/bash
# 后台运行机器狗客户端

cd "$(dirname "$0")"

# 创建日志目录
mkdir -p ~/robot-chat/logs

# 检查是否已运行
if [ -f ~/robot-chat/client.pid ]; then
    PID=$(cat ~/robot-chat/client.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "客户端已在运行 (PID: $PID)"
        exit 0
    fi
fi

# 后台运行
nohup python3 robot_client.py > ~/robot-chat/logs/client_output.log 2>&1 &
PID=$!

# 保存 PID
echo $PID > ~/robot-chat/client.pid

echo "客户端已启动 (PID: $PID)"
echo "日志文件: ~/robot-chat/logs/client_output.log"
