from lib.api import CrazyRobotDog
import time

# 初始化85号狗
dog_76 = CrazyRobotDog(
    name='76',               # 名称，用于日志输出
    robot_ip='192.168.234.1',   # 机器人IP
    local_port=43988,          # 本地端口，一般设置为 `10000 + 狗狗编号`
    local_ip='192.168.234.1'
)

# dog_69 = CrazyRobotDog(
#     name='69',               # 名称，用于日志输出
#     robot_ip='192.168.0.89',   # 机器人IP
#     local_port=10069          # 本地端口，一般设置为 `10000 + 狗狗编号`
# )

# 让狗站立（大约花费4.5秒）
dog_76.stand_up(4.5)
# time.sleep(0.8)
# dog_76.nod_up(2)
# dog_76.nod_down(2)
# dog_69.stand_up()
