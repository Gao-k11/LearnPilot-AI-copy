from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.api.profile import latest_profile, profile_payload, upsert_profile
from backend.app.core.config import get_settings
from backend.app.core.database import get_db
from backend.app.models import (
    Course,
    LearningPath,
    LearningPathNode,
    PathFeedback,
    PathNodeProgress,
    ResourceCenter,
    StudentProfile,
    User,
)
from backend.app.services.learning_service import learning_service


router = APIRouter(prefix="/path", tags=["path"])


class PathGenerateRequest(BaseModel):
    userId: str | int
    profile: dict = Field(default_factory=dict)


class PathProgressUpdateRequest(BaseModel):
    pathId: str | int
    nodeId: str | int
    completed: bool


class PathFeedbackRequest(BaseModel):
    pathId: str | int
    rating: int = Field(ge=1, le=5)
    comment: str = ""


def _path_or_404(db: Session, path_id: int, include_deleted: bool = False) -> LearningPath:
    path = db.get(LearningPath, path_id)
    if path is None or (not include_deleted and path.status == "deleted"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning path not found")
    return path


def _node_or_404(db: Session, node_id: int) -> LearningPathNode:
    node = db.get(LearningPathNode, node_id)
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning path node not found")
    return node


def _level_label(level: str, step: int) -> str:
    mapping = {
        "beginner": "入门",
        "foundation": "基础",
        "intermediate": "进阶",
        "advanced": "高级",
    }
    if step >= 5 and level in {"beginner", "foundation"}:
        return "综合"
    return mapping.get(level, level or "基础")


def _local_nodes(profile: dict) -> list[dict]:
    weak_points = list(profile.get("weak_points") or [])
    topic = profile.get("course") or "当前课程"
    goal = profile.get("goal") or "提升课程掌握度"
    focus = weak_points or [topic]
    nodes = []
    step = 1
    for point in focus:
        nodes.append(
            {
                "title": f"{point}基础概念",
                "description": f"理解{point}的定义、关键术语、输入输出和典型应用场景。",
                "objective": f"围绕“{goal}”掌握{point}的基础概念，并能用自己的话解释核心作用。",
                "estimated_minutes": 30,
            }
        )
        step += 1
        nodes.append(
            {
                "title": f"{point}原理与练习",
                "description": f"结合例题理解{point}的核心原理，完成针对性练习并记录易错点。",
                "objective": f"完成{point}的原理推导、练习题和一次错题复盘。",
                "estimated_minutes": 45,
            }
        )
        step += 1
    nodes.extend(
        [
            {
                "title": f"{topic}代码实践",
                "description": f"使用最小代码案例验证{topic}的关键流程和参数变化。",
                "objective": f"完成一个可解释的{topic}代码案例，并记录输入、输出和实验结论。",
                "estimated_minutes": 50,
            },
            {
                "title": f"{topic}综合复盘",
                "description": f"围绕{goal}完成阶段测评，整理薄弱点和下一轮复习计划。",
                "objective": "完成知识点自测、错题归类和学习总结。",
                "estimated_minutes": 35,
            },
        ]
    )
    return nodes[:8]


def _ml_nodes(profile: dict) -> tuple[str | None, list[dict]]:
    if not get_settings().use_ml_service:
        return None, []
    payload = {
        "profile": profile,
        "goal": profile.get("goal") or "",
        "weak_points": profile.get("weak_points") or [],
        "course": profile.get("course") or "",
    }
    result = learning_service.ml_adapter.plan_path(payload)
    if not isinstance(result, dict):
        return None, []
    path_data = result.get("learning_path") or result.get("path") or result
    if not isinstance(path_data, dict):
        return None, []
    raw_nodes = path_data.get("nodes") or path_data.get("steps") or []
    if not isinstance(raw_nodes, list):
        return None, []
    nodes = []
    for item in raw_nodes:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("name")
        if not title:
            continue
        description = item.get("description") or item.get("objective") or item.get("content") or ""
        nodes.append(
            {
                "title": str(title),
                "description": str(description),
                "objective": str(item.get("objective") or description),
                "estimated_minutes": int(item.get("estimated_minutes") or item.get("duration") or 30),
            }
        )
    return str(path_data.get("title") or "") or None, nodes


def _node_payload(node: LearningPathNode) -> dict:
    normalized_status = "not_started" if node.status in {"pending", ""} else node.status
    return {
        "id": str(node.id),
        "nodeId": str(node.id),
        "node_id": node.id,
        "title": node.title,
        "description": node.description or node.objective,
        "objective": node.objective,
        "status": normalized_status,
        "level": node.level or "基础",
        "step_order": node.step_order,
        "estimated_minutes": node.estimated_minutes,
    }


def _edges(nodes: list[LearningPathNode]) -> list[dict]:
    ordered = sorted(nodes, key=lambda item: item.step_order)
    return [
        {"from": str(current.id), "to": str(following.id)}
        for current, following in zip(ordered, ordered[1:])
    ]


def _path_detail_payload(path: LearningPath, nodes: list[LearningPathNode]) -> dict:
    return {
        "pathId": str(path.id),
        "path_id": path.id,
        "title": path.title,
        "goal": path.goal,
        "nodes": [_node_payload(node) for node in sorted(nodes, key=lambda item: item.step_order)],
        "edges": _edges(nodes),
    }


def _recalculate_progress(db: Session, path: LearningPath) -> tuple[int, int, int]:
    nodes = db.query(LearningPathNode).filter(LearningPathNode.path_id == path.id).all()
    completed_nodes = sum(1 for node in nodes if node.status == "completed")
    progress = round(completed_nodes * 100 / len(nodes)) if nodes else 0
    path.progress = float(progress)
    return len(nodes), completed_nodes, progress


@router.post("/generate")
def generate_path(payload: PathGenerateRequest, db: Session = Depends(get_db)) -> dict:
    user_id = int(payload.userId)
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        db_profile = upsert_profile(db, user_id, payload.profile)
        course_name = payload.profile.get("course") or db_profile.course or ""
        course = (
            db.query(Course).filter(Course.name == course_name).first()
            if course_name
            else None
        )
        ml_title, nodes_data = _ml_nodes(profile_payload(db_profile))
        if not nodes_data:
            nodes_data = _local_nodes(profile_payload(db_profile))

        goal = payload.profile.get("goal") or db_profile.goal or "提升课程掌握度"
        path = LearningPath(
            user_id=user_id,
            course_id=course.id if course else None,
            title=ml_title or f"{course_name or '课程'}个性化学习路径",
            goal=goal,
            status="active",
            progress=0,
        )
        db.add(path)
        db.flush()

        level = payload.profile.get("knowledge_level") or db_profile.knowledge_level or "foundation"
        nodes = []
        for index, item in enumerate(nodes_data, start=1):
            node = LearningPathNode(
                path_id=path.id,
                step_order=index,
                title=item["title"],
                objective=item.get("objective") or item.get("description") or "",
                description=item.get("description") or item.get("objective") or "",
                level=_level_label(level, index),
                estimated_minutes=int(item.get("estimated_minutes") or 30),
                status="not_started",
            )
            db.add(node)
            nodes.append(node)
        db.flush()
        db.commit()
        db.refresh(path)
        for node in nodes:
            db.refresh(node)
        return _path_detail_payload(path, nodes)
    except Exception:
        db.rollback()
        raise


@router.get("/detail")
def get_path_detail(pathId: int = Query(gt=0), db: Session = Depends(get_db)) -> dict:
    path = _path_or_404(db, pathId)
    nodes = db.query(LearningPathNode).filter(LearningPathNode.path_id == path.id).all()
    return _path_detail_payload(path, nodes)


@router.get("/list")
def list_paths(userId: int = Query(gt=0), db: Session = Depends(get_db)) -> dict:
    paths = (
        db.query(LearningPath)
        .filter(LearningPath.user_id == userId, LearningPath.status != "deleted")
        .order_by(LearningPath.created_at.desc())
        .all()
    )
    course_ids = {path.course_id for path in paths if path.course_id}
    courses = {
        course.id: course.name
        for course in db.query(Course).filter(Course.id.in_(course_ids)).all()
    } if course_ids else {}
    items = [
        {
            "pathId": str(path.id),
            "path_id": path.id,
            "title": path.title,
            "goal": path.goal,
            "course": courses.get(path.course_id, ""),
            "progress": round(path.progress or 0),
            "status": path.status,
            "created_at": path.created_at.isoformat() if path.created_at else None,
        }
        for path in paths
    ]
    return {"items": items, "total": len(items)}


@router.delete("/delete")
def delete_path(pathId: int = Query(gt=0), db: Session = Depends(get_db)) -> dict:
    path = _path_or_404(db, pathId)
    path.status = "deleted"
    db.commit()
    return {"success": True, "pathId": str(path.id), "path_id": path.id}


@router.post("/progress/update")
def update_path_progress(payload: PathProgressUpdateRequest, db: Session = Depends(get_db)) -> dict:
    path = _path_or_404(db, int(payload.pathId))
    node = _node_or_404(db, int(payload.nodeId))
    if node.path_id != path.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Node does not belong to path")

    progress = (
        db.query(PathNodeProgress)
        .filter(PathNodeProgress.path_id == path.id, PathNodeProgress.node_id == node.id)
        .first()
    )
    if progress is None:
        progress = PathNodeProgress(path_id=path.id, node_id=node.id, user_id=path.user_id)
        db.add(progress)
    progress.completed = payload.completed
    progress.status = "completed" if payload.completed else "in_progress"
    progress.completed_at = datetime.utcnow() if payload.completed else None
    node.status = progress.status
    _, _, percentage = _recalculate_progress(db, path)
    db.commit()
    return {
        "success": True,
        "pathId": str(path.id),
        "path_id": path.id,
        "nodeId": str(node.id),
        "node_id": node.id,
        "completed": payload.completed,
        "progress": percentage,
    }


@router.get("/progress")
def get_path_progress(pathId: int = Query(gt=0), db: Session = Depends(get_db)) -> dict:
    path = _path_or_404(db, pathId)
    nodes = (
        db.query(LearningPathNode)
        .filter(LearningPathNode.path_id == path.id)
        .order_by(LearningPathNode.step_order.asc())
        .all()
    )
    total, completed, percentage = _recalculate_progress(db, path)
    current = next((node for node in nodes if node.status != "completed"), None)
    db.commit()
    return {
        "pathId": str(path.id),
        "path_id": path.id,
        "total_nodes": total,
        "completed_nodes": completed,
        "progress": percentage,
        "current_node": (
            {"id": str(current.id), "nodeId": str(current.id), "title": current.title}
            if current
            else None
        ),
    }


def _resource_keywords(node: LearningPathNode, profile: StudentProfile | None) -> list[str]:
    values = [node.title, node.objective, node.description or ""]
    if profile and profile.weak_points_json:
        values.extend(str(item) for item in profile.weak_points_json)
    keywords = []
    for value in values:
        for token in str(value).replace("、", " ").replace("，", " ").split():
            cleaned = token.strip("，。；：,.!?()（）")
            if len(cleaned) >= 2 and cleaned not in keywords:
                keywords.append(cleaned)
    return keywords[:12]


@router.get("/resources")
def get_node_resources(nodeId: int = Query(gt=0), db: Session = Depends(get_db)) -> dict:
    node = _node_or_404(db, nodeId)
    path = _path_or_404(db, node.path_id)
    profile = latest_profile(db, path.user_id)
    keywords = _resource_keywords(node, profile)
    query = db.query(ResourceCenter).filter(ResourceCenter.status == "published")
    clauses = []
    for keyword in keywords:
        pattern = f"%{keyword}%"
        clauses.extend(
            [
                ResourceCenter.title.ilike(pattern),
                ResourceCenter.description.ilike(pattern),
                ResourceCenter.content.ilike(pattern),
                ResourceCenter.knowledge_point.ilike(pattern),
                ResourceCenter.tags.ilike(pattern),
            ]
        )
    resources = query.filter(or_(*clauses)).limit(12).all() if clauses else []
    if not resources:
        resources = query.order_by(ResourceCenter.views.desc(), ResourceCenter.id.asc()).limit(8).all()

    items = []
    for resource in resources:
        resource_type = (resource.resource_type or "").lower()
        url = (
            f"/resources/{resource.id}/view"
            if resource_type == "document"
            else (resource.url or "")
        )
        items.append(
            {
                "id": resource.id,
                "title": resource.title,
                "type": resource_type,
                "resource_type": resource_type,
                "open_type": "url",
                "url": url,
                "detail_url": f"/resources/{resource.id}",
                "description": resource.description or "",
                "difficulty": resource.difficulty or "",
                "summary": resource.summary or "",
            }
        )
    return {"nodeId": str(node.id), "node_id": node.id, "items": items}


@router.get("/recommend")
def recommend_paths(userId: int = Query(gt=0), db: Session = Depends(get_db)) -> dict:
    if db.get(User, userId) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    profile = profile_payload(latest_profile(db, userId))
    weak_points = profile["weak_points"] or ["课程核心概念"]
    course = profile["course"] or "当前课程"
    goal = profile["goal"] or "提升课程掌握度"
    preference = profile["preference"] or "混合资源"
    return {
        "items": [
            {
                "title": f"{course}基础巩固路径",
                "description": f"适合“{goal}”的基础巩固路线，结合{preference}推进学习。",
                "course": course,
                "estimated_days": 7,
                "difficulty": profile["knowledge_level"] or "foundation",
                "tags": [*weak_points[:3], preference],
                "reason": f"根据你的薄弱点{'、'.join(weak_points)}推荐",
            }
        ]
    }


@router.post("/feedback")
def submit_path_feedback(payload: PathFeedbackRequest, db: Session = Depends(get_db)) -> dict:
    path = _path_or_404(db, int(payload.pathId))
    db.add(
        PathFeedback(
            path_id=path.id,
            user_id=path.user_id,
            rating=payload.rating,
            comment=payload.comment,
        )
    )
    db.commit()
    return {"success": True, "message": "反馈已提交"}
