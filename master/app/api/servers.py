from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db
from app.models.orm import GPU, Server
from app.schemas.server import (
    GPUSummary,
    Heartbeat,
    ManualNodeCreate,
    NodeUpdate,
    ServerOut,
    ServerRegister,
)
from app.services import node_manager
from app.services.node_manager import NodeError

router = APIRouter(prefix="/api/servers", tags=["servers"])


def _verify_token(token: str) -> None:
    if token != settings.agent_auth_token:
        raise HTTPException(status_code=401, detail="invalid agent token")


@router.post("/register")
def register(payload: ServerRegister, db: Session = Depends(get_db)):
    _verify_token(payload.token)
    gpus = [g.model_dump() for g in payload.gpus]
    server = node_manager.register_server(db, payload, gpus)
    return {"id": server.id, "status": server.status}


@router.post("/manual", response_model=ServerOut)
def create_manual(payload: ManualNodeCreate, db: Session = Depends(get_db)):
    """手动登记节点（未接 Agent，供规划/预登记）。"""
    try:
        return node_manager.create_manual_node(db, payload)
    except NodeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{server_id}/heartbeat")
def heartbeat(server_id: int, payload: Heartbeat, db: Session = Depends(get_db)):
    _verify_token(payload.token)
    gpus = [g.model_dump() for g in payload.gpus]
    server = node_manager.heartbeat(db, server_id, gpus)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")
    return {"id": server.id, "status": server.status}


@router.get("", response_model=list[ServerOut])
def list_servers(db: Session = Depends(get_db)):
    return db.query(Server).order_by(Server.id).all()


@router.get("/{server_id}", response_model=ServerOut)
def get_server(server_id: int, db: Session = Depends(get_db)):
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")
    return server


@router.put("/{server_id}", response_model=ServerOut)
def update_server(server_id: int, payload: NodeUpdate, db: Session = Depends(get_db)):
    try:
        return node_manager.update_node(db, server_id, payload)
    except NodeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.delete("/{server_id}")
def delete_server(server_id: int, db: Session = Depends(get_db)):
    try:
        node_manager.delete_node(db, server_id)
    except NodeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"ok": True}


@router.get("/{server_id}/gpus", response_model=list[GPUSummary])
def list_gpus(server_id: int, db: Session = Depends(get_db)):
    server = db.get(Server, server_id)
    if server is None:
        raise HTTPException(status_code=404, detail="server not found")
    return db.query(GPU).filter(GPU.server_id == server_id).order_by(GPU.index).all()
