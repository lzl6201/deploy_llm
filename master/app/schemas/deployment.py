from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class DeploymentCreate(BaseModel):
    name: str
    model_version_id: int
    server_id: Optional[int] = None  # 缺省时由调度器自动选节点
    engine: Optional[str] = None  # 缺省时按模型格式自动解析（gguf→llama.cpp）
    gpu_ids: List[int] = []
    tp_size: int = 1
    pp_size: int = 1
    port: int = 8000
    max_model_len: int = 4096
    extra: dict = {}
    container_image: Optional[str] = None  # 非空则 Agent 走 Docker 编排


class PlacementRequest(BaseModel):
    """放置预览：给定模型版本与并行度，返回按分数降序的候选节点。"""

    model_version_id: int
    tp_size: int = 1
    max_model_len: Optional[int] = None
    server_id: Optional[int] = None


class PlacementOut(BaseModel):
    server_id: int
    hostname: str
    gpu_ids: List[int]
    score: float
    total_required_mb: int
    reason: str


class DeploymentStatusUpdate(BaseModel):
    status: str
    endpoint: Optional[str] = None
    detail: Optional[str] = None


class ScaleRequest(BaseModel):
    """副本扩缩：目标副本数（同一 model_version + engine 的部署实例数）。"""

    replicas: int


class LaunchConfigOut(BaseModel):
    command: List[str]
    env: dict
    port: int
    health_check_path: str = "/health"
    container_image: Optional[str] = None


class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    model_version_id: int
    engine: str
    format: str = "safetensors"
    server_id: int
    gpu_ids: List[int]
    tp_size: int
    pp_size: int
    quant: str
    port: int
    container_image: Optional[str] = None
    status: str
    endpoint: Optional[str] = None
    last_error: Optional[str] = None
    created_at: datetime


class PendingDeploymentOut(DeploymentOut):
    model_path: str
    model_name: str
    max_model_len: int
    extra: dict = {}
    launch_config: LaunchConfigOut
