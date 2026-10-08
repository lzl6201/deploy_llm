"""用户鉴权：密码哈希、JWT 签发/校验、角色依赖、认证中间件、默认管理员种子。"""

from __future__ import annotations

import datetime
import logging
import re

import bcrypt
import jwt
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def require_roles(*roles: str):
    """授权依赖：校验当前登录用户角色（认证由中间件完成，这里只查角色）。"""

    def _dep(request: Request) -> None:
        role = getattr(request.state, "role", None)
        if role not in roles:
            raise HTTPException(status_code=403, detail="insufficient permission")

    return _dep


def seed_admin(db: Session) -> None:
    from app.models.orm import User

    if db.query(User).first() is not None:
        return
    db.add(
        User(
            username=settings.admin_username,
            password_hash=hash_password(settings.admin_password),
            role="admin",
        )
    )
    db.commit()
    logger.warning(
        "seeded default admin user '%s'; change its password immediately",
        settings.admin_username,
    )


# Agent 信任边界端点（机器调用，共享 token 或无 token），不校验用户 JWT
_AGENT_PUBLIC: list[tuple[re.Pattern, set[str]]] = [
    (re.compile(r"^/api/servers/register$"), {"POST"}),
    (re.compile(r"^/api/servers/\d+/heartbeat$"), {"POST"}),
    (re.compile(r"^/api/deployments/pending$"), {"GET"}),
    (re.compile(r"^/api/deployments/stopping$"), {"GET"}),
    (re.compile(r"^/api/deployments/\d+/status$"), {"POST"}),
    (re.compile(r"^/api/quantize/pending$"), {"GET"}),
    (re.compile(r"^/api/quantize/\d+/status$"), {"POST"}),
]


def _is_public(method: str, path: str) -> bool:
    if method == "POST" and path == "/api/auth/login":
        return True
    for pattern, methods in _AGENT_PUBLIC:
        if method in methods and pattern.match(path):
            return True
    return False


class AuthMiddleware:
    """纯 ASGI 中间件（不用 BaseHTTPMiddleware，避免破坏网关 SSE 流式透传）。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        method = scope["method"]
        if path.startswith("/api/") and not _is_public(method, path):
            headers = dict(scope.get("headers", []))
            auth = headers.get(b"authorization", b"").decode("latin-1")
            if not auth.startswith("Bearer "):
                await JSONResponse(
                    status_code=401, content={"detail": "not authenticated"}
                )(scope, receive, send)
                return
            token = auth[7:].strip()
            try:
                payload = decode_token(token)
            except Exception:
                await JSONResponse(
                    status_code=401, content={"detail": "invalid or expired token"}
                )(scope, receive, send)
                return

            state = scope.setdefault("state", {})
            state["user_id"] = int(payload.get("sub"))
            state["username"] = payload.get("username")
            state["role"] = payload.get("role")

        await self.app(scope, receive, send)
