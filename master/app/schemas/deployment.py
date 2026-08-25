from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class DeploymentCreate(BaseModel):
    name: str
    model_version_id: int
    server_id: int
    engine: str = "vllm"
    gpu_ids: List[int] = []
    tp_size: int = 1
    pp_size: int = 1
    port: int = 8000
    max_model_len: int = 4096
    extra: dict = {}


class DeploymentStatusUpdate(BaseModel):
    status: str
    endpoint: Optional[str] = None
    detail: Optional[str] = None


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
    status: str
    endpoint: Optional[str] = None
    created_at: datetime


class PendingDeploymentOut(DeploymentOut):
    model_path: str
    model_name: str
    max_model_len: int
    extra: dict = {}
    launch_config: LaunchConfigOut
