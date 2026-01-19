#!/bin/bash
# 停止机器狗客户端

if [ ! -f ~/robot-chat/client.pid ]; then
    echo "未找到 PID 文件"
    exit 1
fi

PID=$(cat ~/robot-chat/client.pid)

if ps -p $PID > /dev/null 2>&1; then
    kill $PID
    echo "已停止客户端 (PID: $PID)"
    rm ~/robot-chat/client.pid
else
    echo "进程不存在 (PID: $PID)"
    rm ~/robot-chat/client.pid
fi
