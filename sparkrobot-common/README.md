# SparkRobot Common

SparkRobot 通用库，提供配置管理、日志、工具函数等通用功能。

## 功能

- **配置管理**: 简化 TOML 格式的配置解析和生成
- **常量定义**: 共享的配置字段、路径常量
- **日志工具**: 统一的日志格式和文件管理
- **工具函数**: UUID 生成、IP 获取等通用函数

## 安装

```bash
# 开发模式安装
# 先进入当前目录（含有README的目录）
python -m pip install --upgrade pip setuptools wheel
pip install -e .
```

## 使用

```python
from sparkrobot_common import (
    # 常量
    ORG_NAME,
    WORKSPACE_DIR,
    CONFIG_DIR,
    CONFIG_FILE,

    # 配置字段
    DEFAULT_CONFIG_FIELDS,
    READONLY_FIELDS,
    获取默认配置,
    获取字段信息,

    # TOML 解析
    TomlParser,

    # 日志
    configure_logger,
    get_logger,

    # 工具
    生成UUID,
    获取本机IP,
)
```

## 配置格式

配置文件使用简化的 TOML 格式（一层嵌套）：

```toml
[section]
key = "value"
number = 123
array = ["a", "b", "c"]
```
