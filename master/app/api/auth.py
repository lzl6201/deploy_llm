from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.orm import User
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserOut
from app.services.auth import (
    create_access_token,
    hash_password,
    require_roles,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": UserOut.model_validate(user),
    }


@router.get("/me", response_model=UserOut)
def me(request: Request, db: Session = Depends(get_db)):
    user_id = getattr(request.state, "user_id", None)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_roles("admin"))):
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserOut)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    if db.query(User).filter(User.username == payload.username).first() is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _=Depends(require_roles("admin")),
):
    if user_id == getattr(request.state, "user_id", None):
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    db.delete(user)
    db.commit()
    return {"ok": True}
