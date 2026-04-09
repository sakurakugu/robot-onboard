"""遥测 API 路由

端点：
  GET /api/v1/telemetry
    返回机器狗当前状态快照，包括 power、temp、online 等字段。
    数据由 telemetry_service 后台线程持续更新。

  GET /api/v1/telemetry/full
    返回各类遥测包的最新缓存，包括 imu_info、odom_info、feedback、
    navigation_state、dog_state、bridge_status 等。

响应示例：
  {
    "success": true,
    "data": {
      "online": true,
      "power": 98,
      "temp": 67.4,
      "speed": -0.00067,
      "angle": -0.4166,
      "model": "XG",
      "dev_name": "D100076",
      "sn": "...",
      "mac": "...",
      "ssid": "D100076"
    }
  }
"""

from fastapi import APIRouter

from ..服务 import telemetry_service

router = APIRouter()


@router.get("/api/v1/telemetry")
async def 获取遥测数据() -> dict:
    """返回机器狗最新实时遥测状态（power / temp / online 等）。"""
    data = telemetry_service.获取遥测数据()
    return {"success": True, "data": data}


@router.get("/api/v1/telemetry/full")
async def 获取完整遥测数据() -> dict:
    """返回机器狗完整遥测快照。"""
    data = telemetry_service.获取完整遥测数据()
    return {"success": True, "data": data}
