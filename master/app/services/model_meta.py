"""模型版本 → 推荐引擎输入的统一转换。

集中解析 GGUF KV 结构并构造 :class:`RecommendInput`，供推荐引擎与调度器
复用，避免各自重复解析逻辑。
"""

from __future__ import annotations

from app.models.orm import ModelVersion
from app.services.gguf import GGUFError, parse_gguf
from app.services.recommend_engine import RecommendInput


def gguf_meta(mv: ModelVersion) -> dict:
    """解析 GGUF 的 KV 结构元数据，供精确 KV cache 估算；失败时降级。"""
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


def model_version_input(
    mv: ModelVersion, max_context_len: int | None = None, gpus: list[dict] | None = None
) -> RecommendInput:
    """由模型版本构造推荐引擎输入；`gpus` 为可选的目标节点 GPU 清单。"""
    model = mv.model
    meta = gguf_meta(mv)
    return RecommendInput(
        params_b=model.params_b,
        dtype=mv.dtype or model.dtype,
        context_len=max_context_len or model.context_len or 4096,
        quantization=mv.quantization,
        format=mv.format,
        file_size_mb=meta["file_size_mb"],
        gpus=gpus,
        block_count=meta["block_count"],
        head_count_kv=meta["head_count_kv"],
        key_length=meta["key_length"],
        embedding_length=meta["embedding_length"],
    )
