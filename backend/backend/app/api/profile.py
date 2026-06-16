from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models import StudentProfile, User


router = APIRouter(prefix="/profile", tags=["profile"])


class ProfileUpdateRequest(BaseModel):
    userId: str | int
    profile: dict = Field(default_factory=dict)


PROFILE_DEFAULTS = {
    "major": "",
    "grade": "",
    "course": "",
    "goal": "",
    "weak_points": [],
    "preference": "",
    "cognitive_style": "",
    "knowledge_level": "",
    "mastery": {},
    "engagement_score": 0.0,
    "forgetting_risk": 0.0,
    "learning_stage": "",
}


def profile_payload(profile: StudentProfile | None) -> dict:
    if profile is None:
        return dict(PROFILE_DEFAULTS)
    return {
        "major": profile.major or "",
        "grade": profile.grade or "",
        "course": profile.course or "",
        "goal": profile.goal or "",
        "weak_points": profile.weak_points_json or [],
        "preference": profile.preference or "",
        "cognitive_style": profile.cognitive_style or "",
        "knowledge_level": profile.knowledge_level or "",
        "mastery": profile.mastery or {},
        "engagement_score": profile.engagement_score if profile.engagement_score is not None else 0.0,
        "forgetting_risk": profile.forgetting_risk if profile.forgetting_risk is not None else 0.0,
        "learning_stage": profile.learning_stage or "",
    }


def latest_profile(db: Session, user_id: int) -> StudentProfile | None:
    return (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == user_id)
        .order_by(StudentProfile.id.desc())
        .first()
    )


def upsert_profile(db: Session, user_id: int, values: dict) -> StudentProfile:
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    profile = latest_profile(db, user_id)
    if profile is None:
        profile = StudentProfile(user_id=user_id, raw_text="")
        db.add(profile)

    for field in (
        "major",
        "grade",
        "course",
        "goal",
        "preference",
        "cognitive_style",
        "knowledge_level",
        "engagement_score",
        "forgetting_risk",
        "learning_stage",
    ):
        if field in values:
            setattr(profile, field, values[field])
    if "weak_points" in values:
        profile.weak_points_json = list(values.get("weak_points") or [])
    if "mastery" in values:
        profile.mastery = dict(values.get("mastery") or {})
    profile.raw_text = json.dumps(values, ensure_ascii=False)
    db.flush()
    return profile


@router.get("/get")
def get_profile(
    userId: int = Query(gt=0),
    db: Session = Depends(get_db),
) -> dict:
    if db.get(User, userId) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"userId": str(userId), "profile": profile_payload(latest_profile(db, userId))}


@router.post("/update")
def update_profile(payload: ProfileUpdateRequest, db: Session = Depends(get_db)) -> dict:
    user_id = int(payload.userId)
    try:
        profile = upsert_profile(db, user_id, payload.profile)
        db.commit()
        db.refresh(profile)
        return {"success": True, "profile": profile_payload(profile)}
    except Exception:
        db.rollback()
        raise


@router.get("/schema")
def get_profile_schema() -> dict:
    return {
        "fields": [
            {"key": "major", "label": "专业", "type": "text", "required": True},
            {
                "key": "grade",
                "label": "年级",
                "type": "select",
                "options": ["大一", "大二", "大三", "大四", "研究生"],
            },
            {"key": "course", "label": "当前课程", "type": "text"},
            {"key": "goal", "label": "学习目标", "type": "textarea"},
            {"key": "weak_points", "label": "薄弱知识点", "type": "tags"},
            {
                "key": "preference",
                "label": "学习偏好",
                "type": "select",
                "options": ["讲义", "视频", "练习题", "代码案例", "混合资源"],
            },
            {
                "key": "cognitive_style",
                "label": "认知风格",
                "type": "select",
                "options": ["循序渐进型", "案例驱动型", "实践优先型", "图解理解型"],
            },
            {
                "key": "knowledge_level",
                "label": "基础水平",
                "type": "select",
                "options": ["beginner", "foundation", "intermediate", "advanced"],
            },
        ]
    }
