#!/usr/bin/env python3
"""
Robot Server - 机器狗配置服务器

功能：
1. WiFi配置管理
2. 配置文件管理（读取/修改/重置）
3. 提供Web界面进行配置
4. 提供HTTP API供robot-agent调用
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import subprocess
import os
import uvicorn
from typing import Optional
from pathlib import Path

from config_manager import ConfigManager, 获取配置字段信息, CONFIG_DIR

PORT = 8080

# 创建FastAPI应用实例
app = FastAPI(title="Robot Server", description="机器狗配置服务器")

# 创建配置管理器
config_manager = ConfigManager()


# ==================== 配置API ====================

@app.get("/api/v1/config")
async def 获取全部配置():
    """获取全部配置"""
    try:
        config = config_manager.get()
        return {"success": True, "config": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)})


@app.get("/api/v1/config/fields")
async def 获取配置字段定义信息():
    """获取配置字段定义信息（用于前端展示）"""
    try:
        fields = 获取配置字段信息()
        return {"success": True, "fields": fields}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)})


@app.get("/api/v1/config/path")
async def 获取配置文件路径():
    """获取配置文件路径"""
    try:
        return {
            "success": True, 
            "config_file": str(config_manager.config_path),
            "config_dir": str(config_manager.config_dir)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)})


@app.post("/api/v1/config/reset")
async def 重置配置(request: Request):
    """重置配置为默认值"""
    try:
        data = await request.json() if request.headers.get("content-length", "0") != "0" else {}
        key = data.get("key")  # 可选，如果不提供则重置全部
        
        success = config_manager.reset(key)
        if not success:
            raise HTTPException(status_code=400, detail={"success": False, "error": f"重置失败，配置项 {key} 不存在"})
        
        return {"success": True, "message": f"配置已重置" + (f"（{key}）" if key else "（全部）")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)})


@app.post("/api/v1/config/reload")
async def 重新加载配置():
    """重新从文件加载配置"""
    try:
        config_manager.reload()
        return {"success": True, "message": "配置已重新加载"}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)})


@app.get("/api/v1/config/{key}")
async def 获取单项配置(key: str):
    """获取单项配置"""
    try:
        value = config_manager.get(key)
        if value is None:
            raise HTTPException(status_code=404, detail={"success": False, "error": f"配置项 {key} 不存在"})
        return {"success": True, "key": key, "value": value}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)})


@app.post("/api/v1/config")
async def 更新配置(request: Request):
    """更新配置（支持批量更新）"""
    try:
        data = await request.json()
        
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail={"success": False, "error": "请求数据必须是JSON对象"})
        
        results = config_manager.set_many(data)
        
        # 检查是否有失败的配置项
        failed = [k for k, v in results.items() if not v]
        if failed:
            return {
                "success": False, 
                "message": f"部分配置项更新失败: {', '.join(failed)}", 
                "results": results
            }
        
        return {"success": True, "message": "配置更新成功", "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)})


# ==================== WiFi API ====================

@app.post("/api/v1/wifi/connect")
async def 连接WIFI(request: Request):
    """连接WiFi"""
    try:
        data = await request.json()
        ssid = data.get('ssid')
        password = data.get('password')
        
        if not ssid or not password:
            return {"success": False, "error": "未提供SSID或密码"}
        
        # 连接WiFi
        connect_cmd = f"sudo nmcli device wifi connect '{ssid}' password '{password}' ifname wlan0"
        subprocess.run(connect_cmd, shell=True, check=True, capture_output=True, text=True)
        
        # 关闭网络清除服务
        subprocess.run("sudo systemctl stop networkmanager-cleanup.service", shell=True, capture_output=True, text=True)
        subprocess.run("sudo systemctl disable networkmanager-cleanup.service", shell=True, capture_output=True, text=True)
        
        # 开启自动连接
        auto_connect_cmd = f"sudo nmcli connection modify '{ssid}' connection.autoconnect yes"
        subprocess.run(auto_connect_cmd, shell=True, capture_output=True, text=True)
        
        return {"success": True, "message": "WiFi连接成功"}
    except subprocess.CalledProcessError as e:
        error_msg = f"连接失败: {e.stderr.strip()}"
        raise HTTPException(status_code=500, detail={"success": False, "error": error_msg})


@app.get("/api/v1/wifi/scan")
async def 扫描WIFI():
    """扫描WiFi网络"""
    try:
        # 扫描WiFi网络，使用-t参数获取易于解析的格式
        # 格式: IN-USE:SSID:CHAN:SIGNAL:SECURITY
        scan_cmd = "sudo nmcli -t -f IN-USE,SSID,CHAN,SIGNAL,SECURITY device wifi list"
        result = subprocess.run(scan_cmd, shell=True, check=True, capture_output=True, text=True)
        
        # 解析扫描结果
        wifi_list = []
        lines = result.stdout.strip().split('\n')
        
        for line in lines:
            if not line:
                continue
                
            # 手动解析以处理转义字符
            parts = []
            current = ''
            escaped = False
            for char in line:
                if escaped:
                    current += char
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == ':':
                    parts.append(current)
                    current = ''
                else:
                    current += char
            parts.append(current)
            
            if len(parts) >= 5:
                in_use = parts[0] == '*'
                ssid = parts[1]
                channel = parts[2]
                signal = parts[3]
                security = parts[4]
                
                # 忽略没有SSID的网络
                if not ssid:
                    continue
                    
                wifi_list.append({
                    'ssid': ssid,
                    'signal': signal,
                    'channel': channel,
                    'security': security,
                    'in_use': in_use
                })
        
        # 排序：当前连接的在最前，然后按信号强度降序
        wifi_list.sort(key=lambda x: (not x['in_use'], -int(x['signal']) if x['signal'].isdigit() else 0))
        
        return {"success": True, "networks": wifi_list}
    except subprocess.CalledProcessError as e:
        error_msg = f"扫描失败: {e.stderr.strip()}"
        raise HTTPException(status_code=500, detail={"success": False, "error": error_msg})


# ==================== 系统信息API ====================

@app.get("/api/v1/system/info")
async def 获取系统信息():
    """获取系统基本信息"""
    try:
        info = {
            "config_dir": str(CONFIG_DIR),
            "config_file": str(config_manager.config_path),
        }
        return {"success": True, "info": info}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)})


# 挂载静态文件目录
app.mount("/", StaticFiles(directory=".", html=True), name="static")


if __name__ == '__main__':
    # 确保服务器在正确的目录中运行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("正在启动机器狗配置服务器...")
    print(f"服务器运行在 http://0.0.0.0:{PORT}")
    print(f"配置文件位置: {config_manager.config_path}")
    print("请在浏览器中访问 http://<机器狗IP>:8080 进行配置")
    uvicorn.run(app, host="0.0.0.0", port=PORT)