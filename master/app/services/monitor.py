"""监控聚合 + 告警：基于 Agent 心跳采集的 GPU 指标与部署状态评估告警规则。

告警为有状态模型：条件持续时告警保持 open，条件解除后自动 resolved，
以 dedup_key 去重（同一条件只产生一条 open 告警）。告警规则：
- 节点心跳丢失（critical）
- GPU 显存占用 > 阈值（critical，OOM 风险）
- GPU 温度 > 阈值（warning）
- GPU 利用率异常低（info，浪费提示）
- 部署失败 / 引擎 OOM（critical/warning）
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import SessionLocal
from app.models.orm import Alert, Deployment, GPU, Server

logger = logging.getLogger("monitor")


def _raise_or_keep(db: Session, dedup_key: str, server_id, type_, severity, message) -> None:
    exists = (
        db.query(Alert)
        .filter(Alert.dedup_key == dedup_key, Alert.status == "open")
        .first()
    )
    if exists is None:
        db.add(
            Alert(
                server_id=server_id,
                dedup_key=dedup_key,
                type=type_,
                severity=severity,
                message=message,
            )
        )


def _resolve(db: Session, dedup_key: str) -> None:
    for a in db.query(Alert).filter(Alert.dedup_key == dedup_key, Alert.status == "open").all():
        a.status = "resolved"
        a.resolved_at = datetime.utcnow()


def _nodes_with_running(db: Session) -> set[int]:
    return {
        d.server_id
        for d in db.query(Deployment).filter(Deployment.status == "running").all()
        if d.server_id is not None
    }


def evaluate_alerts(db: Session) -> None:
    """评估全部告警规则；调用方负责 commit。"""
    now = datetime.utcnow()

    # 1. 节点心跳丢失
    for srv in db.query(Server).all():
        key = f"heartbeat_lost:{srv.id}"
        if srv.last_seen is None:
            _resolve(db, key)
            continue
        age = (now - srv.last_seen).total_seconds()
        if srv.status != "offline" and age > settings.heartbeat_timeout:
            _raise_or_keep(
                db, key, srv.id, "heartbeat_lost", "critical",
                f"节点 {srv.hostname} 心跳丢失（{int(age)}s 未上报）",
            )
        else:
            _resolve(db, key)

    # 2. GPU 显存 / 温度
    for gpu in db.query(GPU).all():
        srv = db.get(Server, gpu.server_id)
        host = srv.hostname if srv else f"server{gpu.server_id}"
        vram_pct = (gpu.vram_used_mb / gpu.vram_total_mb * 100) if gpu.vram_total_mb else 0.0

        vkey = f"gpu_vram_high:{gpu.server_id}:{gpu.index}"
        if vram_pct > settings.vram_alert_pct:
            _raise_or_keep(
                db, vkey, gpu.server_id, "gpu_vram_high", "critical",
                f"{host} GPU{gpu.index} 显存占用 {vram_pct:.1f}%（>{settings.vram_alert_pct:.0f}%）",
            )
        else:
            _resolve(db, vkey)

        tkey = f"gpu_temp_high:{gpu.server_id}:{gpu.index}"
        if gpu.temperature > settings.temp_alert_c:
            _raise_or_keep(
                db, tkey, gpu.server_id, "gpu_temp_high", "warning",
                f"{host} GPU{gpu.index} 温度 {gpu.temperature:.0f}℃（>{settings.temp_alert_c:.0f}℃）",
            )
        else:
            _resolve(db, tkey)

    # 3. GPU 利用率异常低（浪费提示，仅对承载运行实例的在线节点）
    nodes_with_deploy = _nodes_with_running(db)
    for srv in db.query(Server).filter(Server.status == "online").all():
        key = f"gpu_idle:{srv.id}"
        gpus = list(srv.gpus)
        if srv.id in nodes_with_deploy and gpus:
            avg = sum(g.utilization for g in gpus) / len(gpus)
            if avg < settings.gpu_idle_pct:
                _raise_or_keep(
                    db, key, srv.id, "gpu_idle", "info",
                    f"节点 {srv.hostname} 有运行实例但 GPU 平均利用率仅 {avg:.1f}%（浪费提示）",
                )
                continue
        _resolve(db, key)

    # 4. 部署失败 / 引擎 OOM
    failed = {
        d.id: d
        for d in db.query(Deployment).filter(Deployment.status == "failed").all()
    }
    for dep_id, dep in failed.items():
        err = (dep.last_error or "").lower()
        if "oom" in err or "out of memory" in err:
            key = f"deploy_oom:{dep_id}"
            _raise_or_keep(
                db, key, dep.server_id, "deploy_oom", "critical",
                f"部署 {dep.name} 引擎 OOM：{dep.last_error}",
            )
        else:
            key = f"deploy_failed:{dep_id}"
            _raise_or_keep(
                db, key, dep.server_id, "deploy_failed", "warning",
                f"部署 {dep.name} 失败：{dep.last_error or '未知原因'}",
            )
    # 解除已恢复的部署告警
    for a in (
        db.query(Alert)
        .filter(Alert.type.in_(["deploy_oom", "deploy_failed"]), Alert.status == "open")
        .all()
    ):
        try:
            dep_id = int(a.dedup_key.split(":", 1)[1])
        except (IndexError, ValueError):
            continue
        if dep_id not in failed:
            _resolve(db, a.dedup_key)


def overview(db: Session) -> dict:
    servers = db.query(Server).all()
    gpus = db.query(GPU).all()
    running = db.query(Deployment).filter(Deployment.status == "running").count()
    open_alerts = db.query(Alert).filter(Alert.status == "open").all()
    return {
        "nodes_total": len(servers),
        "nodes_online": sum(1 for s in servers if s.status == "online"),
        "gpus_total": len(gpus),
        "vram_used_mb": sum(g.vram_used_mb for g in gpus),
        "vram_total_mb": sum(g.vram_total_mb for g in gpus),
        "running_deployments": running,
        "open_alerts": len(open_alerts),
        "alerts_by_severity": {
            "critical": sum(1 for a in open_alerts if a.severity == "critical"),
            "warning": sum(1 for a in open_alerts if a.severity == "warning"),
            "info": sum(1 for a in open_alerts if a.severity == "info"),
        },
    }


def start_monitor_thread() -> None:
    """后台线程：周期评估告警规则（SQLite 无独立进程，用线程足够）。"""

    def loop() -> None:
        while True:
            time.sleep(settings.alert_poll_interval)
            try:
                db = SessionLocal()
                try:
                    evaluate_alerts(db)
                    db.commit()
                finally:
                    db.close()
            except Exception:
                logger.exception("monitor evaluation failed")

    threading.Thread(target=loop, daemon=True, name="monitor-alerts").start()
