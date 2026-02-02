import subprocess

from fastapi import APIRouter, HTTPException, Request

from ..服务.wifi_service import 扫描WiFi, 连接WiFi

router = APIRouter()


@router.post("/api/v1/wifi/connect")
async def 连接WIFI(request: Request):
    try:
        data = await request.json()
        ssid = data.get("ssid")
        password = data.get("password")

        if not ssid or not password:
            return {"success": False, "error": "未提供SSID或密码"}

        连接WiFi(ssid, password)

        return {"success": True, "message": "WiFi连接成功"}
    except subprocess.CalledProcessError as e:
        error_msg = f"连接失败: {e.stderr.strip()}"
        raise HTTPException(status_code=500, detail={"success": False, "error": error_msg}) from e


@router.get("/api/v1/wifi/scan")
async def 扫描WIFI():
    try:
        wifi_list = 扫描WiFi()
        return {"success": True, "networks": wifi_list}
    except subprocess.CalledProcessError as e:
        error_msg = f"扫描失败: {e.stderr.strip()}"
        raise HTTPException(status_code=500, detail={"success": False, "error": error_msg}) from e
