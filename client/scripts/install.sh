#!/bin/bash
# 机器狗客户端安装脚本
# 在机器狗上运行此脚本以安装依赖

set -e

echo "========================================"
echo "  机器狗客户端安装脚本"
echo "========================================"
echo ""

# 检查 Python 版本
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 Python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "✓ 找到 Python: $PYTHON_VERSION"

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    echo "正在安装 pip..."
    curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    python3 /tmp/get-pip.py --user
    rm /tmp/get-pip.py
fi

echo "✓ 找到 pip"

# 安装依赖
echo ""
echo "正在安装依赖..."
pip3 install --user -r ../src/requirements.txt

echo ""
echo "========================================"
echo "  安装完成！"
echo "========================================"
echo ""
echo "运行客户端:"
echo "  python3 robot_client.py"
echo ""
echo "配置文件位置:"
echo "  ~/sparkrobot/config/config.toml和robot-chat.toml"
echo ""
echo "日志位置:"
echo "  ~/sparkrobot/logs/robot-chat/"
echo ""
