import uvicorn

from src.app import PORT, app
from src.服务.config_service import 获取配置管理器单例

if __name__ == "__main__":
    config_manager = 获取配置管理器单例()

    print( "\033[32mINFO\033[0m:     正在启动机器狗配置服务器...")
    print(f"\033[32mINFO\033[0m:     服务器运行在 http://0.0.0.0:{PORT}")
    print(f"\033[32mINFO\033[0m:     配置文件位置: {config_manager.config_path}")
    print( "\033[32mINFO\033[0m:     请在浏览器中访问 http://<机器狗IP>:8080 进行配置")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
