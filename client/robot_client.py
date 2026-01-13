"""
机器狗对话客户端
支持文本和音频输入，接收AI回复和动作指令
"""

import asyncio
import websockets
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any

class RobotDogClient:
    """机器狗对话客户端"""
    
    def __init__(self, server_url: str = "ws://localhost:3001/api/conversation/connect", robot_id: Optional[str] = None):
        """
        初始化客户端
        
        Args:
            server_url: WebSocket服务器地址
            robot_id: 机器狗UUID，如果不提供则由服务器生成
        """
        self.server_url = server_url
        self.robot_id = robot_id or str(uuid.uuid4())
        self.ws = None
        self.running = False
        
    async def connect(self):
        """连接到服务器"""
        uri = f"{self.server_url}?robotId={self.robot_id}"
        print(f"正在连接到服务器: {uri}")
        
        try:
            self.ws = await websockets.connect(uri)
            print(f"✓ 已连接到服务器")
            print(f"机器狗ID: {self.robot_id}")
            self.running = True
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            raise
    
    async def send_text(self, text: str):
        """
        发送文本消息
        
        Args:
            text: 要发送的文本内容
        """
        if not self.ws:
            raise Exception("未连接到服务器")
        
        message = {
            "type": "text_input",
            "robotId": self.robot_id,
            "timestamp": int(datetime.now().timestamp() * 1000),
            "data": {
                "text": text
            }
        }
        
        await self.ws.send(json.dumps(message))
        print(f"\n>>> {text}")
    
    async def send_heartbeat(self):
        """发送心跳"""
        if not self.ws:
            return
        
        message = {
            "type": "heartbeat",
            "robotId": self.robot_id,
            "timestamp": int(datetime.now().timestamp() * 1000),
            "data": {}
        }
        
        await self.ws.send(json.dumps(message))
    
    async def receive_messages(self):
        """接收服务器消息"""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError as e:
                    print(f"✗ 消息解析失败: {e}")
        except websockets.exceptions.ConnectionClosed:
            print("✗ 连接已关闭")
            self.running = False
    
    async def handle_message(self, data: Dict[str, Any]):
        """
        处理服务器消息
        
        Args:
            data: 消息数据
        """
        msg_type = data.get("type")
        
        if msg_type == "text_response":
            # 文本回复
            text = data["data"]["text"]
            print(f"<<< {text}")
            
        elif msg_type == "action_command":
            # 动作指令
            action = data["data"]["action"]
            parameters = data["data"]["parameters"]
            safety_checked = data["data"]["safetyChecked"]
            
            print(f"🤖 执行动作: {action}")
            if parameters:
                print(f"   参数: {parameters}")
            if safety_checked:
                print(f"   ✓ 安全检查通过")
            
            # 这里应该调用机器狗SDK执行实际动作
            await self.execute_action(action, parameters)
            
        elif msg_type == "audio_response":
            # 音频回复
            print("🔊 收到音频回复")
            # TODO: 播放音频
            
        elif msg_type == "error":
            # 错误消息
            error_code = data["data"]["code"]
            error_msg = data["data"]["message"]
            print(f"✗ 错误 [{error_code}]: {error_msg}")
    
    async def execute_action(self, action: str, parameters: Dict[str, Any]):
        """
        执行动作（模拟）
        
        在实际应用中，这里应该调用机器狗SDK来执行动作
        
        Args:
            action: 动作名称
            parameters: 动作参数
        """
        print(f"   正在执行 {action}...")
        await asyncio.sleep(0.5)  # 模拟动作执行时间
        print(f"   ✓ {action} 执行完成")
    
    async def heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            try:
                await self.send_heartbeat()
                await asyncio.sleep(30)  # 每30秒发送一次心跳
            except Exception as e:
                print(f"心跳发送失败: {e}")
                break
    
    async def interactive_mode(self):
        """交互模式 - 从控制台读取输入"""
        print("\n开始交互模式，输入文本与机器狗对话 (输入 'quit' 退出):")
        print("-" * 60)
        
        while self.running:
            try:
                # 使用 asyncio 的方式读取输入
                text = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: input("你: ")
                )
                
                if text.lower() in ['quit', 'exit', 'q']:
                    print("正在退出...")
                    self.running = False
                    break
                
                if text.strip():
                    await self.send_text(text)
                    
            except KeyboardInterrupt:
                print("\n正在退出...")
                self.running = False
                break
            except Exception as e:
                print(f"错误: {e}")
    
    async def run(self):
        """运行客户端"""
        await self.connect()
        
        try:
            # 同时运行消息接收、心跳和交互模式
            await asyncio.gather(
                self.receive_messages(),
                self.heartbeat_loop(),
                self.interactive_mode()
            )
        except Exception as e:
            print(f"运行时错误: {e}")
        finally:
            if self.ws:
                await self.ws.close()
            print("客户端已关闭")


async def main():
    """主函数"""
    import sys
    
    # 服务器地址
    server_url = "ws://localhost:3001/api/conversation/connect"
    if len(sys.argv) > 1:
        server_url = sys.argv[1]
    
    # 机器狗ID（可选）
    robot_id = None
    if len(sys.argv) > 2:
        robot_id = sys.argv[2]
    
    print("=" * 60)
    print("机器狗对话客户端")
    print("=" * 60)
    
    client = RobotDogClient(server_url, robot_id)
    
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序异常: {e}")


if __name__ == "__main__":
    # 运行示例：
    # python client.py
    # python client.py ws://192.168.1.100:3001/api/conversation/connect
    # python client.py ws://localhost:3001/api/conversation/connect your-robot-id
    
    asyncio.run(main())
