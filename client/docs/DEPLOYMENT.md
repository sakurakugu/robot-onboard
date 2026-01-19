# 机器狗客户端部署指南

## 概述

本文档详细说明如何将机器狗客户端部署到实际的机器狗设备上，并配置与服务端的通信。

## 系统架构

```
┌─────────────────┐      WebSocket     ┌─────────────────┐
│   服务端        │◄──────────────────► │   机器狗客户端   │
│  (后端+前端)    │                     │    (Python)     │
└─────────────────┘                    └─────────────────┘
        │                                       │
        │                                       │
        ▼                                       ▼
  ┌──────────┐                          ┌──────────┐
  │  数据库   │                          │ 机器狗SDK│
  └──────────┘                          └──────────┘
```

## 部署方式

### 方式一：自动部署（推荐）

通过服务端前端界面自动部署客户端代码。

#### 步骤

1. **启动服务端**
   ```bash
   cd app/robot-chat/backend
   npm start
   ```

2. **访问前端界面**
   - 打开浏览器访问：http://localhost:5174
   - 进入"机器人管理"页面

3. **添加机器狗**
   - 点击"添加机器人"按钮
   - 填写信息：
     - 名称：机器狗的名字
     - IP地址：机器狗的网络地址
     - 本地IP：服务器的IP（机器狗连接用）
     - 型号：如 unitree-go2
   - 点击"添加"

4. **自动部署流程**
   - 服务端通过 SSH 连接到机器狗
   - 创建 `~/robot-chat` 目录
   - 检测机器狗是否已有 UUID（从 `~/robot-chat/config.json`）
   - 如果没有 UUID，生成新的 UUIDv7
   - 将客户端代码复制到机器狗
   - 保存 UUID 到 `~/robot-chat/config.json`

5. **在机器狗上运行客户端**
   ```bash
   # SSH 登录到机器狗
   ssh firefly@<机器狗IP>
   
   # 进入客户端目录
   cd ~/robot-chat
   
   # 安装依赖
   ./install.sh
   
   # 修改配置文件中的服务器地址
   vi config.toml
   # 将 server.url 改为: ws://<服务器IP>:3002/ws
   
   # 启动客户端
   ./start_daemon.sh
   ```

#### 前置条件

- 机器狗必须已配置 SSH 免密登录
- 机器狗与服务器在同一网络内
- 用户名为 `firefly`（或在代码中修改）

### 方式二：手动部署

适用于无法使用自动部署的情况。

#### 步骤

1. **打包客户端代码**
   ```bash
   cd app/robot-chat/client
   tar czf robot-client.tar.gz *
   ```

2. **传输到机器狗**
   ```bash
   scp robot-client.tar.gz firefly@<机器狗IP>:~/
   ```

3. **在机器狗上解压和配置**
   ```bash
   # SSH 登录
   ssh firefly@<机器狗IP>
   
   # 创建目录
   mkdir -p ~/robot-chat
   
   # 解压
   cd ~/robot-chat
   tar xzf ~/robot-client.tar.gz
   rm ~/robot-client.tar.gz
   
   # 安装依赖
   ./install.sh
   ```

4. **配置客户端**

   编辑 `~/robot-chat/config.toml`：
   ```toml
   [robot]
   name = "robot-dog-1"        # 修改为你的机器狗名字
   uuid = "自动生成"            # 首次运行会自动生成
   model = "unitree-go2"        # 修改为实际型号
   
   [server]
   url = "ws://192.168.1.100:3002/ws"  # 修改为服务器地址
   reconnect_interval = 5
   heartbeat_interval = 30
   ```

5. **启动客户端**
   ```bash
   ./start_daemon.sh
   ```

## UUID 管理

### UUID 生成规则

1. **服务端添加机器狗时**：
   - 检查机器狗的 `~/robot-chat/config.json` 文件
   - 如果文件存在且包含 `uuid` 字段，使用该 UUID
   - 如果不存在，服务端生成新的 UUIDv7
   - 服务端将 UUID 写入机器狗的 `config.json`

2. **客户端首次运行时**：
   - 检查 `~/robot-chat/config.toml` 文件
   - 如果不存在，生成新的 UUIDv7
   - 保存到配置文件中

### UUID 同步建议

- **推荐方式**：先在服务端添加机器狗，自动生成并同步 UUID
- **手动方式**：
  1. 客户端先运行一次生成 UUID
  2. 复制 `config.toml` 中的 UUID
  3. 在服务端添加机器狗时使用该 UUID

## 客户端集成

### 与机器狗 SDK 集成

参考 `robot_client_integrated.py`：

```python
from robot_client import RobotClient

# 导入你的机器狗 SDK
# from unitree_sdk import RobotController

class RobotActionExecutor:
    def __init__(self):
        # self.robot = RobotController()
        pass
    
    async def execute(self, action: str, parameters: dict) -> bool:
        if action == 'stand_up':
            # self.robot.stand_up()
            print("站起")
            return True
        elif action == 'sit_down':
            # self.robot.sit_down()
            print("坐下")
            return True
        # ... 其他动作
        return False

async def main():
    client = RobotClient()
    executor = RobotActionExecutor()
    client.set_action_executor(executor.execute)
    await client.run()
```

### 支持的动作类型

需要在客户端实现以下动作（根据实际 SDK 调整）：

- `stand_up` - 站起
- `sit_down` - 坐下
- `walk_forward` - 前进
- `walk_backward` - 后退
- `turn_left` - 左转
- `turn_right` - 右转
- `wave` - 挥手
- `dance` - 跳舞

## 开机自启动

### 使用 systemd

1. **创建服务文件**
   ```bash
   sudo vi /etc/systemd/system/robot-client.service
   ```

2. **写入配置**
   ```ini
   [Unit]
   Description=Robot Dog Client
   After=network.target
   
   [Service]
   Type=simple
   User=firefly
   WorkingDirectory=/home/firefly/robot-chat
   ExecStart=/usr/bin/python3 /home/firefly/robot-chat/robot_client.py
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target
   ```

3. **启用服务**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable robot-client
   sudo systemctl start robot-client
   ```

4. **管理服务**
   ```bash
   # 查看状态
   sudo systemctl status robot-client
   
   # 查看日志
   sudo journalctl -u robot-client -f
   
   # 停止服务
   sudo systemctl stop robot-client
   
   # 重启服务
   sudo systemctl restart robot-client
   ```

## 运维管理

### 日志查看

```bash
# 客户端日志
tail -f ~/robot-chat/logs/robot_client_*.log

# 后台运行日志
tail -f ~/robot-chat/logs/client_output.log

# systemd 日志
sudo journalctl -u robot-client -f
```

### 状态检查

```bash
# 检查进程
ps aux | grep robot_client

# 检查 PID 文件
cat ~/robot-chat/client.pid

# 检查配置
cat ~/robot-chat/config.toml
```

### 重启客户端

```bash
# 后台模式
./stop.sh
./start_daemon.sh

# systemd 模式
sudo systemctl restart robot-client
```

### 更新客户端

```bash
# 1. 停止客户端
./stop.sh  # 或 sudo systemctl stop robot-client

# 2. 备份配置
cp ~/robot-chat/config.toml ~/robot-chat/config.toml.bak

# 3. 更新代码（方式一：从服务器拉取）
cd ~/robot-chat
# 手动复制新文件，或者重新运行自动部署

# 4. 恢复配置
cp ~/robot-chat/config.toml.bak ~/robot-chat/config.toml

# 5. 重启客户端
./start_daemon.sh  # 或 sudo systemctl start robot-client
```

## 故障排查

### 1. 无法连接到服务器

**现象**：客户端日志显示连接失败

**排查步骤**：
```bash
# 1. 检查网络连接
ping <服务器IP>

# 2. 检查端口是否开放
telnet <服务器IP> 3002

# 3. 检查配置文件
cat ~/robot-chat/config.toml | grep url

# 4. 检查服务器防火墙
# 在服务器上：
sudo ufw status
sudo ufw allow 3002
```

### 2. 客户端频繁重连

**现象**：日志中反复出现连接/断开

**排查步骤**：
```bash
# 1. 检查网络稳定性
ping -c 100 <服务器IP>

# 2. 调整心跳间隔
vi ~/robot-chat/config.toml
# 增加 heartbeat_interval 值

# 3. 检查服务器负载
# 在服务器上：
top
```

### 3. 动作未执行

**现象**：收到动作指令但机器狗没有响应

**排查步骤**：
```bash
# 1. 检查日志中是否收到动作
tail -f ~/robot-chat/logs/robot_client_*.log | grep action

# 2. 确认动作执行器已设置
# 检查代码中是否调用了 set_action_executor

# 3. 测试机器狗 SDK
# 编写简单测试脚本验证 SDK 功能
```

### 4. SSH 自动部署失败

**现象**：在服务端添加机器狗时报错

**排查步骤**：
```bash
# 1. 测试 SSH 连接
ssh firefly@<机器狗IP> exit

# 2. 配置免密登录
ssh-keygen -t rsa
ssh-copy-id firefly@<机器狗IP>

# 3. 检查服务端日志
cd app/robot-chat/backend
cat logs/*.log | grep -i error
```

## 安全建议

1. **SSH 安全**
   - 使用 SSH 密钥认证
   - 禁用密码登录
   - 限制 SSH 访问 IP

2. **网络安全**
   - 使用防火墙限制端口访问
   - 考虑使用 VPN
   - 启用 HTTPS/WSS（生产环境）

3. **权限管理**
   - 客户端使用非 root 用户运行
   - 限制文件权限

## 性能优化

1. **降低延迟**
   - 减少心跳间隔
   - 使用有线网络
   - 优化服务器性能

2. **减少带宽**
   - 压缩音频数据
   - 限制日志输出
   - 使用二进制协议（可选）

3. **提高稳定性**
   - 启用自动重连
   - 实现请求重试
   - 监控网络质量

## 附录

### A. 配置文件完整示例

```toml
[robot]
name = "robot-dog-1"
uuid = "01934b7e-8f2a-7890-abcd-ef0123456789"
model = "unitree-go2"

[server]
url = "ws://192.168.1.100:3002/ws"
reconnect_interval = 5
heartbeat_interval = 30

[audio]
format = "opus"
sample_rate = 48000
channels = 1

[logging]
level = "INFO"
max_file_size_mb = 10
```

### B. 文件清单

客户端目录应包含以下文件：

- `robot_client.py` - 主程序
- `robot_client_integrated.py` - 集成示例
- `requirements.txt` - 依赖列表
- `README.md` - 使用说明
- `install.sh` - 安装脚本
- `start.sh` - 启动脚本（前台）
- `start_daemon.sh` - 启动脚本（后台）
- `stop.sh` - 停止脚本

### C. 依赖版本

```
websockets>=12.0
tomli>=2.0.1
tomli-w>=1.0.0
```

Python 版本要求：>= 3.7

## 支持

如有问题，请查看：
- 客户端日志：`~/robot-chat/logs/`
- 服务端日志：`app/robot-chat/backend/logs/`
- 项目文档：`docs/机器狗对话/`
