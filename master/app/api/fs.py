from fastapi import APIRouter, HTTPException, Query

from app.services import fs
from app.services.gguf import GGUFError, parse_gguf

router = APIRouter(prefix="/api/fs", tags=["filesystem"])


@router.get("/roots")
def fs_roots():
    return fs.list_roots()


@router.get("/list")
def fs_list(path: str = Query(..., description="目录绝对路径")):
    try:
        current, entries = fs.list_dir(path)
    except fs.FSPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {
        "path": current,
        "entries": [
            {
                "name": e.name,
                "path": e.path,
                "type": e.type,
                "size_bytes": e.size_bytes,
                "is_gguf": e.is_gguf,
            }
            for e in entries
        ],
    }


@router.get("/inspect")
def fs_inspect(path: str = Query(..., description="GGUF 文件绝对路径")):
    try:
        fs._assert_allowed(path)
        return parse_gguf(path).to_dict()
    except fs.FSPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except GGUFError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
