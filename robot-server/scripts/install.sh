#!/bin/bash

# 使用方法：
# cd ~/sparkrobot/robot-server/scripts/ # 进入目录
# chmod +x install.sh                   # 赋予安装脚本执行权限
# sudo ./install.sh                     # 运行一键安装脚本

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 检查是否以 root 运行
if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}错误: 请使用 sudo 运行此脚本${NC}"
  echo "示例: sudo ./install.sh"
  exit 1
fi

# 定义进程名称
PROCESS_NAME="sparkrobot-server"

# 获取脚本所在目录的绝对路径
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BASE_DIR=$(dirname "$SCRIPT_DIR")
SERVICE_NAME="${PROCESS_NAME}.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"

echo -e "${GREEN}正在安装机器狗本体服务器 Robot Server...${NC}"
echo -e "${BLUE}工作目录: $BASE_DIR${NC}"

# 1. 赋予相关脚本执行权限
echo -e "${BLUE}正在设置文件权限...${NC}"
chmod +x "$SCRIPT_DIR/start.sh"
chmod +x "$BASE_DIR/main.py"

# 2. 生成 systemd 服务文件
# 使用当前路径动态生成，确保路径正确
echo -e "${BLUE}正在生成服务配置文件 $SERVICE_FILE ...${NC}"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=机器人配置服务器
After=network.target

[Service]
Type=simple
User=firefly
WorkingDirectory=$BASE_DIR
ExecStart=/usr/bin/python3 $BASE_DIR/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 3. 重新加载 systemd 并启动服务
echo -e "${BLUE}正在启动服务...${NC}"
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

# 4. 检查服务状态
echo -e "${BLUE}正在检查服务状态...${NC}"
sleep 2 # 等待服务启动
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}安装成功！服务正在运行。${NC}"
    echo -e "${BLUE}服务名称: $SERVICE_NAME${NC}"
    echo -e "${BLUE}查看日志: sudo journalctl -u $SERVICE_NAME -f${NC}"
    echo -e "${BLUE}停止服务: sudo systemctl stop $SERVICE_NAME${NC}"

    # 显示当前状态
    systemctl status $SERVICE_NAME --no-pager | head -n 10
else
    echo -e "${RED}服务启动失败，请检查日志。${NC}"
    systemctl status $SERVICE_NAME --no-pager
    exit 1
fi
