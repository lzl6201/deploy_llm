"""调度器：按显存需求 + GPU 空闲度对在线节点打分放置。

放置策略（贪心打分）：
1. 候选为 ``status == "online"`` 且含 GPU 快照的节点；
2. 拟合判断：按引擎（vLLM 张量并行 / llama.cpp 层切分）计算在请求上下文
   长度下的显存足迹（权重 + KV cache + 开销），与各卡「当前空闲显存」
   (vram_total - vram_used) 比较；空闲显存已扣除其他进程占用，故不再叠加
   可用率系数；
3. 打分：节点空闲显存余量 + (100 - 平均利用率) 加权，取最高者；
4. 指定 server_id 时仅在该节点内选卡，放不下则报错。

上下文长度未指定时按最小可用值（MIN_CTX）估算最小足迹，判断节点是否
「能跑」，实际上下文由推荐引擎另行优化。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.orm import ModelVersion, Server
from app.services.model_meta import model_version_input
from app.services.recommend_engine import (
    MIN_CTX,
    _kv_cache_mb,
    _overhead_ratio,
    _weight_mb,
)


class PlacementError(Exception):
    """无可用节点或显存不足。"""


@dataclass
class Placement:
    server_id: int
    hostname: str
    gpu_ids: list[int]
    score: float
    total_required_mb: int
    reason: str


def _requirements(mv: ModelVersion, tp_size: int, max_model_len: int | None):
    """返回 (total_mb, per_gpu_mb, format)。

    per_gpu_mb：vLLM 张量并行时单卡所需显存；llama.cpp 层切分按合计校验，
    故标记为 total（调度时据此走「合计」分支）。
    """
    inp = model_version_input(mv, max_model_len or MIN_CTX)
    quant = mv.quantization or ("F16" if inp.format == "gguf" else "none")
    weight = _weight_mb(inp, quant)
    kv = _kv_cache_mb(inp, inp.context_len)
    overhead = int(weight * _overhead_ratio(inp))
    total = weight + kv + overhead
    per_gpu = total if inp.format == "gguf" else (total // tp_size if tp_size else total)
    return total, per_gpu, inp.format


def _score_server(
    server: Server, total: int, per_gpu: int, tp_size: int, fmt: str
) -> Placement | None:
    """对单个节点打分；放不下返回 None。"""
    entries = [
        (g.index, max(0, g.vram_total_mb - g.vram_used_mb), g.utilization)
        for g in server.gpus
    ]
    if len(entries) < tp_size:
        return None

    entries.sort(key=lambda e: -e[1])  # 空闲显存降序
    chosen = entries[:tp_size]
    free_chosen = [e[1] for e in chosen]
    if fmt == "gguf":
        if sum(free_chosen) < total:
            return None
    elif free_chosen[-1] < per_gpu:
        return None

    gpu_ids = sorted(e[0] for e in chosen)
    total_free = sum(e[1] for e in entries)
    avg_util = sum(e[2] for e in entries) / len(entries)
    score = total_free + (100 - avg_util) * 1000
    reason = (
        f"{len(gpu_ids)} 卡 · 节点空闲 {total_free // 1024}G"
        f" · 平均利用率 {avg_util:.0f}%"
    )
    return Placement(
        server_id=server.id,
        hostname=server.hostname,
        gpu_ids=gpu_ids,
        score=score,
        total_required_mb=total,
        reason=reason,
    )


def candidates(
    db: Session,
    mv: ModelVersion,
    tp_size: int,
    max_model_len: int | None,
    server_id: int | None = None,
    limit: int = 10,
) -> list[Placement]:
    """返回按分数降序的候选节点；不指定 server_id 时全集群打分。"""
    total, per_gpu, fmt = _requirements(mv, tp_size or 1, max_model_len)
    query = db.query(Server).filter(Server.status == "online")
    if server_id is not None:
        query = query.filter(Server.id == server_id)

    results = []
    for srv in query.all():
        p = _score_server(srv, total, per_gpu, tp_size or 1, fmt)
        if p is not None:
            results.append(p)
    results.sort(key=lambda p: -p.score)
    return results[:limit]


def _max_gpus_per_node(db: Session) -> int:
    return max(
        (len(s.gpus) for s in db.query(Server).filter(Server.status == "online").all()),
        default=0,
    )


def _has_rdma_nodes(db: Session) -> bool:
    return (
        db.query(Server)
        .filter(Server.status == "online", Server.interconnect.in_(["ib", "nvlink"]))
        .first()
        is not None
    )


def pick_best(
    db: Session,
    mv: ModelVersion,
    tp_size: int,
    max_model_len: int | None,
    server_id: int | None = None,
) -> Placement:
    """挑选最优节点；无可用节点时抛 :class:`PlacementError`。

    当 ``tp_size`` 超过单节点 GPU 数时需要跨机张量并行，仅在集群存在
    IB/RDMA 互联节点时才允许（否则给出明确降级提示）。
    """
    out = candidates(db, mv, tp_size, max_model_len, server_id, limit=1)
    if not out:
        if server_id is None and tp_size > _max_gpus_per_node(db) and not _has_rdma_nodes(db):
            raise PlacementError(
                f"TP={tp_size} 超过单节点最大 GPU 数，需跨机张量并行，"
                "但集群无 IB/RDMA 互联节点；请降低并行度或选择量化"
            )
        raise PlacementError("无可用节点：显存不足或缺少足够空闲 GPU")
    return out[0]
