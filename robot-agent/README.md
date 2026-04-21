# robot-agent - 机器狗客户端

机器狗端核心客户端程序，负责与云端服务通信、音频处理、动作执行等功能。

## 功能特性

- **配置管理**: 分离配置存储，支持热更新
- **WebSocket 通信**: 多通道实时通信
- **心跳保持**: 自动发送心跳包保持连接
- **客户端注册**: 连接时自动注册到服务器
- **音频采集**: 麦克风采集 → Opus 压缩 → 服务端 ASR
- **音频播放**: 接收服务端语音回复并在音箱播放
- **动作执行**: 接收并执行服务端发送的动作指令
- **运行时桥接**: 将导航、建图、巡逻命令转发给 `robot-runtime`
- **状态汇聚上报**: 订阅 `robot-runtime` 摘要状态并转发到云端
- **视觉识别**: 支持摄像头拍照和视觉分析
- **日志记录**: 完整的运行日志
- **自动重连**: 断线后自动重连
- **后台运行**: 支持守护进程方式运行

## 目录结构

```
robot-agent/
├── src/
│   ├── core/                    # 核心层
│   │   ├── config/              # 配置管理
│   │   │   └── __init__.py
│   │   ├── dog/                 # 机器狗 SDK
│   │   │   ├── lib/             # SDK 动态库
│   │   │   │   ├── zsl-1/       # ZSL-1 型号
│   │   │   │   ├── zsl-1w/      # ZSL-1W 型号
│   │   │   │   └── zsm-1w/      # ZSM-1W 型号
│   │   │   └── sdk.py           # SDK 封装
│   │   ├── __init__.py
│   │   └── auth_client.py       # 认证客户端
│   ├── modules/                 # 功能模块
│   │   ├── actions/             # 动作执行
│   │   │   ├── executor.py      # 动作执行器
│   │   │   └── mapping.py       # 动作映射
│   │   ├── audio/               # 音频处理
│   │   │   ├── capture.py       # 音频采集
│   │   │   └── playback.py      # 音频播放
│   │   ├── control/             # 控制模块
│   │   │   ├── ipc.py           # IPC 通信
│   │   │   ├── joystick.py      # 摇杆控制
│   │   │   └── process.py       # 进程控制
│   │   ├── runtime/             # 本地运行时桥接
│   │   │   ├── coordinator.py   # 客户端运行时协调器
│   │   │   └── runtime_client.py# robot-runtime IPC 客户端包装
│   │   ├── transport/           # 通信模块
│   │   │   ├── protocol.py      # 协议定义
│   │   │   └── ws_manager.py    # WebSocket 管理
│   │   └── vision/              # 视觉模块
│   │       └── camera.py        # 摄像头
│   ├── __init__.py
│   ├── application.py           # 应用主类
│   └── main.py                  # 入口文件
├── scripts/
│   ├── install.sh               # 安装脚本
│   ├── start.sh                 # 启动脚本
│   └── stop.sh                  # 停止脚本
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 架构设计

### 分层架构

```
┌─────────────────────────────────────────┐
│              main.py                    │
│            (程序入口)                    │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│           application.py                │
│           (应用主类)                     │
│  - 初始化各模块                          │
│  - 管理连接生命周期                      │
│  - 消息路由分发                          │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
┌───▼───┐    ┌────▼────┐     ┌───▼───┐
│ core/ │    │ modules │     │       │
│ 核心层 │    │ 功能模块│     │       │
└───────┘    └─────────┘     └───────┘
```

### 核心层 (core/)

底层功能，core 之间可以相互调用，但无法直接调用 modules 中的功能模块。

| 模块        | 功能                 |
| ----------- | -------------------- |
| config      | 配置管理，支持热更新 |
| dog/sdk     | 机器狗 SDK 封装      |
| auth_client | 认证客户端           |

### 功能模块 (modules/)

依赖 core，modules 之间可以相互调用。

| 模块      | 功能                         |
| --------- | ---------------------------- |
| actions   | 动作执行，解析和执行动作指令 |
| audio     | 音频采集和播放               |
| control   | IPC 通信、摇杆控制、进程控制 |
| runtime   | 与 `robot-runtime` 交互、转发导航与建图命令 |
| transport | WebSocket 通信管理           |
| vision    | 摄像头和视觉识别             |

## 安装部署

### 系统依赖

```bash
sudo apt update
sudo apt install -y portaudio19-dev libportaudio2
```

### 安装

```bash
# 在机器狗上运行
cd robot-agent
./scripts/install.sh
```

### 配置文件

首次运行时自动创建配置文件：

**配置** (`~/sparkrobot/config/config.toml`):

```toml
[robot]
name = "robot-dog-1"
model = "unitree-go2"
uuid = "自动生成的UUIDv7"
version = "0.0.0"  # 自动检测

[cloud]
enabled = true
server_url = "ws://localhost:9000"
business_url = "/api/v1/robot/business"
audio_upload_url = "/api/v1/robot/audio/upload"
audio_download_url = "/api/v1/robot/audio/download"
reconnect_interval = 5
heartbeat_interval = 30

[studio]
enabled = false
server_url = "ws://192.168.5.8:9010"
business_url = "/api/v1/web/business"
reconnect_interval = 5
heartbeat_interval = 15

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

### 运行

**前台运行（调试用）**:

```bash
./scripts/start.sh # 启动
./scripts/stop.sh  # 停止
```

**后台运行（生产环境）**:

```bash
# 启动
systemctl start sparkrobot-agent
# 停止（二选一）
./scripts/stop.sh
systemctl stop sparkrobot-agent

# 查看日志
tail -f ~/sparkrobot/logs/robot-agent/robot-agent_$(date +%Y%m%d).log
```

## WebSocket 通信

### 通道说明

| 通道           | 用途     | 消息类型             |
| -------------- | -------- | -------------------- |
| business       | 业务消息 | 注册、文本、动作指令 |
| control        | 控制消息 | 心跳、状态、摇杆数据 |
| audio_upload   | 音频上传 | 语音输入流           |
| audio_download | 音频下载 | 语音回复流           |

### 消息格式

#### 客户端发送

**注册消息**:

```json
{
  "type": "robot_register",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "name": "机器狗-{{uuid前四位}}",
    "model": "agibot-d1",
    "version": "0.0.0",
    "metadata": {}
  }
}
```

**心跳消息**:

```json
{
  "type": "heartbeat",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {}
}
```

**音频开始**:

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

**音频数据块**:

```json
{
  "type": "audio_chunk",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "sessionId": "uuid",
    "seq": 12,
    "buffer": "base64..."
  }
}
```

**音频结束**:

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

#### 服务端发送

**文本响应**:

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

**动作指令**:

```json
{
  "type": "action_command",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "action": "stand_up",
    "parameters": {}
  }
}
```

**导航命令**:

```json
{
  "type": "navigation_command",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "requestId": "req-1",
    "command": "navigate_to",
    "goal": {
      "x": 1.2,
      "y": 0.5,
      "yaw": 1.57,
      "frameId": "map",
      "mapName": "office-1"
    }
  }
}
```

**建图命令**:

```json
{
  "type": "map_command",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "requestId": "req-2",
    "command": "start_mapping",
    "mapName": "office-1"
  }
}
```

**音频响应**:

```json
{
  "type": "audio_response",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "format": "opus",
    "buffer": "base64..."
  }
}
```

## 动作系统

### 动作格式

动作通过特定格式的文本触发：

```
{{action=动作名,参数1=值1,参数2=值2}}
```

示例：

```
{{action=forward,vx=0.2,vy=0,yaw_rate=0}}
{{action=stand_up}}
{{action=sit_down}}
```

### 支持的动作

| 动作名     | 参数             | 描述 |
| ---------- | ---------------- | ---- |
| stand_up   | -                | 站立 |
| sit_down   | -                | 趴下 |
| forward    | vx, vy, yaw_rate | 前进 |
| backward   | -                | 后退 |
| turn_left  | -                | 左转 |
| turn_right | -                | 右转 |
| dance      | -                | 跳舞 |

### 动作执行流程

```
服务端动作指令
      │
      ▼
┌─────────────────┐
│  mapping.py     │
│  解析动作格式    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  executor.py    │
│  执行动作        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  sdk.py         │
│  调用底层 SDK    │
└─────────────────┘
```

## 音频处理

### 音频采集流程

```
麦克风采集
    │
    ▼
┌─────────────┐
│  PyAudio    │
│  16kHz 单声道│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  VAD 检测    │
│  语音活动检测 │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Opus 编码   │
│  20ms 帧     │
└──────┬──────┘
       │
       ▼
WebSocket 上传
```

### 音频播放流程

```
WebSocket 下载
       │
       ▼
┌─────────────┐
│  Opus 解码   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  PyAudio    │
│  播放输出    │
└─────────────┘
```

## SDK 模式

robot-agent 支持两种控制模式：

- **SDK 模式**: 通过 SDK 直接控制机器狗
- **遥控模式**: 通过外部遥控器控制

可通过服务端指令切换模式。

## 开机自启动

### 使用 systemd

创建服务文件 `/etc/systemd/system/sparkrobot-agent.service`:

```ini
[Unit]
Description=Robot Dog Agent
After=network.target

[Service]
Type=simple
User=firefly
WorkingDirectory=/home/firefly/sparkrobot/robot-agent
ExecStart=/usr/bin/python3 /home/firefly/sparkrobot/robot-agent/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable sparkrobot-agent
sudo systemctl start sparkrobot-agent

# 查看状态
sudo systemctl status sparkrobot-agent

# 查看日志
sudo journalctl -u sparkrobot-agent -f
```

## 故障排查

### 连接问题

1. 检查网络连接
2. 确认服务器地址配置正确
3. 查看日志中的错误信息

### 音频问题

1. 确认 `portaudio19-dev` 已安装
2. 检查麦克风和音箱设备
3. 查看音频配置参数

### 动作执行问题

1. 确认 SDK 模式已启用
2. 检查动作名称和参数
3. 查看 SDK 日志
