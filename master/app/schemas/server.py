from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class GPURegister(BaseModel):
    index: int
    name: str
    vram_total_mb: int
    vram_used_mb: int = 0
    utilization: float = 0.0
    temperature: float = 0.0
    power_w: float = 0.0


class ServerRegister(BaseModel):
    token: str
    hostname: str
    ip: Optional[str] = None
    driver: Optional[str] = None
    cuda: Optional[str] = None
    interconnect: Optional[str] = "pcie"
    gpus: List[GPURegister] = []


class Heartbeat(BaseModel):
    token: str
    gpus: List[GPURegister] = []


class ManualGPUCreate(BaseModel):
    index: int
    name: str
    vram_total_mb: int


class ManualNodeCreate(BaseModel):
    """手动登记节点（未接 Agent，供规划/预登记）。"""

    hostname: str
    ip: Optional[str] = None
    driver: Optional[str] = None
    cuda: Optional[str] = None
    interconnect: Optional[str] = "pcie"
    gpus: List[ManualGPUCreate] = []


class NodeUpdate(BaseModel):
    """编辑节点（hostname 可选，用于改名）。"""

    hostname: Optional[str] = None
    ip: Optional[str] = None
    driver: Optional[str] = None
    cuda: Optional[str] = None
    interconnect: Optional[str] = None
    gpus: Optional[List[ManualGPUCreate]] = None


class GPUSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index: int
    name: str
    vram_total_mb: int
    vram_used_mb: int
    utilization: float
    temperature: float
    power_w: float
    status: str


class ServerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hostname: str
    ip: Optional[str] = None
    driver: Optional[str] = None
    cuda: Optional[str] = None
    interconnect: Optional[str] = None
    status: str
    source: str = "agent"
    total_gpus: int
    last_seen: Optional[datetime] = None
    gpus: List[GPUSummary] = []
