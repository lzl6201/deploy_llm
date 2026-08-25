from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    server_id: Optional[int] = None
    dedup_key: str
    type: str
    severity: str
    message: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime] = None


class OverviewOut(BaseModel):
    nodes_total: int
    nodes_online: int
    gpus_total: int
    vram_used_mb: int
    vram_total_mb: int
    running_deployments: int
    open_alerts: int
    alerts_by_severity: dict
