from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.models import ProducerArtifact, ProducerTask, User

ALLOWED_STATUSES = frozenset({"pending", "running", "completed", "failed"})
REQUIREMENT_SUMMARY_LIMIT = 120
ERROR_MESSAGE_LIST_LIMIT = 200
CONTENT_PREVIEW_LIMIT = 400


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _truncate(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    value = str(text).strip()
    if not value:
        return None
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def _clamp_progress(value: Any) -> int:
    try:
        progress = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, progress))


def _normalize_status(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Allowed: {', '.join(sorted(ALLOWED_STATUSES))}",
        )
    return normalized



def _build_task_query(db: Session, keyword: str | None, status_value: str | None, user_id: int | None):
    artifact_counts = (
        db.query(
            ProducerArtifact.task_id.label("artifact_task_id"),
            func.count(ProducerArtifact.id).label("artifact_count"),
        )
        .group_by(ProducerArtifact.task_id)
        .subquery()
    )

    query = (
        db.query(
            ProducerTask,
            User,
            func.coalesce(artifact_counts.c.artifact_count, 0).label("artifact_count"),
        )
        .outerjoin(User, ProducerTask.user_id == User.id)
        .outerjoin(artifact_counts, ProducerTask.task_id == artifact_counts.c.artifact_task_id)
    )

    normalized_status = _normalize_status(status_value)
    if normalized_status:
        query = query.filter(func.lower(ProducerTask.status) == normalized_status)

    if user_id is not None:
        query = query.filter(ProducerTask.user_id == user_id)

    if keyword:
        pattern = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                ProducerTask.task_id.like(pattern),
                ProducerTask.topic.like(pattern),
                ProducerTask.requirement.like(pattern),
                User.username.like(pattern),
                User.email.like(pattern),
            )
        )

    return query


def _list_item_payload(task: ProducerTask, user: User | None, artifact_count: int) -> dict[str, Any]:
    username = user.username if user is not None else "未知用户"
    email = user.email or "" if user is not None else ""
    user_status = (user.status or "active") if user is not None else ""
    return {
        "taskId": task.task_id,
        "userId": task.user_id or 0,
        "username": username,
        "email": email,
        "userStatus": user_status,
        "topic": task.topic,
        "requirementSummary": _truncate(task.requirement, REQUIREMENT_SUMMARY_LIMIT) or "",
        "taskType": task.task_type,
        "status": (task.status or "").lower(),
        "progress": _clamp_progress(task.progress),
        "artifactCount": max(0, int(artifact_count or 0)),
        "errorMessage": _truncate(task.error_message, ERROR_MESSAGE_LIST_LIMIT),
        "createdAt": _iso(task.created_at),
        "updatedAt": _iso(task.updated_at),
    }


def list_admin_producer_tasks(
    db: Session,
    *,
    page: int,
    page_size: int,
    keyword: str | None = None,
    status_value: str | None = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    query = _build_task_query(db, keyword, status_value, user_id)
    total = int(query.count())
    rows = (
        query.order_by(ProducerTask.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_list_item_payload(task, user, artifact_count) for task, user, artifact_count in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
    }


def _build_result_summary(result_json: Any, artifact_types: list[str]) -> dict[str, Any]:
    if not isinstance(result_json, dict):
        return {
            "topic": "",
            "requestedTypes": [],
            "artifactTypes": artifact_types,
            "agentTraceCount": 0,
        }
    requested = result_json.get("requested_types")
    traces = result_json.get("agent_traces")
    return {
        "topic": str(result_json.get("topic") or ""),
        "requestedTypes": list(requested) if isinstance(requested, list) else [],
        "artifactTypes": artifact_types,
        "agentTraceCount": len(traces) if isinstance(traces, list) else 0,
    }


def get_admin_producer_task_detail(db: Session, task_id: str) -> dict[str, Any]:
    row = (
        db.query(ProducerTask, User)
        .outerjoin(User, ProducerTask.user_id == User.id)
        .filter(ProducerTask.task_id == task_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producer task not found")

    task, user = row
    artifacts = (
        db.query(ProducerArtifact)
        .filter(ProducerArtifact.task_id == task_id)
        .order_by(ProducerArtifact.id.asc())
        .all()
    )
    artifact_types = []
    artifact_items = []
    for artifact in artifacts:
        artifact_type = artifact.artifact_type or ""
        if artifact_type and artifact_type not in artifact_types:
            artifact_types.append(artifact_type)
        artifact_items.append(
            {
                "artifactType": artifact_type,
                "title": artifact.title,
                "contentPreview": _truncate(artifact.content, CONTENT_PREVIEW_LIMIT) or "",
                "url": artifact.url,
                "createdAt": _iso(artifact.created_at),
            }
        )

    return {
        "taskId": task.task_id,
        "user": {
            "userId": task.user_id or 0,
            "username": user.username if user is not None else "未知用户",
            "email": user.email or "" if user is not None else "",
            "status": (user.status or "active") if user is not None else "",
        },
        "topic": task.topic,
        "requirement": task.requirement or "",
        "taskType": task.task_type,
        "status": (task.status or "").lower(),
        "progress": _clamp_progress(task.progress),
        "errorMessage": task.error_message,
        "createdAt": _iso(task.created_at),
        "updatedAt": _iso(task.updated_at),
        "artifactCount": len(artifacts),
        "artifacts": artifact_items,
        "resultSummary": _build_result_summary(task.result_json, artifact_types),
    }
