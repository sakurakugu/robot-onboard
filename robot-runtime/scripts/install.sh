#!/bin/bash

# 使用方法：
# cd ~/sparkrobot/robot-runtime/scripts/ # 进入目录
# chmod +x install.sh                   # 赋予安装脚本执行权限
# sudo ./install.sh                     # 运行一键安装脚本

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
  echo -e "${RED}错误: 请使用 sudo 运行此脚本${NC}"
  echo "示例: sudo ./install.sh"
  exit 1
fi

PROCESS_NAME="sparkrobot-runtime"
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BASE_DIR=$(dirname "$SCRIPT_DIR")
SERVICE_NAME="${PROCESS_NAME}.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"

echo -e "${GREEN}正在安装机器狗本体运行时 Robot Runtime...${NC}"
echo -e "${BLUE}工作目录: $BASE_DIR${NC}"

echo -e "${BLUE}正在设置文件权限...${NC}"
chmod +x "$SCRIPT_DIR/start.sh"
chmod +x "$SCRIPT_DIR/stop.sh"
chmod +x "$BASE_DIR/main.py"

echo -e "${BLUE}正在生成服务配置文件 $SERVICE_FILE ...${NC}"
cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=机器人本体运行时
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

echo -e "${BLUE}正在启动服务...${NC}"
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

echo -e "${BLUE}正在检查服务状态...${NC}"
sleep 2
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}安装成功！服务正在运行。${NC}"
    echo -e "${BLUE}服务名称: $SERVICE_NAME${NC}"
    echo -e "${BLUE}查看日志: sudo journalctl -u $SERVICE_NAME -f${NC}"
    echo -e "${BLUE}停止服务: sudo systemctl stop $SERVICE_NAME${NC}"
    systemctl status $SERVICE_NAME --no-pager | head -n 10
else
    echo -e "${RED}服务启动失败，请检查日志。${NC}"
    systemctl status $SERVICE_NAME --no-pager
    exit 1
fi
