from fastapi import APIRouter

from app.services.engine import list_engines

router = APIRouter(prefix="/api/engines", tags=["engines"])


@router.get("")
def engines():
    return list_engines()
