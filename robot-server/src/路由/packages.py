"""
安装包上传接口 - 供手机端将本地安装包上传到机器人

上传单个 full 整包后，自动解出到 ~/sparkrobot/packages/
"""
import tarfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from sparkrobot_common import WORKSPACE_DIR

router = APIRouter()

_PACKAGES_DIR = WORKSPACE_DIR / "packages"
_FULL_PACKAGE_NAME = "robot-full.tar.gz"


def _解出整包内子包(full_package_path: Path) -> list[str]:
    """将 full 整包内的 packages/*.tar.gz 解到 packages 目录。"""
    extracted: list[str] = []
    with tarfile.open(full_package_path, "r:*") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            member_path = Path(member.name)
            if "packages" not in member_path.parts:
                continue
            if member_path.suffixes[-2:] != [".tar", ".gz"]:
                continue

            file_name = member_path.name
            target_path = _PACKAGES_DIR / file_name
            file_obj = tar.extractfile(member)
            if file_obj is None:
                continue
            target_path.write_bytes(file_obj.read())
            extracted.append(file_name)
    return extracted


@router.post("/api/v1/packages/upload")
async def 上传安装包(file: UploadFile) -> dict:
    """接收手机端上传的 full 整包，保存并解出到 ~/sparkrobot/packages/"""
    _PACKAGES_DIR.mkdir(parents=True, exist_ok=True)
    target: Path = _PACKAGES_DIR / _FULL_PACKAGE_NAME

    try:
        content = await file.read()
        target.write_bytes(content)
        extracted = _解出整包内子包(target)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"success": False, "error": f"保存安装包失败: {e}"},
        ) from e

    return {
        "success": True,
        "message": f"full 安装包已保存到 {target}",
        "path": str(target),
        "size": len(content),
        "extracted": extracted,
    }
