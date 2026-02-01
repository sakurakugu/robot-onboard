#!/bin/bash
# 机器狗客户端安装脚本
# 在机器狗上运行此脚本以安装依赖

set -e

cd "$(dirname "$0")"

WORKSPACE_DIR="$HOME/sparkrobot"
LOGS_DIR="$WORKSPACE_DIR/logs/robot-agent"
STDOUT_LOG="$LOGS_DIR/client_stdout_$(date +'%Y%m%d').log"

log() {
    # 获取 ISO 格式时间戳
    local timestamp
    timestamp=$(date '+%Y-%m-%dT%H:%M:%S%:z')
    timestamp=${timestamp//Z/+00:00}

    local msg="[$timestamp] $1"
    # echo 输出内容
    # | tee -a 追加到文件
    echo "$msg" | tee -a "$STDOUT_LOG"
}

log "========================================"
log "    机器狗客户端安装脚本"
log "========================================"
log ""

# 检查 Python 版本
if ! command -v python3 &> /dev/null; then
    log "错误: 未找到 Python3"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
log "✓ 找到 Python: $PYTHON_VERSION"

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    log "正在安装 pip..."
    curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    python3 /tmp/get-pip.py --user
    rm /tmp/get-pip.py
fi

log "✓ 找到 pip"

# 安装依赖
log ""
log "正在安装依赖..."
sudo apt-get update && sudo apt-get install -y portaudio19-dev
pip3 install --user -r ../requirements.txt

echo ""
echo "========================================"
log "  安装完成！"
echo "========================================"
echo ""
echo "运行程序: ./start.sh"
echo ""
echo "配置位置: ~/sparkrobot/config/config.toml和robot-agent.toml"
echo "日志位置: ~/sparkrobot/logs/robot-agent/"
echo ""
