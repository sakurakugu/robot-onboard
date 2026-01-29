# 机器狗客户端

## 结构

core/ 底层 ， core之间可以相互调用，但是无法直接调用 modules/ 中的功能模块
modules / 功能模块，依赖 core/ ，modules之间可以相互调用
main.py 主入口
application.py 应用入口

## 功能特性

- ✅ 配置管理：分离配置存储
  - 全局配置（UUID等）：`~/sparkrobot/config/config.toml`
  - 机器人对话配置：`~/sparkrobot/config/robot-agent.toml`
- ✅ WebSocket 通信：与服务端实时通信
- ✅ 心跳保持：自动发送心跳包保持连接
- ✅ 客户端注册：连接时自动注册到服务器
- ✅ 接收音频：接收服务端语音回复并在音箱播放
- ✅ 语音对话：麦克风采集 → Opus压缩 → 服务端ASR → 大模型
- ✅ 执行动作：接收并执行服务端发送的动作指令
- ✅ 日志记录：在 `~/sparkrobot/logs/robot-agent/` 中记录运行日志
- ✅ 自动重连：断线后自动重连
- ✅ 后台运行：支持以守护进程方式运行

## 快速开始

### 1. 安装依赖

```bash
# 在机器狗上运行
./install.sh
```

### 2. 配置

首次运行时会自动创建配置文件：

**全局配置** (`~/sparkrobot/config/config.toml`)：
```toml
# 全局配置 - 所有应用共享
uuid = "自动生成的UUIDv7"
```

**机器人对话配置** (`~/sparkrobot/config/robot-agent.toml`)：
```toml
[robot]
name = "robot-dog-1"
model = "unitree-go2"

[server]
base_url = "ws://localhost"
ws_path = "/api/v1/conversation/connect"
control_url = "ws://localhost:9000/api/v1/conversation/connect"
business_url = "ws://localhost:9001/api/v1/conversation/connect"
audio_upload_url = "ws://localhost:9002/api/v1/conversation/connect"
audio_download_url = "ws://localhost:9003/api/v1/conversation/connect"
reconnect_interval = 5
heartbeat_interval = 30

[audio]
sample_rate = 16000
channels = 1
frame_duration_ms = 20
vad_threshold = 0.015
vad_silence_ms = 800
max_segment_ms = 10000
enable_streaming = true
input_device = ""

[logging]
level = "INFO"
max_file_size_mb = 10
```

修改 `server.business_url` / `server.control_url` / `server.audio_*_url` 为实际的服务器地址（或设置 `server.base_url`）。

### 3. 运行

#### 前台运行（调试用）

```bash
./start.sh
# 或者
python3 robot_client.py
```

#### 后台运行（生产环境）

```bash
# 启动
./start_后台.sh

# 停止
./stop.sh

# 查看日志
tail -f ~/sparkrobot/logs/robot-agent/robot-agent_$(date +%Y%m%d).log
```

## 部署流程

### 自动部署（推荐）

通过服务端前端界面添加机器狗时：

1. 填写机器狗信息和 IP 地址
2. 点击"添加"
3. 服务端会自动：
   - 通过 SSH 连接到机器狗
   - 创建 `~/sparkrobot/robot-agent` 目录（存放代码）
   - 创建 `~/sparkrobot/config` 目录（存放配置）
   - 复制客户端代码
   - 检测或生成 UUID 到 `config.toml`

### 手动部署

```bash
# 1. 复制客户端代码到机器狗
scp -r client/* firefly@<机器狗IP>:~/sparkrobot/robot-agent/

# 2. 登录机器狗
ssh firefly@<机器狗IP>

# 3. 安装依赖
cd ~/sparkrobot/robot-agent
./install.sh

# 4. 修改配置
vim ~/sparkrobot/config/robot-agent.toml
# 修改 server.business_url / server.control_url / server.audio_*_url 为服务器地址（或设置 server.base_url）

# 5. 启动客户端
./start_daemon.sh
```

## 目录结构

```
~/sparkrobot/
├── config/                  # 配置目录（所有应用共享）
│   ├── config.toml          # 全局配置（UUID等）
│   └── robot-agent.toml     # 机器人对话专用配置
├── robot-agent/             # 客户端代码目录
│   ├── pyproject.toml
│   ├── README.md
│   ├── requirements.txt
│   ├── scripts
│   │   ├── install.sh
│   │   ├── start_后台.sh
│   │   ├── start.sh
│   │   └── stop.sh
│   └── src
│       ├── application.py
│       ├── core
│       │   ├── config
│       │   │   ├── config.py
│       │   │   ├── const.py
│       │   │   └── __init__.py
│       │   ├── dog
│       │   │   ├── lib      # 智元官方的sdk库   
│       │   │   └── sdk.py
│       │   ├── __init__.py
│       │   ├── logger
│       │   │   └── __init__.py
│       │   └── utils
│       │       └── __init__.py
│       ├── main.py
│       └── modules
│           ├── actions
│           │   ├── executor.py
│           │   ├── __init__.py
│           │   └── mapping.py
│           ├── audio
│           │   ├── capture.py
│           │   ├── __init__.py
│           │   └── playback.py
│           ├── control
│           │   ├── ipc.py
│           │   └── process.py
│           ├── group_control
│           │   ├── crazy.py
│           │   └── dog_core.py
│           ├── __init__.py
│           └── transport
│               ├── __init__.py
│               ├── protocol.py
│               └── ws_manager.py
├── logs/                    # 日志目录
│   ├── robot-agent_20260114.log
│   └── client_output.log
└── cache/                   # 缓存目录
    └── media/               # 媒体缓存目录
        └── tts/             # 文本转语音缓存目录
```

// TODO: 修改以下内容
## 消息格式

### 客户端发送

#### 客户端注册
```json
{
  "type": "robot_register",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "name": "机器狗-{{uuid前四位}}",
    "model": "agibot-d1",
    "version": "1.0.0",
    "metadata": {}
  }
}
```

#### 文本输入
```json
{
  "type": "text_input",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "text": "你好"
  }
}
```

#### 音频输入（会话开始）
```json
{
  "type": "audio_start",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "format": "opus",
    "sampleRate": 16000,
    "channels": 1,
    "frameDurationMs": 20,
    "sessionId": "uuid"
  }
}
```

#### 音频输入（数据块）
```json
{
  "type": "audio_chunk",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "format": "opus",
    "sampleRate": 16000,
    "channels": 1,
    "frameDurationMs": 20,
    "sessionId": "uuid",
    "seq": 12,
    "buffer": "base64..."
  }
}
```

#### 音频输入（会话结束）
```json
{
  "type": "audio_end",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "sessionId": "uuid",
    "reason": "silence"
  }
}
```

#### 心跳包
```json
{
  "type": "heartbeat",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {}
}
```

#### 状态更新
```json
{
  "type": "status",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "battery": 85,
    "temperature": 45,
    "position": "standing"
  }
}
```

### 服务端发送

#### 文本响应
```json
{
  "type": "text_response",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "text": "你好！"
  }
}
```

#### 音频响应
```json
{
  "type": "audio_response",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "format": "opus",
    "buffer": "base64编码的音频数据",
    "duration": 3.5
  }
}
```

#### 动作指令
```json
{
  "type": "action_command",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "action": "stand_up",
    "parameters": {},
    "safetyChecked": true
  }
}
```

#### 错误消息
```json
{
  "type": "error",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "code": "ERROR_CODE",
    "message": "错误描述"
  }
}
```

## 开机自启动

### 使用 systemd

创建服务文件 `/etc/systemd/system/robot-agent.service`：

```ini
[Unit]
Description=Robot Dog Agent
After=network.target

[Service]
Type=simple
User=firefly
WorkingDirectory=/home/firefly/sparkrobot/robot-agent
ExecStart=/usr/bin/python3 /home/firefly/sparkrobot/robot-agent/src/robot_agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable robot-agent
sudo systemctl start robot-agent

# 查看状态
sudo systemctl status robot-agent

# 查看日志
sudo journalctl -u robot-agent -f
```

## 故障排查
