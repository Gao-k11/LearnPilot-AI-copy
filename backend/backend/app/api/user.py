from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models import User


router = APIRouter(prefix="/api/user", tags=["user"])


class UserInfoUpdateRequest(BaseModel):
    nickname: str | None = None
    gender: str | None = None
    phone: str | None = None
    avatar: str | None = None


def _frontend_role(user: User) -> str:
    if user.username == "admin" or bool(user.is_admin) or user.role == "admin":
        return "ADMIN"
    return "USER"


def user_info_payload(user: User) -> dict:
    nickname = user.nickname or user.display_name or user.username
    return {
        "user_id": user.id,
        "username": user.username,
        "nickname": nickname,
        "gender": user.gender or "",
        "phone": user.phone or "",
        "email": user.email or "",
        "role": _frontend_role(user),
        "avatar": user.avatar or "",
    }


@router.get("/info")
def get_user_info(user: User = Depends(get_current_user)) -> dict:
    return user_info_payload(user)


@router.put("/info")
def update_user_info(
    payload: UserInfoUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    for field in ("nickname", "gender", "phone", "avatar"):
        value = getattr(payload, field)
        if value is not None:
            setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user_info_payload(user)
