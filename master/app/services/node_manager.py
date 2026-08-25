from datetime import datetime

from sqlalchemy.orm import Session

from app.models.orm import Deployment, GPU, Server


class NodeError(Exception):
    """节点管理操作失败（重名 / 存在部署 / 不存在等）。"""


def _upsert_gpus(server: Server, gpus: list[dict]) -> None:
    """以 index 为键重建 GPU 快照。"""
    by_index = {g.index: g for g in server.gpus}
    new_gpus = []
    for item in gpus:
        gpu = by_index.get(item["index"])
        if gpu is None:
            gpu = GPU(index=item["index"], server_id=server.id)
        gpu.name = item.get("name")
        gpu.vram_total_mb = item.get("vram_total_mb", 0)
        gpu.vram_used_mb = item.get("vram_used_mb", 0)
        gpu.utilization = item.get("utilization", 0.0)
        gpu.temperature = item.get("temperature", 0.0)
        gpu.power_w = item.get("power_w", 0.0)
        new_gpus.append(gpu)
    server.gpus = new_gpus
    server.total_gpus = len(new_gpus)


def register_server(db: Session, payload, gpus: list[dict]) -> Server:
    server = db.query(Server).filter(Server.hostname == payload.hostname).first()
    if server is None:
        server = Server(hostname=payload.hostname)
        db.add(server)

    server.ip = payload.ip
    server.token = payload.token
    server.driver = payload.driver
    server.cuda = payload.cuda
    server.interconnect = payload.interconnect or "pcie"
    server.status = "online"
    server.source = "agent"  # Agent 接管后，即便此前手动登记也标记为 agent
    server.last_seen = datetime.utcnow()

    _upsert_gpus(server, gpus)

    db.commit()
    db.refresh(server)
    return server


def heartbeat(db: Session, server_id: int, gpus: list[dict]) -> Server | None:
    server = db.get(Server, server_id)
    if server is None:
        return None

    server.last_seen = datetime.utcnow()
    server.status = "online"
    server.source = "agent"
    _upsert_gpus(server, gpus)

    db.commit()
    db.refresh(server)
    return server


def create_manual_node(db: Session, payload) -> Server:
    """手动登记节点（未接 Agent）。hostname 唯一。"""
    existing = db.query(Server).filter(Server.hostname == payload.hostname).first()
    if existing is not None:
        raise NodeError(f"节点已存在: {payload.hostname}")

    server = Server(
        hostname=payload.hostname,
        ip=payload.ip,
        driver=payload.driver,
        cuda=payload.cuda,
        interconnect=payload.interconnect or "pcie",
        status="offline",
        source="manual",
    )
    db.add(server)
    db.flush()
    _upsert_gpus(server, [g.model_dump() for g in payload.gpus])
    db.commit()
    db.refresh(server)
    return server


def update_node(db: Session, server_id: int, payload) -> Server:
    server = db.get(Server, server_id)
    if server is None:
        raise NodeError("节点不存在")

    if payload.hostname is not None and payload.hostname != server.hostname:
        dup = (
            db.query(Server)
            .filter(Server.hostname == payload.hostname, Server.id != server_id)
            .first()
        )
        if dup is not None:
            raise NodeError(f"hostname 已被占用: {payload.hostname}")
        server.hostname = payload.hostname

    if payload.ip is not None:
        server.ip = payload.ip
    if payload.driver is not None:
        server.driver = payload.driver
    if payload.cuda is not None:
        server.cuda = payload.cuda
    if payload.interconnect is not None:
        server.interconnect = payload.interconnect
    if payload.gpus is not None:
        _upsert_gpus(server, [g.model_dump() for g in payload.gpus])

    db.commit()
    db.refresh(server)
    return server


def delete_node(db: Session, server_id: int) -> None:
    server = db.get(Server, server_id)
    if server is None:
        raise NodeError("节点不存在")

    dep_count = (
        db.query(Deployment).filter(Deployment.server_id == server_id).count()
    )
    if dep_count > 0:
        raise NodeError(f"该节点存在 {dep_count} 个部署任务，请先删除或迁移部署后再删除节点")

    db.delete(server)
    db.commit()
