from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..服务.map_service import 获取地图服务单例

router = APIRouter()
map_service = 获取地图服务单例()


@router.get("/api/v1/maps")
async def 获取地图列表() -> dict:
    try:
        return {
            "success": True,
            "data": {
                "map_dir": str(map_service.获取地图目录()),
                "maps": map_service.获取地图列表(),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e


@router.get("/api/v1/maps/{map_id:path}/download")
async def 下载地图(map_id: str) -> Response:
    try:
        zip_data, file_name = map_service.打包地图(map_id)
        encoded_file_name = quote(file_name)
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_file_name}",
        }
        return Response(content=zip_data, media_type="application/zip", headers=headers)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"success": False, "error": str(e)}) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"success": False, "error": str(e)}) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail={"success": False, "error": str(e)}) from e
