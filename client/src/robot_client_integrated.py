#!/usr/bin/env python3
"""
机器狗客户端 - 集成示例
演示如何将客户端与实际的机器狗 SDK 集成
"""

import asyncio
import sys
from pathlib import Path

# 导入客户端
from robot_client import RobotClient

# 如果有机器狗 SDK，在这里导入
# from robot_sdk import RobotController

class RobotActionExecutor:
    """机器狗动作执行器"""
    
    def __init__(self):
        # 初始化机器狗 SDK
        # self.robot = RobotController()
        pass
    
    async def execute(self, action: str, parameters: dict) -> bool:
        """执行动作
        
        Args:
            action: 动作名称，如 'stand_up', 'sit_down', 'walk_forward' 等
            parameters: 动作参数
            
        Returns:
            执行是否成功
        """
        print(f"\n[执行动作] {action}")
        print(f"[参数] {parameters}")
        
        try:
            # 根据动作类型调用对应的 SDK 方法
            if action == 'stand_up':
                # self.robot.stand_up()
                print("机器狗站起")
                
            elif action == 'sit_down':
                # self.robot.sit_down()
                print("机器狗坐下")
                
            elif action == 'walk_forward':
                distance = parameters.get('distance', 1.0)
                # self.robot.walk_forward(distance)
                print(f"机器狗前进 {distance} 米")
                
            elif action == 'turn':
                angle = parameters.get('angle', 90)
                # self.robot.turn(angle)
                print(f"机器狗转向 {angle} 度")
                
            elif action == 'wave':
                # self.robot.wave()
                print("机器狗挥手")
                
            elif action == 'dance':
                # self.robot.dance()
                print("机器狗跳舞")
                
            else:
                print(f"未知动作: {action}")
                return False
            
            return True
            
        except Exception as e:
            print(f"执行动作失败: {e}")
            return False


async def main():
    """主函数"""
    print("=" * 50)
    print("  机器狗客户端 - 集成版本")
    print("=" * 50)
    print()
    
    # 创建客户端
    client = RobotClient()
    
    # 创建动作执行器
    executor = RobotActionExecutor()
    
    # 设置动作执行器
    client.set_action_executor(executor.execute)
    
    print(f"配置文件: {client.config_file}")
    print(f"日志目录: {client.log_dir}")
    print(f"机器狗 UUID: {client.config['robot']['uuid']}")
    print(f"机器狗名称: {client.config['robot']['name']}")
    print()
    
    # 运行客户端
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\n客户端已停止")


if __name__ == '__main__':
    asyncio.run(main())
