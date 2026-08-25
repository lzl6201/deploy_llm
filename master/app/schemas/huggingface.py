from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class HfModelOut(BaseModel):
    id: str
    downloads: int = 0
    likes: int = 0
    tags: List[str] = []
    pipeline_tag: str = ""
    created_at: str = ""


class HfFileOut(BaseModel):
    path: str
    size: int = 0
    is_gguf: bool = False


class DownloadCreate(BaseModel):
    repo_id: str
    filename: str
    size_bytes: int = 0


class DownloadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repo_id: str
    filename: str
    dest_path: str
    size_bytes: int
    downloaded_bytes: int
    status: str
    progress: float
    error: Optional[str] = None
    model_version_id: Optional[int] = None
    created_at: datetime
