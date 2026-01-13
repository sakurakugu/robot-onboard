# 机器狗对话客户端

Python客户端用于连接机器狗对话管理系统。

## 依赖安装

```bash
pip install websockets
```

## 使用方法

### 基本使用

```bash
python robot_client.py
```

### 指定服务器地址

```bash
python robot_client.py ws://192.168.1.100:3001/api/conversation/connect
```

### 指定机器狗ID

```bash
python robot_client.py ws://localhost:3001/api/conversation/connect your-robot-id
```

## 示例对话

```
你: 你好
<<< 你好主人！我是你的机器狗助手，有什么可以帮到你的吗？

你: 坐下
<<< 好的主人[ACTION:sit_down()]
🤖 执行动作: sit_down
   ✓ 安全检查通过
   正在执行 sit_down...
   ✓ sit_down 执行完成

你: 向前走两步
<<< 好的，我来走两步[ACTION:walk_forward(steps=2)]
🤖 执行动作: walk_forward
   参数: {'steps': 2}
   ✓ 安全检查通过
   正在执行 walk_forward...
   ✓ walk_forward 执行完成
```

## 功能特性

- ✅ WebSocket连接管理
- ✅ 文本对话
- ✅ 动作指令接收和执行
- ✅ 心跳保持连接
- ✅ 交互式命令行界面
- ⏳ 音频输入支持（开发中）
- ⏳ 音频输出播放（开发中）

## 集成到实际机器狗

在 `execute_action` 方法中替换模拟代码为实际的机器狗SDK调用：

```python
async def execute_action(self, action: str, parameters: Dict[str, Any]):
    """执行动作"""
    # 导入你的机器狗SDK
    from robot_control.lib.api import sdk
    
    # 根据动作名称调用对应的SDK方法
    if action == "stand_up":
        await sdk.stand_up()
    elif action == "sit_down":
        await sdk.sit_down()
    elif action == "walk_forward":
        steps = parameters.get("steps", 1)
        await sdk.walk_forward(steps)
    # ... 其他动作
```
