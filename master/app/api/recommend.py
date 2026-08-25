from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.orm import GPU, ModelVersion
from app.schemas.recommend import (
    PlanRequest,
    RecommendRequest,
    RecommendResponse,
    ServerModelRecommendOut,
)
from app.services.gguf import GGUFError, parse_gguf
from app.services.recommend_engine import RecommendInput, RecommendResult, recommend

router = APIRouter(prefix="/api/recommend", tags=["recommend"])


def _to_response(result: RecommendResult) -> RecommendResponse:
    return RecommendResponse(
        engine=result.engine,
        tp_size=result.tp_size,
        quantization=result.quantization,
        fits_single_gpu=result.fits_single_gpu,
        fits=result.fits,
        estimated_vram_mb=result.estimated_vram_mb,
        weight_mb=result.weight_mb,
        kv_cache_mb=result.kv_cache_mb,
        recommended_ctx_len=result.recommended_ctx_len,
        note=result.note,
        alternatives=result.alternatives,
    )


def _gpu_list_for(db: Session, server_id: int) -> list[dict]:
    gpus = db.query(GPU).filter(GPU.server_id == server_id).order_by(GPU.index).all()
    return [{"vram_total_mb": g.vram_total_mb} for g in gpus]


def _gguf_meta(mv: ModelVersion) -> dict:
    """解析 GGUF KV 结构，供精确 KV cache 估算；失败时退化。"""
    meta = {
        "block_count": 0,
        "head_count_kv": 0,
        "key_length": 0,
        "embedding_length": 0,
        "file_size_mb": mv.file_size_mb or 0,
    }
    if mv.format == "gguf":
        try:
            info = parse_gguf(mv.storage_path)
            meta = {
                "block_count": info.block_count,
                "head_count_kv": info.head_count_kv,
                "key_length": info.key_length,
                "embedding_length": info.embedding_length,
                "file_size_mb": int(info.file_size_bytes // (1024 * 1024)),
            }
        except GGUFError:
            pass
    return meta


def _plan_for_version(
    db: Session, mv: ModelVersion, server_id: int, max_context_len: int | None = None
) -> RecommendResult:
    """为单个模型版本 + 目标节点计算部署方案。"""
    model = mv.model
    ctx_len = max_context_len or model.context_len or 4096
    meta = _gguf_meta(mv)
    gpu_list = _gpu_list_for(db, server_id)
    return recommend(
        RecommendInput(
            params_b=model.params_b,
            dtype=mv.dtype or model.dtype,
            context_len=ctx_len,
            quantization=mv.quantization,
            format=mv.format,
            file_size_mb=meta["file_size_mb"],
            gpus=gpu_list,
            block_count=meta["block_count"],
            head_count_kv=meta["head_count_kv"],
            key_length=meta["key_length"],
            embedding_length=meta["embedding_length"],
        )
    )


@router.post("", response_model=RecommendResponse)
def recommend_deploy(req: RecommendRequest):
    result = recommend(
        RecommendInput(
            params_b=req.params_b,
            dtype=req.dtype,
            context_len=req.context_len,
            quantization=req.quantization,
            format=req.format,
            file_size_mb=req.file_size_mb,
            gpus=[g.model_dump() for g in req.gpus],
            block_count=req.block_count,
            head_count_kv=req.head_count_kv,
            key_length=req.key_length,
            embedding_length=req.embedding_length,
        )
    )
    return _to_response(result)


@router.post("/plan", response_model=RecommendResponse)
def recommend_plan(req: PlanRequest, db: Session = Depends(get_db)):
    mv = db.get(ModelVersion, req.model_version_id)
    if mv is None:
        raise HTTPException(status_code=404, detail="model version not found")
    return _to_response(_plan_for_version(db, mv, req.server_id, req.max_context_len))


@router.get("/models", response_model=list[ServerModelRecommendOut])
def recommend_models(
    server_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """反向推荐：给定节点显卡，返回仓库中每个模型版本的可部署性。"""
    versions = db.query(ModelVersion).all()
    results: list[ServerModelRecommendOut] = []
    for mv in versions:
        plan = _plan_for_version(db, mv, server_id)
        model = mv.model
        results.append(
            ServerModelRecommendOut(
                model_id=model.id,
                model_name=model.name,
                version_id=mv.id,
                version=mv.version,
                format=mv.format,
                params_b=model.params_b,
                quantization=mv.quantization,
                dtype=mv.dtype or model.dtype,
                fits=plan.fits,
                engine=plan.engine,
                tp_size=plan.tp_size,
                recommended_ctx_len=plan.recommended_ctx_len,
                estimated_vram_mb=plan.estimated_vram_mb,
                note=plan.note,
            )
        )
    results.sort(key=lambda r: (not r.fits, -r.params_b))
    return results
