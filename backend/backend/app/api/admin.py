from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.api.auth import user_payload
from backend.app.core.database import get_db
from backend.app.core.security import get_current_admin
from backend.app.models import User
from backend.app.services.admin_dashboard_service import build_admin_statistics
from backend.app.services.admin_producer_service import (
    get_admin_producer_task_detail,
    list_admin_producer_tasks,
)


router = APIRouter(prefix="/admin", tags=["admin"])


class RoleUpdateRequest(BaseModel):
    isAdmin: bool | None = None
    is_admin: bool | None = None


def _admin_value(payload: RoleUpdateRequest) -> bool:
    if payload.isAdmin is not None:
        return payload.isAdmin
    return bool(payload.is_admin)


def _apply_role_filter(query, role: str | None):
    if not role:
        return query
    normalized = role.strip().lower()
    if normalized in {"admin", "administrator"}:
        return query.filter(
            or_(
                User.is_admin.is_(True),
                func.lower(User.role) == "admin",
                User.username == "admin",
            )
        )
    if normalized in {"user", "student"}:
        return query.filter(
            User.is_admin.is_(False),
            func.lower(User.role) != "admin",
            User.username != "admin",
        )
    return query.filter(func.lower(User.role) == normalized)


def _apply_status_filter(query, status_value: str | None):
    if not status_value:
        return query.filter(User.status != "deleted")
    normalized = status_value.strip().lower()
    if normalized == "all":
        return query
    return query.filter(User.status == normalized)


@router.get("/users/page")
def list_users(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    keyword: str | None = Query(default=None),
    role: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    del current_admin
    query = db.query(User)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                User.username.like(pattern),
                User.email.like(pattern),
                User.nickname.like(pattern),
            )
        )
    query = _apply_role_filter(query, role)
    query = _apply_status_filter(query, status)

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


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    del current_admin
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user_payload(user)


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    payload: RoleUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if (user.status or "active") == "deleted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot update role for deleted user")

    is_admin = _admin_value(payload)
    if user.id == current_admin.id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin role",
        )

    user.is_admin = is_admin
    user.role = "admin" if is_admin else "student"
    db.commit()
    db.refresh(user)
    return {"success": True, "user": user_payload(user)}


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    if current_admin.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete yourself")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if (user.status or "active") == "deleted":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already deleted")
    user.status = "deleted"
    db.commit()
    return {"success": True, "id": user_id, "status": "deleted"}


@router.get("/statistics")
def statistics(
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    del current_admin
    return build_admin_statistics(db)


@router.get("/producer/tasks")
def list_producer_tasks(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    keyword: str | None = Query(default=None),
    status: str | None = Query(default=None),
    userId: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    del current_admin
    return list_admin_producer_tasks(
        db,
        page=page,
        page_size=pageSize,
        keyword=keyword,
        status_value=status,
        user_id=userId,
    )


@router.get("/producer/tasks/{task_id}")
def get_producer_task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin),
) -> dict:
    del current_admin
    return get_admin_producer_task_detail(db, task_id)
