from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class ModelCreate(BaseModel):
    name: str
    params_b: float = 0.0
    architecture: str = ""
    dtype: str = "bf16"
    format: str = "safetensors"
    context_len: int = 4096
    base_storage_path: str
    source: str = "local"


class ModelImportRequest(BaseModel):
    """从文件系统导入 GGUF 模型（自动解析元数据）。"""

    path: str
    version: str = "v1"
    source: str = "local"


class ModelVersionCreate(BaseModel):
    version: str
    quantization: str = "none"
    dtype: str = "bf16"
    format: str = "safetensors"
    architecture: str = ""
    gguf_file_type: int = 0
    storage_path: str
    size_gb: Optional[float] = None
    file_size_mb: int = 0


class ModelVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    quantization: str
    dtype: str = "bf16"
    format: str = "safetensors"
    architecture: str = ""
    gguf_file_type: int = 0
    storage_path: str
    size_gb: Optional[float] = None
    file_size_mb: int = 0


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    params_b: float
    architecture: str = ""
    dtype: str
    format: str = "safetensors"
    context_len: int
    base_storage_path: str
    source: str
    created_at: datetime
    versions: List[ModelVersionOut] = []
