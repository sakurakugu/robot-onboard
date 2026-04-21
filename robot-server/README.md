# robot-server - 机器狗本地配置服务

机器狗端本地配置服务器，提供 HTTP API 和 mDNS 服务发现功能。

> 使用Python而不是Go或C++是为了快速开发和迭代，后续可以根据需要重写为更高性能的语言。而且大多数是I/O密集型操作，Go或C++主要是降低资源占用，Python的性能目前足够了。

## 功能特性

- **配置管理**: 读取、写入、重置配置文件
- **WiFi 配置**: 扫描和连接 WiFi 网络
- **Web 界面**: 提供配置页面
- **mDNS 广播**: 自动在局域网广播服务，支持 phone-app 自动发现
- **日志管理**: 查看系统日志
- **音量控制**: 系统音量管理
- **认证服务**: 简单的会话认证

## 目录结构

```
robot-server/
├── src/
│   ├── 服务/                    # 服务层
│   │   ├── __init__.py
│   │   ├── auth_service.py      # 认证服务
│   │   ├── config_service.py    # 配置服务
│   │   ├── log_service.py       # 日志服务
│   │   ├── mdns_service.py      # mDNS 服务
│   │   ├── sdk_service.py       # SDK 服务
│   │   ├── volume_service.py    # 音量服务
│   │   └── wifi_service.py      # WiFi 服务
│   ├── 路由/                    # 路由层
│   │   ├── __init__.py
│   │   ├── auth.py              # 认证路由
│   │   ├── config.py            # 配置路由
│   │   ├── logs.py              # 日志路由
│   │   ├── sdk.py               # SDK 路由
│   │   ├── system.py            # 系统路由
│   │   ├── volume.py            # 音量路由
│   │   └── wifi.py              # WiFi 路由
│   ├── __init__.py
│   ├── app.py                   # FastAPI 应用
│   └── 认证.py                  # 依赖注入
├── static/                      # 静态文件
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── app.js
│   └── index.html               # Web 配置页面
├── scripts/
│   ├── install.sh               # 安装脚本
│   ├── start.sh                 # 启动脚本
│   └── stop.sh                  # 停止脚本
├── main.py                      # 入口文件
├── pyproject.toml
└── README.md
```

## 安装运行

### 安装依赖

```bash
# 建议先进入虚拟环境，避免污染系统 Python
cd robot-server
python -m pip install -e ../sparkrobot-common
python -m pip install -e .
```

### 运行

```bash
python main.py
```

服务器将运行在 `http://0.0.0.0:8080`。

## API 接口

### 认证 API

| 方法 | 路径                  | 描述         |
| ---- | --------------------- | ------------ |
| POST | `/api/v1/auth/login`  | 登录认证     |
| POST | `/api/v1/auth/logout` | 登出         |
| GET  | `/api/v1/auth/status` | 获取认证状态 |

### 配置 API

| 方法 | 路径                    | 描述             |
| ---- | ----------------------- | ---------------- |
| GET  | `/api/v1/config`        | 获取全部配置     |
| GET  | `/api/v1/config/{key}`  | 获取单项配置     |
| GET  | `/api/v1/config/fields` | 获取配置字段定义 |
| GET  | `/api/v1/config/path`   | 获取配置文件路径 |
| POST | `/api/v1/config`        | 更新配置（批量） |
| POST | `/api/v1/config/reset`  | 重置配置         |
| POST | `/api/v1/config/reload` | 重新加载配置     |

### WiFi API

| 方法 | 路径                   | 描述           |
| ---- | ---------------------- | -------------- |
| GET  | `/api/v1/wifi/scan`    | 扫描 WiFi 网络 |
| POST | `/api/v1/wifi/connect` | 连接 WiFi      |
| GET  | `/api/v1/wifi/status`  | 获取 WiFi 状态 |

### 音量 API

| 方法 | 路径                  | 描述         |
| ---- | --------------------- | ------------ |
| GET  | `/api/v1/volume`      | 获取当前音量 |
| POST | `/api/v1/volume`      | 设置音量     |
| POST | `/api/v1/volume/mute` | 设置静音     |

### 日志 API

| 方法 | 路径                      | 描述         |
| ---- | ------------------------- | ------------ |
| GET  | `/api/v1/logs`            | 获取日志列表 |
| GET  | `/api/v1/logs/{filename}` | 获取日志内容 |

### SDK API

| 方法 | 路径                 | 描述          |
| ---- | -------------------- | ------------- |
| GET  | `/api/v1/sdk/status` | 获取 SDK 状态 |
| POST | `/api/v1/sdk/mode`   | 切换 SDK 模式 |

### 系统 API

| 方法 | 路径                      | 描述         |
| ---- | ------------------------- | ------------ |
| GET  | `/api/v1/system/info`     | 获取系统信息 |
| POST | `/api/v1/system/reboot`   | 重启系统     |
| POST | `/api/v1/system/shutdown` | 关机         |

### 遥测 API

| 方法 | 路径                     | 描述 |
| ---- | ------------------------ | ---- |
| GET  | `/api/v1/telemetry`      | 获取当前整机摘要遥测，兼容现有页面与脚本 |
| GET  | `/api/v1/telemetry/full` | 获取完整遥测快照，包含 `dog_state / imu_info / odom_info / feedback / navigation_state / bridge_status` 等最新缓存 |

当前本地配置页顶部遥测栏也会显示：

- 整机在线状态
- 电量、温度、设备名
- `bridge_status` 对应的运控桥状态、裁决原因、当前输出速度

## mDNS 服务发现

robot-server 启动后会自动在局域网广播 mDNS 服务，phone-app 可以通过 `/api/v1/robots/discover` 接口自动发现局域网内的所有机器人。

### 服务类型

- `_sparkrobot._tcp.local.`

### TXT 记录

广播的 TXT 记录包含：

| 字段    | 描述            |
| ------- | --------------- |
| uuid    | 机器人唯一标识  |
| name    | 机器人名称      |
| model   | 机器人型号      |
| version | robot-agent版本 |
| ip      | IP 地址         |
| port    | 服务端口        |

### 发现流程

```
┌─────────────────┐
│  phone-app      │
│   后端服务       │
└────────┬────────┘
         │ mDNS 查询
         │ _sparkrobot._tcp.local.
         ▼
┌─────────────────┐
│  robot-server   │
│   mDNS 广播      │
│   TXT: uuid,    │
│       name,     │
│       model...  │
└─────────────────┘
```

## Web 配置界面

robot-server 提供了一个简单的 Web 配置界面，访问 `http://<机器狗IP>:8080` 即可使用。

### 功能

- 查看和修改配置
- 扫描和连接 WiFi
- 查看系统日志
- 调整音量
- 查看 SDK 状态

## 配置文件

配置文件位置：`~/sparkrobot/config/config.toml`

使用简化的 TOML 格式（一层嵌套）：

```toml
[robot]
name = "robot-dog-1"
model = "agibot-d1"
version = "zsl-1"

[network]
wifi_ssid = "MyWiFi"
wifi_password = "password"

[audio]
volume = 80
mute = false

[cloud]
enabled = true
server_url = "ws://192.168.1.100:9000"
business_url = "/api/v1/robot/business"

[studio]
enabled = false
server_url = "ws://192.168.5.8:9010"
business_url = "/api/v1/web/business"
```

## 与 robot-agent 的关系

```
┌─────────────────────────────────────────────────────┐
│                   机器狗端                          │
│  ┌─────────────────┐      ┌─────────────────┐      │
│  │  robot-server   │      │  robot-agent    │      │
│  │  (端口 8080)     │      │  (WebSocket)    │      │
│  │                 │      │                 │      │
│  │  - 配置管理      │◄────►│  - 读取配置     │      │
│  │  - WiFi 配置     │      │  - 状态上报     │      │
│  │  - mDNS 广播     │      │  - 音量控制     │      │
│  │  - Web 界面      │      │  - SDK 模式     │      │
│  └─────────────────┘      └─────────────────┘      │
│           │                        │               │
│           ▼                        ▼               │
│  ┌─────────────────────────────────────────┐       │
│  │         ~/sparkrobot/config/            │       │
│  │         config.toml (共享配置)           │       │
│  └─────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────┘
```

robot-agent 通过 HTTP 调用 robot-server 的 API 来：

- 获取/更新配置
- 控制音量
- 切换 SDK 模式

## 开机自启动

创建服务文件 `/etc/systemd/system/sparkrobot-server.service`:

```ini
[Unit]
Description=Robot Server
After=network.target

[Service]
Type=simple
User=firefly
WorkingDirectory=/home/firefly/sparkrobot/robot-server
ExecStart=/usr/bin/python3 /home/firefly/sparkrobot/robot-server/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable sparkrobot-server
sudo systemctl start sparkrobot-server
```

查看日志：

```bash
sudo journalctl -u sparkrobot-server -f
```

关闭/重启服务：

```bash
sudo systemctl stop sparkrobot-server
sudo systemctl restart sparkrobot-server
```
