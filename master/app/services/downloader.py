"""HF 模型下载后台任务。

下载在 Master 执行（Master 挂载共享模型存储，且可直连 hf-mirror 镜像）。
每个任务起一个守护线程：流式下载到 `.part`，周期性回写进度，完成后
`os.replace` 到目标路径，若为 GGUF 则自动解析并注册为模型版本。
"""

from __future__ import annotations

import os
import threading

from app.db.session import SessionLocal
from app.models.orm import DownloadJob
from app.services.huggingface import download_to_file
from app.services.model_registry import register_gguf


def start_download_job(job_id: int) -> None:
    """启动后台下载线程（不阻塞请求线程）。"""
    t = threading.Thread(target=run_download_job, args=(job_id,), daemon=True)
    t.start()


def run_download_job(job_id: int) -> None:
    db = SessionLocal()
    job = db.get(DownloadJob, job_id)
    if job is None:
        db.close()
        return
    repo_id = job.repo_id
    filename = job.filename
    dest_path = job.dest_path
    expected_size = job.size_bytes
    job.status = "running"
    job.progress = 0.0
    db.commit()
    db.close()

    def on_progress(downloaded: int, total: int) -> None:
        _update_progress(job_id, downloaded, total)

    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        downloaded = download_to_file(
            repo_id, filename, dest_path, on_progress, expected_size=expected_size
        )
        os.replace(dest_path + ".part", dest_path)
        _finish_done(job_id, dest_path, downloaded)
    except Exception as exc:  # noqa: BLE001 - 后台任务需兜底记录失败
        _finish_failed(job_id, str(exc))


def _update_progress(job_id: int, downloaded: int, total: int) -> None:
    db = SessionLocal()
    job = db.get(DownloadJob, job_id)
    if job is None:
        db.close()
        return
    job.downloaded_bytes = downloaded
    if total > 0:
        job.size_bytes = total
        job.progress = round(downloaded * 100.0 / total, 1)
    db.commit()
    db.close()


def _finish_done(job_id: int, dest_path: str, downloaded: int) -> None:
    model_version_id = None
    err = None
    if dest_path.lower().endswith(".gguf"):
        db = SessionLocal()
        try:
            model = register_gguf(db, dest_path, version="v1", source="huggingface")
            model_version_id = model.id
        except Exception as exc:  # noqa: BLE001 - 注册失败不阻断下载完成态
            err = f"下载完成，但 GGUF 注册失败: {exc}"
        finally:
            db.close()

    db = SessionLocal()
    job = db.get(DownloadJob, job_id)
    if job is None:
        db.close()
        return
    job.status = "done"
    job.progress = 100.0
    job.downloaded_bytes = downloaded
    if downloaded > 0 and (job.size_bytes or 0) < downloaded:
        job.size_bytes = downloaded
    job.model_version_id = model_version_id
    if err:
        job.error = err
    db.commit()
    db.close()


def _finish_failed(job_id: int, error: str) -> None:
    db = SessionLocal()
    job = db.get(DownloadJob, job_id)
    if job is None:
        db.close()
        return
    job.status = "failed"
    job.error = error
    db.commit()
    db.close()
