from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class QuantizeCreate(BaseModel):
    model_version_id: int
    target_quant: str
    server_id: int


class QuantizeStatusUpdate(BaseModel):
    status: str
    progress: Optional[float] = None
    error: Optional[str] = None
    target_path: Optional[str] = None


class QuantizeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_version_id: int
    method: str
    target_quant: str
    server_id: Optional[int] = None
    source_path: Optional[str] = None
    target_path: Optional[str] = None
    status: str
    progress: float
    error: Optional[str] = None
    created_at: datetime


class PendingQuantizeOut(QuantizeOut):
    command: List[str]
