#!/usr/bin/env python3
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
import subprocess
import os
import uvicorn

PORT = 8080

# 创建FastAPI应用实例
app = FastAPI()

# 连接WiFi的POST端点
@app.post("/api/v1/wifi/connect")
async def connect_wifi(request: Request):
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

# 扫描WiFi的GET端点
@app.get("/api/v1/wifi/scan")
async def scan_wifi():
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

# 挂载静态文件目录
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == '__main__':
    # 确保服务器在正确的目录中运行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print("正在启动机器狗WiFi设置服务器...")
    print(f"服务器运行在 http://0.0.0.0:{PORT}")
    print("请在浏览器中访问 http://<机器狗IP>:8080 来设置WiFi")
    uvicorn.run(app, host="0.0.0.0", port=PORT)