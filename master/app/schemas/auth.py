from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    created_at: Optional[datetime] = None


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=72)
    role: str = Field(default="viewer", pattern="^(admin|operator|viewer)$")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
