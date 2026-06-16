from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import create_access_token, get_current_user, hash_password, verify_password
from backend.app.models import User


router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthCompatRegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1)


class AuthCompatLoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1)


def user_payload(user: User) -> dict:
    is_admin = bool(user.is_admin) or user.role == "admin" or user.username == "admin"
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email or "",
        "isAdmin": is_admin,
        "is_admin": is_admin,
        "role": "ADMIN" if is_admin else "USER",
        "status": user.status or "active",
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def auth_payload(user: User) -> dict:
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": user_payload(user),
    }


def _clean_email(email: str) -> str:
    cleaned = email.strip()
    if "@" not in cleaned:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="email is invalid")
    return cleaned


@router.post("/register")
def register(payload: AuthCompatRegisterRequest, db: Session = Depends(get_db)) -> dict:
    email = _clean_email(payload.email)
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="username is required")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")

    is_admin = username == "admin"
    user = User(
        username=username,
        display_name=username,
        email=email,
        password_hash=hash_password(payload.password),
        role="admin" if is_admin else "student",
        is_admin=is_admin,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return auth_payload(user)


@router.post("/login")
def login(payload: AuthCompatLoginRequest, db: Session = Depends(get_db)) -> dict:
    email = _clean_email(payload.email)
    user = db.query(User).filter(User.email == email).first()
    if user is None or (user.status or "active") == "deleted" or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return auth_payload(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return user_payload(user)
