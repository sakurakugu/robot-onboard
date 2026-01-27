# 机器狗客户端

## 功能特性

- ✅ 配置管理：分离配置存储
  - 全局配置（UUID等）：`~/sparkrobot/config/config.toml`
  - 机器人对话配置：`~/sparkrobot/config/robot-chat.toml`
- ✅ WebSocket 通信：与服务端实时通信
- ✅ 心跳保持：自动发送心跳包保持连接
- ✅ 客户端注册：连接时自动注册到服务器
- ✅ 接收音频：接收服务端语音回复并在音箱播放
- ✅ 语音对话：麦克风采集 → Opus压缩 → 服务端ASR → 大模型
- ✅ 执行动作：接收并执行服务端发送的动作指令
- ✅ 日志记录：在 `~/sparkrobot/robot-chat/logs/` 中记录运行日志
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

**机器人对话配置** (`~/sparkrobot/config/robot-chat.toml`)：
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
./start_daemon.sh

# 停止
./stop.sh

# 查看日志
tail -f ~/robot-chat/logs/client_output.log
```

## 部署流程

### 自动部署（推荐）

通过服务端前端界面添加机器狗时：

1. 填写机器狗信息和 IP 地址
2. 点击"添加"
3. 服务端会自动：
   - 通过 SSH 连接到机器狗
   - 创建 `~/sparkrobot/robot-chat` 目录（存放代码）
   - 创建 `~/sparkrobot/config` 目录（存放配置）
   - 复制客户端代码
   - 检测或生成 UUID 到 `config.toml`

### 手动部署

```bash
# 1. 复制客户端代码到机器狗
scp -r client/* firefly@<机器狗IP>:~/sparkrobot/robot-chat/

# 2. 登录机器狗
ssh firefly@<机器狗IP>

# 3. 安装依赖
cd ~/sparkrobot/robot-chat
./install.sh

# 4. 修改配置
vi ~/sparkrobot/config/robot-chat.toml
# 修改 server.business_url / server.control_url / server.audio_*_url 为服务器地址（或设置 server.base_url）

# 5. 启动客户端
./start_daemon.sh
```

## 集成到你的项目

### 基本使用

```python
import asyncio
from robot_client import RobotClient

async def main():
    # 创建客户端
    client = RobotClient()
    
    # 设置动作执行器
    async def action_executor(action: str, parameters: dict) -> bool:
        """执行动作的函数"""
        print(f"执行动作: {action}, 参数: {parameters}")
        # 调用机器狗 SDK
        # robot.execute(action, parameters)
        return True
    
    client.set_action_executor(action_executor)
    
    # 运行客户端
    await client.run()

if __name__ == '__main__':
    asyncio.run(main())
```

### 集成示例

参考 [robot_client_integrated.py](robot_client_integrated.py) 了解如何集成机器狗 SDK。

## 目录结构

```
~/sparkrobot/
├── config/                  # 配置目录（所有应用共享）
│   ├── config.toml         # 全局配置（UUID等）
│   └── robot-chat.toml     # 机器人对话专用配置
└── robot-chat/             # 客户端代码目录
    ├── README.md           # 说明文档
    ├── src/                # 源代码
    │   ├── robot_client.py
    │   ├── robot_client_integrated.py
    │   └── requirements.txt
    ├── scripts/            # 脚本
    │   ├── install.sh
    │   ├── start.sh
    │   ├── start_daemon.sh
    │   └── stop.sh
    └── logs/               # 日志目录
        ├── robot_client_20260114.log
        ├── client_output.log
        └── audio_*.opus
```

## 消息格式

### 客户端发送

#### 客户端注册
```json
{
  "type": "client_register",
  "robotId": "uuid",
  "timestamp": 1234567890,
  "data": {
    "name": "机器狗1",
    "model": "unitree-go2",
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

### 使用 systemd（推荐）

创建服务文件 `/etc/systemd/system/robot-client.service`：

```ini
[Unit]
Description=Robot Dog Client
After=network.target

[Service]
Type=simple
User=firefly
WorkingDirectory=/home/firefly/sparkrobot/robot-chat
ExecStart=/usr/bin/python3 /home/firefly/sparkrobot/robot-chat/src/robot_client.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable robot-client
sudo systemctl start robot-client

# 查看状态
sudo systemctl status robot-client

# 查看日志
sudo journalctl -u robot-client -f
```

### 使用 crontab

```bash
crontab -e
```

添加：

```
@reboot cd /home/firefly/sparkrobot/robot-chat && ./start_daemon.sh
```

## 故障排查

### 无法连接到服务器

1. 检查服务器地址是否正确（`~/sparkrobot/config/robot-chat.toml`）
2. 检查网络连接
3. 检查防火墙设置
4. 查看日志：`tail -f ~/sparkrobot/robot-chat/logs/robot_client_*.log`

### 动作未执行

1. 检查是否设置了动作执行器
2. 查看日志中的动作信息
3. 确认机器狗 SDK 正常工作

### 客户端频繁重连

1. 检查网络稳定性
2. 调整心跳间隔（`~/sparkrobot/config/robot-chat.toml`）
3. 检查服务器负载

## 注意事项

1. 确保服务端已启动且 WebSocket 地址正确
2. 首次运行会生成新的 UUID 在 `~/sparkrobot/config/config.toml`，之后会一直使用该 UUID
3. UUID 在所有 Spark Robot 应用中共享
4. 动作执行器需要根据实际的机器狗 SDK 进行实现
5. 音频播放功能需要额外实现（目前仅保存音频文件）
6. 建议在生产环境使用后台运行模式

## 配置文件说明

### 全局配置 (config.toml)
- `uuid`: 机器人的唯一标识符，所有应用共享
- 由系统自动生成和管理

### Robot-Chat 专用配置 (robot-chat.toml)
- `robot.name`: 机器人名称
- `robot.model`: 机器人型号
- `server.business_url`: 业务通道 WebSocket 地址（9001）
- `server.control_url`: 控制通道 WebSocket 地址（9000）
- `server.audio_upload_url`: 音频上传通道 WebSocket 地址（9002）
- `server.audio_download_url`: 音频下载通道 WebSocket 地址（9003）
- `server.reconnect_interval`: 重连间隔（秒）
- `server.heartbeat_interval`: 心跳间隔（秒）
- `audio.*`: 音频相关配置
- `logging.*`: 日志相关配置

## License

MIT
