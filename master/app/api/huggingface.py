from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.orm import DownloadJob
from app.schemas.huggingface import (
    DownloadCreate,
    DownloadOut,
    HfFileOut,
    HfModelOut,
)
from app.services import huggingface as hf
from app.services.downloader import start_download_job
from app.config import settings

router = APIRouter(prefix="/api/hf", tags=["huggingface"])


@router.get("/search", response_model=list[HfModelOut])
def search(query: str = Query(...), limit: int = 20, sort: str = "downloads"):
    try:
        return hf.search_models(query, limit, sort)
    except hf.HFError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/orgs")
def list_orgs():
    return {"orgs": hf.GGUF_ORGS}


@router.get("/org/{org}", response_model=list[HfModelOut])
def org_models(org: str, limit: int = 20):
    try:
        return hf.list_org_models(org, limit)
    except hf.HFError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/models/{repo_id:path}/files", response_model=list[HfFileOut])
def model_files(repo_id: str):
    try:
        return hf.get_model_files(repo_id)
    except hf.HFError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/download", response_model=DownloadOut)
def create_download(payload: DownloadCreate, db: Session = Depends(get_db)):
    filename = payload.filename.replace("\\", "/").split("/")[-1]
    if not filename or filename in (".", ".."):
        raise HTTPException(status_code=400, detail="无效的文件名")
    # 仓库 id 只保留 org/repo 形式，去除路径穿越字符
    repo_id = payload.repo_id.replace("\\", "/").strip("/")
    parts = [p for p in repo_id.split("/") if p not in ("", ".", "..")]
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="无效的仓库 id")
    repo_id = "/".join(parts)
    dest = f"{settings.hf_download_dir.rstrip('/')}/hf/{repo_id}/{filename}"
    job = DownloadJob(
        repo_id=repo_id,
        filename=filename,
        dest_path=dest,
        size_bytes=payload.size_bytes,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    start_download_job(job.id)
    return job


@router.get("/downloads", response_model=list[DownloadOut])
def list_downloads(db: Session = Depends(get_db)):
    return db.query(DownloadJob).order_by(DownloadJob.id.desc()).all()


@router.get("/downloads/{job_id}", response_model=DownloadOut)
def download_detail(job_id: int, db: Session = Depends(get_db)):
    job = db.get(DownloadJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="download job not found")
    return job
