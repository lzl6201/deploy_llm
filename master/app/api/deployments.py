from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.orm import Deployment, DeployTask, ModelVersion
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentOut,
    DeploymentStatusUpdate,
    LaunchConfigOut,
    PendingDeploymentOut,
)
from app.services.engine import get_engine
from app.services.engine.base import DeployRequest

router = APIRouter(prefix="/api/deployments", tags=["deployments"])


@router.post("", response_model=DeploymentOut)
def create_deployment(payload: DeploymentCreate, db: Session = Depends(get_db)):
    mv = db.get(ModelVersion, payload.model_version_id)
    if mv is None:
        raise HTTPException(status_code=404, detail="model version not found")

    dep = Deployment(
        name=payload.name,
        model_version_id=payload.model_version_id,
        engine=payload.engine,
        format=mv.format,
        server_id=payload.server_id,
        gpu_ids=payload.gpu_ids,
        tp_size=payload.tp_size,
        pp_size=payload.pp_size,
        quant=mv.quantization,
        max_model_len=payload.max_model_len,
        port=payload.port,
        status="pending",
    )
    db.add(dep)
    db.commit()
    db.refresh(dep)

    db.add(DeployTask(deployment_id=dep.id, action="deploy", status="pending"))
    db.commit()
    return dep


@router.get("", response_model=list[DeploymentOut])
def list_deployments(db: Session = Depends(get_db)):
    return db.query(Deployment).order_by(Deployment.id.desc()).all()


@router.get("/pending", response_model=list[PendingDeploymentOut])
def pending_deployments(server_id: int, db: Session = Depends(get_db)):
    deps = (
        db.query(Deployment)
        .filter(Deployment.server_id == server_id, Deployment.status == "pending")
        .all()
    )
    result = []
    for dep in deps:
        mv = db.get(ModelVersion, dep.model_version_id)
        if mv is None:
            continue
        adapter = get_engine(dep.engine)
        req = DeployRequest(
            model_path=mv.storage_path,
            model_name=mv.model.name,
            quantization=dep.quant,
            gpu_ids=dep.gpu_ids,
            tp_size=dep.tp_size,
            pp_size=dep.pp_size,
            max_model_len=dep.max_model_len,
            port=dep.port,
            extra=dep.extra or {},
        )
        lc = adapter.build_launch_config(req)
        result.append(
            {
                "id": dep.id,
                "name": dep.name,
                "model_version_id": dep.model_version_id,
                "engine": dep.engine,
                "format": dep.format,
                "server_id": dep.server_id,
                "gpu_ids": dep.gpu_ids,
                "tp_size": dep.tp_size,
                "pp_size": dep.pp_size,
                "quant": dep.quant,
                "port": dep.port,
                "status": dep.status,
                "endpoint": dep.endpoint,
                "created_at": dep.created_at,
                "model_path": mv.storage_path,
                "model_name": mv.model.name,
                "max_model_len": dep.max_model_len,
                "extra": dep.extra or {},
                "launch_config": LaunchConfigOut(
                    command=lc.command,
                    env=lc.env,
                    port=lc.port,
                    health_check_path=lc.health_check_path,
                    container_image=lc.container_image,
                ),
            }
        )
    return result


@router.post("/{deployment_id}/status", response_model=DeploymentOut)
def update_status(
    deployment_id: int, payload: DeploymentStatusUpdate, db: Session = Depends(get_db)
):
    dep = db.get(Deployment, deployment_id)
    if dep is None:
        raise HTTPException(status_code=404, detail="deployment not found")
    dep.status = payload.status
    if payload.endpoint:
        dep.endpoint = payload.endpoint
    db.commit()
    db.refresh(dep)
    return dep


@router.post("/{deployment_id}/stop", response_model=DeploymentOut)
def stop_deployment(deployment_id: int, db: Session = Depends(get_db)):
    dep = db.get(Deployment, deployment_id)
    if dep is None:
        raise HTTPException(status_code=404, detail="deployment not found")
    dep.status = "stopping"
    db.add(DeployTask(deployment_id=deployment_id, action="stop", status="pending"))
    db.commit()
    db.refresh(dep)
    return dep
