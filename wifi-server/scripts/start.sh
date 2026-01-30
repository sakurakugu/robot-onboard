#!/bin/bash

# 使用方法：
# cd ~/sparkrobot/robot-server/scripts/ # 进入目录
# chmod +x start.sh                     # 赋予启动脚本执行权限
# sudo ./start.sh                       # 运行启动脚本

# 切换到该软件所在目录（脚本的父目录）
cd $(dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)")

# 运行Python服务器
python3 server.py