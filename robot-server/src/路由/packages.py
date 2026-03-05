"""
安装包上传接口 - 供手机端将本地安装包上传到机器人

上传后存放到 ~/sparkrobot/packages/{robot-agent|robot-server|sparkrobot-common}.tar.gz
"""
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from sparkrobot_common import WORKSPACE_DIR

router = APIRouter()

# 包类型到目标文件名的映射
_PACKAGE_FILENAMES = {
    "agent": "robot-agent.tar.gz",
    "server": "robot-server.tar.gz",
    "common": "sparkrobot-common.tar.gz",
}

_PACKAGES_DIR = WORKSPACE_DIR / "packages"


@router.post("/api/v1/packages/upload")
async def 上传安装包(type: str, file: UploadFile) -> dict:
    """接收手机端上传的安装包文件，保存到 ~/sparkrobot/packages/"""
    if type not in _PACKAGE_FILENAMES:
        raise HTTPException(
            status_code=400,
            detail={"success": False, "error": f"无效的包类型: {type}，必须是 agent、server 或 common"},
        )

    _PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    target: Path = _PACKAGES_DIR / _PACKAGE_FILENAMES[type]

    try:
        content = await file.read()
        target.write_bytes(content)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": f"保存安装包失败: {e}"},
        ) from e

    return {
        "success": True,
        "message": f"{type} 安装包已保存到 {target}",
        "path": str(target),
        "size": len(content),
    }
