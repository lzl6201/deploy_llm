from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.orm import Model, ModelVersion
from app.schemas.model import (
    ModelCreate,
    ModelImportRequest,
    ModelOut,
    ModelVersionCreate,
    ModelVersionOut,
)
from app.services import fs
from app.services.gguf import GGUFError
from app.services.model_registry import register_gguf

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("", response_model=list[ModelOut])
def list_models(db: Session = Depends(get_db)):
    return db.query(Model).order_by(Model.id).all()


@router.post("", response_model=ModelOut)
def create_model(payload: ModelCreate, db: Session = Depends(get_db)):
    model = Model(**payload.model_dump())
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


@router.post("/import", response_model=ModelOut)
def import_model(payload: ModelImportRequest, db: Session = Depends(get_db)):
    """导入 GGUF 文件：解析元数据后自动建模型 + 首个版本（同名则追加版本）。"""
    try:
        fs._assert_allowed(payload.path)
        return register_gguf(
            db, payload.path, version=payload.version, source=payload.source
        )
    except fs.FSPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except GGUFError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/{model_id}", response_model=ModelOut)
def get_model(model_id: int, db: Session = Depends(get_db)):
    model = db.get(Model, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="model not found")
    return model


@router.post("/{model_id}/versions", response_model=ModelVersionOut)
def add_version(model_id: int, payload: ModelVersionCreate, db: Session = Depends(get_db)):
    model = db.get(Model, model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="model not found")
    version = ModelVersion(model_id=model_id, **payload.model_dump())
    db.add(version)
    db.commit()
    db.refresh(version)
    return version
