from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.orm import ModelVersion, QuantizeJob
from app.schemas.quantize import (
    PendingQuantizeOut,
    QuantizeCreate,
    QuantizeOut,
    QuantizeStatusUpdate,
)
from app.services.gguf import GGUFError, parse_gguf
from app.services.quantize import build_quantize_command

router = APIRouter(prefix="/api/quantize", tags=["quantize"])


@router.post("", response_model=QuantizeOut)
def create_quantize(payload: QuantizeCreate, db: Session = Depends(get_db)):
    mv = db.get(ModelVersion, payload.model_version_id)
    if mv is None:
        raise HTTPException(status_code=404, detail="model version not found")
    if mv.format != "gguf":
        raise HTTPException(status_code=400, detail="仅 GGUF 模型支持在线量化")

    qc = build_quantize_command(mv.storage_path, payload.target_quant)
    job = QuantizeJob(
        model_version_id=mv.id,
        method="llama-quantize",
        target_quant=payload.target_quant,
        server_id=payload.server_id,
        source_path=qc.source_path,
        target_path=qc.target_path,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[QuantizeOut])
def list_quantize(db: Session = Depends(get_db)):
    return db.query(QuantizeJob).order_by(QuantizeJob.id.desc()).all()


@router.get("/pending", response_model=list[PendingQuantizeOut])
def pending_quantize(server_id: int, db: Session = Depends(get_db)):
    jobs = (
        db.query(QuantizeJob)
        .filter(QuantizeJob.server_id == server_id, QuantizeJob.status == "pending")
        .all()
    )
    result = []
    for job in jobs:
        qc = build_quantize_command(job.source_path, job.target_quant)
        result.append(
            {
                "id": job.id,
                "model_version_id": job.model_version_id,
                "method": job.method,
                "target_quant": job.target_quant,
                "server_id": job.server_id,
                "source_path": job.source_path,
                "target_path": job.target_path,
                "status": job.status,
                "progress": job.progress,
                "error": job.error,
                "created_at": job.created_at,
                "command": qc.command,
            }
        )
    return result


@router.post("/{job_id}/status", response_model=QuantizeOut)
def update_quantize(
    job_id: int, payload: QuantizeStatusUpdate, db: Session = Depends(get_db)
):
    job = db.get(QuantizeJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    job.status = payload.status
    if payload.progress is not None:
        job.progress = payload.progress
    if payload.error is not None:
        job.error = payload.error
    if payload.target_path:
        job.target_path = payload.target_path
    db.commit()
    db.refresh(job)

    # 量化完成后，自动将产物注册为同模型的新版本，使其可直接部署
    if job.status == "done" and job.target_path:
        _register_quantized_version(db, job)

    return job


def _register_quantized_version(db: Session, job: QuantizeJob) -> None:
    try:
        exists = (
            db.query(ModelVersion)
            .filter(ModelVersion.storage_path == job.target_path)
            .first()
        )
        if exists:
            return
        source_mv = db.get(ModelVersion, job.model_version_id)
        if source_mv is None:
            return
        info = parse_gguf(job.target_path)
        new_mv = ModelVersion(
            model_id=source_mv.model_id,
            version=f"{source_mv.version}-{job.target_quant}",
            quantization=info.file_type_label or job.target_quant,
            dtype="F16",
            format="gguf",
            architecture=info.architecture,
            gguf_file_type=info.file_type,
            storage_path=job.target_path,
            size_gb=round(info.file_size_bytes / (1024**3), 3),
            file_size_mb=int(info.file_size_bytes // (1024 * 1024)),
        )
        db.add(new_mv)
        db.commit()
    except (GGUFError, OSError):
        db.rollback()
