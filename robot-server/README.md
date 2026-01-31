# Robot Server

机器狗配置服务器，提供配置管理和 WiFi 配置的 HTTP API。

## 功能

- **配置管理**: 读取、写入、重置配置文件
- **WiFi 配置**: 扫描和连接 WiFi 网络
- **Web 界面**: 提供配置页面

## 安装

```bash
# 安装依赖
pip install -e ../sparkrobot-common
pip install -e .
```

## 运行

```bash
python server.py
```

服务器将运行在 `http://0.0.0.0:8080`。

## API

### 配置 API

- `GET /api/v1/config` - 获取全部配置
- `GET /api/v1/config/{key}` - 获取单项配置
- `GET /api/v1/config/fields` - 获取配置字段定义
- `GET /api/v1/config/path` - 获取配置文件路径
- `POST /api/v1/config` - 更新配置（批量）
- `POST /api/v1/config/reset` - 重置配置
- `POST /api/v1/config/reload` - 重新加载配置

### WiFi API

- `GET /api/v1/wifi/scan` - 扫描 WiFi 网络
- `POST /api/v1/wifi/connect` - 连接 WiFi

## 配置文件

配置文件位置：`~/sparkrobot/config/config.toml`

使用简化的 TOML 格式（一层嵌套）。
