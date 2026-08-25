from typing import List, Optional

from pydantic import BaseModel


class GPUCapacity(BaseModel):
    vram_total_mb: int


class PlanRequest(BaseModel):
    """按「模型版本 + 目标节点」自动推荐（服务端解析 GGUF 元数据）。"""

    model_version_id: int
    server_id: int
    max_context_len: Optional[int] = None


class RecommendRequest(BaseModel):
    params_b: float = 0.0
    dtype: str = "bf16"
    context_len: int = 4096
    quantization: str = "none"
    format: str = "safetensors"
    file_size_mb: int = 0
    gpus: List[GPUCapacity] = []
    block_count: int = 0
    head_count_kv: int = 0
    key_length: int = 0
    embedding_length: int = 0


class Alternative(BaseModel):
    engine: str
    tp_size: int
    quantization: str
    ctx_len: int
    weight_mb: int
    kv_cache_mb: int
    total_mb: int
    fits: bool


class RecommendResponse(BaseModel):
    engine: str
    tp_size: int
    quantization: str
    fits_single_gpu: bool
    fits: bool
    estimated_vram_mb: int
    weight_mb: int
    kv_cache_mb: int
    recommended_ctx_len: int
    note: str
    alternatives: List[Alternative] = []


class ServerModelRecommendOut(BaseModel):
    """反向推荐：给定节点显卡，输出仓库中每个模型版本是否可部署。"""

    model_id: int
    model_name: str
    version_id: int
    version: str
    format: str
    params_b: float
    quantization: str
    dtype: str
    fits: bool
    engine: str
    tp_size: int
    recommended_ctx_len: int
    estimated_vram_mb: int
    note: str
