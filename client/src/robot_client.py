#!/usr/bin/env python3
"""
机器狗客户端
功能：
- 配置管理（~/sparkrobot/config/robot-chat.toml）
- WebSocket 通信
- 心跳保持
- 接收音频回复（opus）
- 执行动作指令
- 日志记录
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Dict, Any, Callable
import base64
from lib.util import generate_uuid
from lib.api import CrazyRobotDog
from lib.api.logger import CNLevelFormatter

import websockets
from websockets import ClientConnection

try:
    import tomli
    import tomli_w
except ImportError:
    print("请安装依赖: pip install -r $HOME/sparkrobot/robot-chat/requirements.txt")
    sys.exit(1)


class RobotClient:
    """机器狗客户端"""

    def __init__(self, workspace: Optional[Path] = None):
        """初始化客户端
        
        Args:
            workspace: 工作目录，默认为 ~/sparkrobot
        """
        # 配置目录
        if workspace is None:
            workspace = Path.home() / "sparkrobot"
        self.base_dir = workspace
        self.config_dir = self.base_dir / "config"
        self.project_name = "robot-chat"
        self.log_dir = self.base_dir / "logs" / self.project_name
        
        # 配置文件
        self.global_config_file = self.config_dir / "config.toml"         # 全局配置（uuid等）
        self.config_file = self.config_dir / f"{self.project_name}.toml"  # 机器人对话专用配置
        
        # 确保目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载配置
        self.config = self._load_or_create_config()
        
        # 设置日志
        self._setup_logger()
        
        # WebSocket 连接
        self.ws: Optional[ClientConnection] = None
        self.connected = False
        self.reconnect_interval = 5  # 秒
        self.heartbeat_interval = 30  # 秒
        
        # 消息处理器
        self.message_handlers: Dict[str, Callable] = {
            'text_response': self._handle_text_response,
            'audio_response': self._handle_audio_response,
            'action_command': self._handle_action_command,
            'error': self._handle_error,
        }
        
        # 动作执行器（需要用户自定义）
        self.action_executor: Optional[Callable] = None
        
    def _load_or_create_config(self) -> Dict[str, Any]:
        """加载或创建配置文件"""
        # 1. 加载全局配置 (uuid/name/model 等，扁平结构)
        if self.global_config_file.exists():
            with open(self.global_config_file, 'rb') as f:
                global_config = tomli.load(f)
        else:
            # 创建默认全局配置
            global_config = {
                'uuid': generate_uuid(),
                'name': 'robot-dog-1',
                'model': 'agibot-d1',
            }
            with open(self.global_config_file, 'wb') as f:
                tomli_w.dump(global_config, f)

        # 2. 加载robot-chat专用配置
        if self.config_file.exists():
            with open(self.config_file, 'rb') as f:
                robot_chat_config = tomli.load(f)
        else:
            # 创建默认robot-chat配置
            robot_chat_config = {
                'server': {
                    'url': 'ws://192.168.0.88:3002/api/conversation/connect',
                    'reconnect_interval': 5,
                    'heartbeat_interval': 30,
                },
                'sdk': {
                    'robot_ip': '127.0.0.1',
                    'local_port': 43988,
                },
                'audio': {
                    'format': 'opus',
                    'sample_rate': 48000,
                    'channels': 1,
                },
                'logging': {
                    'level': 'INFO',
                    'max_file_size_mb': 10,
                }
            }
            with open(self.config_file, 'wb') as f:
                tomli_w.dump(robot_chat_config, f)
        
        # 3. 合并配置，将全局扁平字段组装为运行时 robot 节
        config = robot_chat_config
        config['robot'] = {
            'uuid': global_config.get('uuid', generate_uuid()),
            'name': global_config.get('name'),
            'model': global_config.get('model'),
        }
        
        return config
    
    def _save_config(self, config: Dict[str, Any]) -> None:
        """保存配置到文件"""
        # 分离全局配置和专用配置（写入扁平结构）
        robot_cfg = config.get('robot', {})
        global_config = {
            'uuid': robot_cfg.get('uuid', generate_uuid()),
            'name': robot_cfg.get('name'),
            'model': robot_cfg.get('model'),
        }
        with open(self.global_config_file, 'wb') as f:
            tomli_w.dump(global_config, f)
        
        # 保存robot-chat专用配置
        robot_chat_config = {k: v for k, v in config.items() if k != 'robot'}
        with open(self.config_file, 'wb') as f:
            tomli_w.dump(robot_chat_config, f)
    
    def _setup_logger(self) -> None:
        level = self.config['logging'].get('level', 'INFO')
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        formatter = CNLevelFormatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        file_handler = logging.FileHandler(self.log_dir / f"robot_client_{time.strftime('%Y%m%d')}.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        console_handler = logging.StreamHandler()
        console_formatter = CNLevelFormatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%H:%M:%S.%f")
        console_handler.setFormatter(console_formatter)
        logger = logging.getLogger("RobotClient")
        logger.setLevel(level)
        logger.handlers = []
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        self.logger = logger
        
    async def connect(self) -> bool:
        """连接到服务器"""
        try:
            robot_uuid = self.config['robot']['uuid']
            server_url = self.config['server']['url']
            
            # 添加 robotId 参数
            url = f"{server_url}?robotId={robot_uuid}"
            
            self.logger.info(f"正在连接服务器: {url}")
            self.ws = await websockets.connect(url)
            self.connected = True
            self.logger.info(f"已连接到服务器，机器狗UUID: {robot_uuid}")
            
            # 发送注册消息
            await self.send_register()
            
            return True
            
        except Exception as e:
            self.logger.error(f"连接失败: {e}")
            self.connected = False
            return False
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self.ws:
            await self.ws.close()
            self.connected = False
            self.logger.info("已断开连接")
    
    async def send_message(self, message: Dict[str, Any]) -> None:
        """发送消息到服务器"""
        if not self.ws or not self.connected:
            self.logger.warning("未连接到服务器，无法发送消息")
            return
        
        try:
            await self.ws.send(json.dumps(message))
            self.logger.debug(f"发送消息: {message['type']}")
        except Exception as e:
            self.logger.error(f"发送消息失败: {e}")
            self.connected = False
    
    async def send_text(self, text: str) -> None:
        """发送文本消息"""
        message = {
            'type': 'text_input',
            'robotId': self.config['robot']['uuid'],
            'timestamp': int(time.time() * 1000),
            'data': {
                'text': text
            }
        }
        await self.send_message(message)
    
    async def send_audio_chunk(self, audio_bytes: bytes) -> None:
        message = {
            'type': 'audio_chunk',
            'robotId': self.config['robot']['uuid'],
            'timestamp': int(time.time() * 1000),
            'data': {
                'format': 'opus',
                'sampleRate': self.config['audio'].get('sample_rate', 48000),
                'channels': self.config['audio'].get('channels', 1),
                'buffer': base64.b64encode(audio_bytes).decode('ascii')
            }
        }
        await self.send_message(message)
    
    async def send_register(self) -> None:
        """发送注册消息"""
        message = {
            'type': 'client_register',
            'robotId': self.config['robot']['uuid'],
            'timestamp': int(time.time() * 1000),
            'data': {
                'name': self.config['robot'].get('name'),
                'model': self.config['robot'].get('model'),
                'version': '1.0.0',
                'metadata': {}
            }
        }
        await self.send_message(message)
    
    async def send_heartbeat(self) -> None:
        """发送心跳包"""
        message = {
            'type': 'heartbeat',
            'robotId': self.config['robot']['uuid'],
            'timestamp': int(time.time() * 1000),
            'data': {}
        }
        await self.send_message(message)
    
    async def send_status(self, status: Dict[str, Any]) -> None:
        """发送状态信息"""
        message = {
            'type': 'status',
            'robotId': self.config['robot']['uuid'],
            'timestamp': int(time.time() * 1000),
            'data': status
        }
        await self.send_message(message)
    
    async def _handle_text_response(self, data: Dict[str, Any]) -> None:
        """处理文本响应"""
        text = data.get('text', '')
        self.logger.info(f"收到文本响应: {text}")
    
    async def _handle_audio_response(self, data: Dict[str, Any]) -> None:
        """处理音频响应"""
        audio_format = data.get('format', 'opus')
        audio_buffer = data.get('buffer', '')
        duration = data.get('duration', 0)
        
        self.logger.info(f"收到音频响应: format={audio_format}, duration={duration}s")
        
        try:
            if audio_format != 'opus':
                self.logger.error(f"不支持的音频格式: {audio_format}")
                return
            audio_data = base64.b64decode(audio_buffer)
            
            audio_file = self.log_dir / f"audio_{int(time.time())}.opus"
            with open(audio_file, 'wb') as f:
                f.write(audio_data)
            self.logger.info(f"音频已保存: {audio_file}")
            
            # TODO: 播放音频
            
        except Exception as e:
            self.logger.error(f"处理音频失败: {e}")
    
    async def _handle_action_command(self, data: Dict[str, Any]) -> None:
        """处理动作指令"""
        action = data.get('action', '')
        parameters = data.get('parameters', {})
        safety_checked = data.get('safetyChecked', False)
        
        self.logger.info(f"收到动作指令: action={action}, parameters={parameters}")
        
        # 执行动作
        if self.action_executor:
            try:
                result = await self.action_executor(action, parameters)
                self.logger.info(f"动作执行结果: {result}")
            except Exception as e:
                self.logger.error(f"执行动作失败: {e}")
        else:
            self.logger.warning("未设置动作执行器，跳过动作执行")
    
    async def _handle_error(self, data: Dict[str, Any]) -> None:
        """处理错误消息"""
        code = data.get('code', '')
        message = data.get('message', '')
        self.logger.error(f"服务器错误: {code} - {message}")
    
    async def _receive_loop(self) -> None:
        """接收消息循环"""
        while self.connected:
            try:
                if not self.ws:
                    break
                    
                message_str = await self.ws.recv()
                message = json.loads(message_str)
                
                msg_type = message.get('type')
                data = message.get('data', {})
                
                # 调用相应的处理器
                handler = self.message_handlers.get(msg_type)
                if handler:
                    await handler(data)
                else:
                    self.logger.warning(f"未知的消息类型: {msg_type}")
                    
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("连接已关闭")
                self.connected = False
                break
            except Exception as e:
                self.logger.error(f"接收消息失败: {e}")
                await asyncio.sleep(1)
    
    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        interval = self.config['server'].get('heartbeat_interval', 30)
        while self.connected:
            await asyncio.sleep(interval)
            if self.connected:
                await self.send_heartbeat()
    
    async def run(self) -> None:
        """运行客户端（自动重连）"""
        self.logger.info("机器狗客户端启动")
        
        while True:
            try:
                # 尝试连接
                if not self.connected:
                    success = await self.connect()
                    if not success:
                        reconnect_interval = self.config['server'].get('reconnect_interval', 5)
                        self.logger.info(f"{reconnect_interval} 秒后重试连接...")
                        await asyncio.sleep(reconnect_interval)
                        continue
                
                # 启动接收和心跳循环
                receive_task = asyncio.create_task(self._receive_loop())
                heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                
                # 等待任务完成
                await asyncio.gather(receive_task, heartbeat_task)
                
            except KeyboardInterrupt:
                self.logger.info("收到中断信号，正在退出...")
                break
            except Exception as e:
                self.logger.error(f"运行时错误: {e}")
                self.connected = False
                
            finally:
                if self.ws:
                    await self.disconnect()
    
    def set_action_executor(self, executor: Callable) -> None:
        """设置动作执行器
        
        Args:
            executor: 异步函数，签名为 async def executor(action: str, parameters: dict) -> bool
        """
        self.action_executor = executor


async def main():
    """主函数"""
    client = RobotClient()

    # 构建 SDK 控制器（默认在机器狗内部运行，端口43988）
    sdk_cfg = client.config.get('sdk', {})
    robot_name = client.config['robot'].get('name', 'robot-dog')
    robot_ip = sdk_cfg.get('robot_ip', '192.168.234.1')
    local_port = int(sdk_cfg.get('local_port', 43988))

    class RobotSDKController:
        def __init__(self, name: str, robot_ip: str, local_port: int):
            self.dog = CrazyRobotDog(name=name, robot_ip=robot_ip, local_port=local_port, local_ip=robot_ip)

        async def execute(self, action: str, parameters: dict) -> bool:
            try:
                if action == 'stand_up':
                    await asyncio.to_thread(self.dog.stand_up)
                elif action == 'sit_down':
                    await asyncio.to_thread(self.dog.lie_down)
                elif action == 'shake_hand':
                    await asyncio.to_thread(self.dog.shake_hand)
                elif action == 'walk_forward':
                    steps = float(parameters.get('steps', 1))
                    speed = float(parameters.get('speed', 0.5))
                    distance = steps * 0.5
                    await asyncio.to_thread(self.dog.move_by_distance, "x", distance, speed)
                elif action == 'walk_backward':
                    steps = float(parameters.get('steps', 1))
                    speed = float(parameters.get('speed', 0.5))
                    distance = steps * 0.5
                    await asyncio.to_thread(self.dog.move_by_distance, "-x", distance, speed)
                elif action == 'turn_left':
                    angle = float(parameters.get('angle', 90))
                    speed = float(parameters.get('speed', 30))
                    await asyncio.to_thread(self.dog.turn_around, angle, speed, "ccw")
                elif action == 'turn_right':
                    angle = float(parameters.get('angle', 90))
                    speed = float(parameters.get('speed', 30))
                    await asyncio.to_thread(self.dog.turn_around, angle, speed, "cw")
                elif action == 'nod':
                    duration = float(parameters.get('duration', 0.5))
                    await asyncio.to_thread(self.dog.nod_down, duration, 0.3)
                    await asyncio.to_thread(self.dog.nod_up, duration, 0.3)
                    await asyncio.to_thread(self.dog.attitude_rest, 0.3)
                elif action == 'wave':
                    await asyncio.to_thread(self.dog.stand_up)
                    await asyncio.to_thread(self.dog.lean_left, 0.4, 0.2)
                    await asyncio.to_thread(self.dog.lean_right, 0.4, 0.2)
                    await asyncio.to_thread(self.dog.attitude_rest, 0.3)
                elif action == 'dance':
                    await asyncio.to_thread(self.dog.stand_up)
                    await asyncio.to_thread(self.dog.rotate_counterclockwise, 0.4, 0.2)
                    await asyncio.to_thread(self.dog.rotate_clockwise, 0.4, 0.2)
                    await asyncio.to_thread(self.dog.max_height, 0.4, 0.3)
                    await asyncio.to_thread(self.dog.min_height, 0.4, -0.3)
                    await asyncio.to_thread(self.dog.attitude_rest, 0.3)
                else:
                    return False
                return True
            except Exception:
                return False

    controller = RobotSDKController(robot_name, robot_ip, local_port)

    async def action_executor(action: str, parameters: dict) -> bool:
        return await controller.execute(action, parameters)
    
    client.set_action_executor(action_executor)
    
    # 运行客户端
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\n客户端已停止")


if __name__ == '__main__':
    asyncio.run(main())
