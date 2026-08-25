from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.orm import Deployment, DeployTask, ModelVersion
from app.schemas.deployment import (
    DeploymentCreate,
    DeploymentOut,
    DeploymentStatusUpdate,
    LaunchConfigOut,
    PendingDeploymentOut,
    PlacementOut,
    PlacementRequest,
    ScaleRequest,
)
from app.services import scheduler
from app.services.engine import get_engine
from app.services.engine.base import DeployRequest
from app.services.model_meta import model_version_input
from app.services.recommend_engine import _engine_for

router = APIRouter(prefix="/api/deployments", tags=["deployments"])


@router.post("/place", response_model=list[PlacementOut])
def preview_placement(payload: PlacementRequest, db: Session = Depends(get_db)):
    """放置预览：返回按分数降序的候选节点（不落库）。"""
    mv = db.get(ModelVersion, payload.model_version_id)
    if mv is None:
        raise HTTPException(status_code=404, detail="model version not found")
    return scheduler.candidates(
        db, mv, payload.tp_size or 1, payload.max_model_len, payload.server_id
    )


@router.post("", response_model=DeploymentOut)
def create_deployment(payload: DeploymentCreate, db: Session = Depends(get_db)):
    mv = db.get(ModelVersion, payload.model_version_id)
    if mv is None:
        raise HTTPException(status_code=404, detail="model version not found")

    engine = payload.engine or _engine_for(model_version_input(mv))
    tp_size = payload.tp_size or 1

    # 放置：未指定节点则全集群自动选；指定节点但未选卡则由调度器补卡
    try:
        if payload.server_id is None:
            placement = scheduler.pick_best(db, mv, tp_size, payload.max_model_len)
            server_id = placement.server_id
            gpu_ids = payload.gpu_ids or placement.gpu_ids
        else:
            server_id = payload.server_id
            gpu_ids = payload.gpu_ids
            if not gpu_ids:
                placement = scheduler.pick_best(
                    db, mv, tp_size, payload.max_model_len, server_id=server_id
                )
                gpu_ids = placement.gpu_ids
    except scheduler.PlacementError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    dep = Deployment(
        name=payload.name,
        model_version_id=payload.model_version_id,
        engine=engine,
        format=mv.format,
        server_id=server_id,
        gpu_ids=gpu_ids,
        tp_size=tp_size,
        pp_size=payload.pp_size,
        quant=mv.quantization,
        max_model_len=payload.max_model_len,
        port=payload.port,
        container_image=payload.container_image,
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


@router.get("/stopping", response_model=list[DeploymentOut])
def stopping_deployments(server_id: int, db: Session = Depends(get_db)):
    """Agent 拉取待停止的部署（status=stopping），停进程后回传 stopped。"""
    return (
        db.query(Deployment)
        .filter(Deployment.server_id == server_id, Deployment.status == "stopping")
        .all()
    )


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
        default_image = {
            "vllm": settings.vllm_container_image,
            "llama.cpp": settings.llama_cpp_container_image,
        }.get(dep.engine, "")
        container_image = dep.container_image or default_image or ""
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
            container_image=container_image,
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
                "container_image": dep.container_image,
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
    if payload.detail:
        dep.last_error = payload.detail

    # 收到 stopped：完成对应 stop/restart 任务；restart 则重新进入 pending 拉起
    if payload.status == "stopped":
        tasks = (
            db.query(DeployTask)
            .filter(
                DeployTask.deployment_id == deployment_id,
                DeployTask.action.in_(["stop", "restart"]),
                DeployTask.status == "pending",
            )
            .all()
        )
        restart = any(t.action == "restart" for t in tasks)
        for t in tasks:
            t.status = "done"
        if restart:
            dep.status = "pending"
            dep.endpoint = None
            db.add(
                DeployTask(deployment_id=deployment_id, action="deploy", status="pending")
            )

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


@router.post("/{deployment_id}/restart", response_model=DeploymentOut)
def restart_deployment(deployment_id: int, db: Session = Depends(get_db)):
    """重启：先停（stopping），Agent 停进程回传 stopped 后自动重新拉起。"""
    dep = db.get(Deployment, deployment_id)
    if dep is None:
        raise HTTPException(status_code=404, detail="deployment not found")
    if dep.status in ("pending", "stopping"):
        raise HTTPException(status_code=409, detail=f"当前状态 {dep.status} 无法重启")
    dep.status = "stopping"
    db.add(DeployTask(deployment_id=deployment_id, action="restart", status="pending"))
    db.commit()
    db.refresh(dep)
    return dep


def _place_replica(db, mv, tp_size, max_model_len, server_id):
    """副本放置：优先与模板同节点，放不下则回退全局。"""
    try:
        return scheduler.pick_best(db, mv, tp_size, max_model_len, server_id=server_id)
    except scheduler.PlacementError:
        if server_id is None:
            raise
        return scheduler.pick_best(db, mv, tp_size, max_model_len, server_id=None)


@router.post("/{deployment_id}/scale")
def scale_deployment(
    deployment_id: int, payload: ScaleRequest, db: Session = Depends(get_db)
):
    """副本扩缩：将「同 model_version + engine」的副本数调整为目标值。"""
    if payload.replicas < 1:
        raise HTTPException(status_code=422, detail="replicas 至少为 1")

    template = db.get(Deployment, deployment_id)
    if template is None:
        raise HTTPException(status_code=404, detail="deployment not found")
    mv = db.get(ModelVersion, template.model_version_id)

    group = (
        db.query(Deployment)
        .filter(
            Deployment.model_version_id == template.model_version_id,
            Deployment.engine == template.engine,
        )
        .all()
    )
    active = [d for d in group if d.status not in ("stopped", "failed")]
    active.sort(key=lambda d: d.id)

    if len(active) < payload.replicas:
        created = _scale_up(
            db, template, mv, payload.replicas - len(active), len(active)
        )
        db.commit()
        return {"replicas": payload.replicas, "created": created, "stopped": []}

    if len(active) > payload.replicas:
        excess = active[-(len(active) - payload.replicas):]
        for d in excess:
            d.status = "stopping"
            db.add(DeployTask(deployment_id=d.id, action="stop", status="pending"))
        db.commit()
        return {"replicas": payload.replicas, "created": [], "stopped": [d.id for d in excess]}

    return {"replicas": payload.replicas, "created": [], "stopped": []}


def _scale_up(db, template, mv, count, base_seq):
    created = []
    tp_size = template.tp_size or 1
    for j in range(count):
        placement = _place_replica(
            db, mv, tp_size, template.max_model_len, template.server_id
        )
        dep = Deployment(
            name=template.name,
            model_version_id=template.model_version_id,
            engine=template.engine,
            format=template.format,
            server_id=placement.server_id,
            gpu_ids=placement.gpu_ids,
            tp_size=template.tp_size,
            pp_size=template.pp_size,
            quant=template.quant,
            max_model_len=template.max_model_len,
            port=template.port + base_seq + j + 1,
            extra=template.extra or {},
            container_image=template.container_image,
            status="pending",
        )
        db.add(dep)
        db.flush()
        dep.name = f"{template.name}-{dep.id}"
        db.add(DeployTask(deployment_id=dep.id, action="deploy", status="pending"))
        created.append(dep.id)
    return created
