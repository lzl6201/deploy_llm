"""网关负载均衡：将 OpenAI 兼容请求（/v1/*）按模型名分发到健康运行实例。

服务（service）以「模型名」为键：同一模型的多个运行实例（副本）组成后端池，
按轮询（round-robin）分发。代理失败的后端进入短暂冷却，冷却期内不参与分发。
"""

from __future__ import annotations

import itertools
import time

from sqlalchemy.orm import Session

from app.models.orm import Deployment, Model, ModelVersion

# endpoint -> 冷却截止时间（秒）
_cooldown: dict[str, float] = {}
_rr = itertools.count()

COOLDOWN_SECONDS = 10.0


class GatewayError(Exception):
    """无可用后端。"""


def _running_backends(db: Session, model_name: str) -> list[tuple[int, str]]:
    """返回 (deployment_id, endpoint) 的运行实例，按模型名匹配。"""
    rows = (
        db.query(Deployment, Model.name)
        .join(ModelVersion, Deployment.model_version_id == ModelVersion.id)
        .join(Model, ModelVersion.model_id == Model.id)
        .filter(Model.name == model_name, Deployment.status == "running")
        .all()
    )
    return [(d.id, d.endpoint) for d, _ in rows if d.endpoint]


def served_models(db: Session) -> list[dict]:
    """返回当前可对外服务的模型名列表（OpenAI /v1/models 格式）。"""
    rows = (
        db.query(Model.name)
        .join(ModelVersion, ModelVersion.model_id == Model.id)
        .join(Deployment, Deployment.model_version_id == ModelVersion.id)
        .filter(Deployment.status == "running")
        .distinct()
        .all()
    )
    return [{"id": name, "object": "model", "owned_by": "deploy-llm"} for (name,) in rows]


def select_backend(db: Session, model_name: str) -> tuple[int, str]:
    """轮询选择一个健康后端；无后端时抛 :class:`GatewayError`。"""
    backends = _running_backends(db, model_name)
    now = time.time()
    healthy = [(i, ep) for i, ep in backends if _cooldown.get(ep, 0.0) <= now]
    if not healthy:
        healthy = backends  # 全部冷却时退回全量，避免无端 503
    if not healthy:
        raise GatewayError(f"模型 '{model_name}' 无可用运行实例")
    idx = next(_rr) % len(healthy)
    return healthy[idx]


def mark_down(endpoint: str, seconds: float = COOLDOWN_SECONDS) -> None:
    _cooldown[endpoint] = time.time() + seconds
