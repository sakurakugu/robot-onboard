#!/bin/bash

# 启动WiFi设置服务器
echo "正在启动机器狗WiFi设置服务器..."
echo "服务器将运行在 http://0.0.0.0:8080"
echo "请在浏览器中访问 http://<机器狗IP>:8080 来设置WiFi"
echo ""

# 切换到脚本所在目录
cd "$(dirname "$0")"

# 运行Python服务器
python3 server.py