from __future__ import annotations

from datetime import datetime, time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.api.auth import user_payload
from backend.app.core.database import get_db
from backend.app.core.security import optional_user
from backend.app.models import (
    LearningPath,
    PathFeedback,
    ProducerTask,
    ResourceCenter,
    User,
)


router = APIRouter(prefix="/admin", tags=["admin"])


class RoleUpdateRequest(BaseModel):
    isAdmin: bool | None = None
    is_admin: bool | None = None


def _admin_value(payload: RoleUpdateRequest) -> bool:
    if payload.isAdmin is not None:
        return payload.isAdmin
    return bool(payload.is_admin)


@router.get("/users/page")
def list_users(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    keyword: str | None = Query(default=None),
    role: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(User)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(or_(User.username.like(pattern), User.email.like(pattern)))
    if role:
        normalized = role.strip().lower()
        if normalized == "admin":
            query = query.filter(or_(User.is_admin.is_(True), User.role == "admin"))
        elif normalized == "user":
            query = query.filter(User.role != "admin", User.is_admin.is_(False))
        else:
            query = query.filter(User.role == normalized)
    if status:
        query = query.filter(User.status == status.strip())

    total = query.count()
    users = (
        query.order_by(User.id.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )
    return {
        "items": [user_payload(user) for user in users],
        "total": total,
        "page": page,
        "pageSize": pageSize,
    }


@router.get("/users/{id}")
def get_user(id: int, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user_payload(user)


@router.put("/users/{id}/role")
def update_user_role(id: int, payload: RoleUpdateRequest, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    is_admin = _admin_value(payload)
    user.is_admin = is_admin
    user.role = "admin" if is_admin else "student"
    db.commit()
    db.refresh(user)
    return {"success": True, "user": user_payload(user)}


@router.delete("/users/{id}")
def delete_user(
    id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_user),
) -> dict:
    if current_user is not None and current_user.id == id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")
    user = db.get(User, id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.status = "deleted"
    db.commit()
    return {"success": True, "id": id}


def _safe_count(db: Session, model) -> int:
    try:
        return int(db.query(model).count())
    except Exception:
        return 0


@router.get("/statistics")
def statistics(db: Session = Depends(get_db)) -> dict:
    today_start = datetime.combine(datetime.now().date(), time.min)
    try:
        today_user_count = int(db.query(User).filter(User.created_at >= today_start).count())
    except Exception:
        today_user_count = 0
    return {
        "userCount": _safe_count(db, User),
        "resourceCount": _safe_count(db, ResourceCenter),
        "pathCount": _safe_count(db, LearningPath),
        "feedbackCount": _safe_count(db, PathFeedback),
        "producerTaskCount": _safe_count(db, ProducerTask),
        "todayUserCount": today_user_count,
        "todayResourceViewCount": 0,
    }
