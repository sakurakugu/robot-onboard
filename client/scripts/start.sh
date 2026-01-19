#!/bin/bash
# 启动机器狗客户端
# 可以设置为开机自启动

cd "$(dirname "$0")"

echo "启动机器狗客户端..."
python3 robot_client.py
