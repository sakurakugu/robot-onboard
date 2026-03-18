import uvicorn
from sparkrobot_common import configure_logger, get_logger

from src.app import PORT, app
from src.服务.config_service import 获取配置管理器单例

APP_NAME = "robot-server"

if __name__ == "__main__":
    config_manager = 获取配置管理器单例()
    config = config_manager.获取()
    logging_cfg = config.get("logging", {})
    configure_logger(
        app_name=APP_NAME,
        log_dir=logging_cfg.get("log_dir"),
        level=logging_cfg.get("level", "INFO"),
        max_file_size_mb=logging_cfg.get("max_file_size_mb"),
        log_file_prefix=APP_NAME,
    )
    logger = get_logger(APP_NAME)

    logger.info("正在启动机器狗配置服务器...")
    logger.info(f"服务器运行在 http://0.0.0.0:{PORT}")
    logger.info(f"配置文件位置: {config_manager.config_path}")
    logger.info("请在浏览器中访问 http://<机器狗IP>:8080 进行配置")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
