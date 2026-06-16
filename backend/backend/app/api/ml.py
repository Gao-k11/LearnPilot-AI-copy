from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from backend.app.api.path import PathGenerateRequest, generate_path
from backend.app.api.profile import latest_profile, profile_payload, upsert_profile
from backend.app.api.profile_builder import _build_profile
from backend.app.core.database import get_db
from backend.app.core.security import optional_user
from backend.app.models import MLProfileAnswer, User


router = APIRouter(prefix="/api/ml", tags=["ml"])


QUESTIONS = [
    {
        "id": "major_grade_course",
        "question_id": "major_grade_course",
        "question": "请简单介绍你的专业、年级和当前正在学习的课程。",
        "type": "text",
        "required": True,
        "field": "basic_info",
    },
    {
        "id": "goal",
        "question_id": "goal",
        "question": "你这次学习最希望达成什么目标？",
        "type": "textarea",
        "required": True,
        "field": "goal",
    },
    {
        "id": "weak_points",
        "question_id": "weak_points",
        "question": "目前哪些知识点最薄弱或最容易卡住？",
        "type": "tags",
        "required": True,
        "field": "weak_points",
    },
    {
        "id": "preference",
        "question_id": "preference",
        "question": "你更喜欢哪种学习资源形式？",
        "type": "select",
        "options": ["讲义", "视频", "练习题", "代码案例", "混合资源"],
        "required": False,
        "field": "preference",
    },
    {
        "id": "cognitive_style",
        "question_id": "cognitive_style",
        "question": "你更习惯哪种学习方式？",
        "type": "select",
        "options": ["循序渐进型", "案例驱动型", "实践优先型", "图解理解型"],
        "required": False,
        "field": "cognitive_style",
    },
    {
        "id": "knowledge_level",
        "question_id": "knowledge_level",
        "question": "你认为自己当前基础水平如何？",
        "type": "select",
        "options": ["beginner", "foundation", "intermediate", "advanced"],
        "required": False,
        "field": "knowledge_level",
    },
]

QUESTION_INDEX = {
    "major_grade_course": 0,
    "basic_info": 0,
    "goal": 1,
    "weak_points": 2,
    "preference": 3,
    "cognitive_style": 4,
    "knowledge_level": 5,
}


class AnswerItem(BaseModel):
    question_id: str = ""
    question: str = ""
    answer: str = ""

    model_config = ConfigDict(extra="allow")


class MLProfileAnswerRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=64)
    userId: str | int | None = None
    question_id: str = Field(min_length=1, max_length=128)
    question: str = ""
    answer: str = ""
    answers: list[AnswerItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class MLProfileGenerateRequest(BaseModel):
    userId: str | int | None = None
    session_id: str | None = Field(default=None, max_length=64)
    answers: list[AnswerItem] = Field(default_factory=list)

    model_config = ConfigDict(extra="allow")


class MLLearningPathRequest(BaseModel):
    userId: str | int | None = None
    profile: dict = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


def _resolved_user_id(
    current_user: User | None,
    requested_user_id: str | int | None,
) -> int:
    if current_user is not None:
        return current_user.id
    return int(requested_user_id or 1)


def _save_answers(
    db: Session,
    session_id: str,
    user_id: int | None,
    answers: list[AnswerItem],
) -> None:
    for item in answers:
        if not item.answer.strip():
            continue
        db.add(
            MLProfileAnswer(
                user_id=user_id,
                session_id=session_id,
                question_id=item.question_id or "unknown",
                question=item.question,
                answer=item.answer.strip(),
            )
        )


def _answers_for_builder(answers: list[AnswerItem]) -> list[str]:
    ordered = [""] * 6
    for item in answers:
        index = QUESTION_INDEX.get(item.question_id)
        if index is not None and item.answer.strip():
            ordered[index] = item.answer.strip()
    return ordered


@router.get("/profile/current")
def get_current_ml_profile(
    userId: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_user),
) -> dict:
    user_id = _resolved_user_id(current_user, userId)
    return {
        "userId": str(user_id),
        "profile": profile_payload(latest_profile(db, user_id)),
    }


@router.get("/profile/questions")
def get_ml_profile_questions() -> dict:
    return {"questions": QUESTIONS}


@router.post("/profile/answer")
def save_ml_profile_answer(
    payload: MLProfileAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_user),
) -> dict:
    session_id = payload.session_id or uuid4().hex
    user_id = _resolved_user_id(current_user, payload.userId)
    main_answer = AnswerItem(
        question_id=payload.question_id,
        question=payload.question,
        answer=payload.answer,
    )
    items = [main_answer, *payload.answers]
    _save_answers(db, session_id, user_id, items)
    db.commit()
    return {
        "success": True,
        "session_id": session_id,
        "question_id": payload.question_id,
        "answer": payload.answer,
    }


@router.post("/profile/generate")
def generate_ml_profile(
    payload: MLProfileGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_user),
) -> dict:
    user_id = _resolved_user_id(current_user, payload.userId)
    session_id = payload.session_id or uuid4().hex
    profile = _build_profile(_answers_for_builder(payload.answers))
    profile["preference"] = profile["preference"] or "混合资源"
    profile["cognitive_style"] = profile["cognitive_style"] or "循序渐进型"
    profile["knowledge_level"] = profile["knowledge_level"] or "foundation"
    try:
        _save_answers(db, session_id, user_id, payload.answers)
        db_profile = upsert_profile(db, user_id, profile)
        db.commit()
        db.refresh(db_profile)
    except Exception:
        db.rollback()
        raise
    return {
        "success": True,
        "userId": str(user_id),
        "profile": {
            key: profile_payload(db_profile)[key]
            for key in (
                "major",
                "grade",
                "course",
                "goal",
                "weak_points",
                "preference",
                "cognitive_style",
                "knowledge_level",
            )
        },
    }


@router.post("/learning-path/generate")
def generate_ml_learning_path(
    payload: MLLearningPathRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_user),
) -> dict:
    user_id = _resolved_user_id(current_user, payload.userId)
    result = generate_path(
        PathGenerateRequest(userId=user_id, profile=payload.profile),
        db,
    )
    result["pathId"] = str(result["pathId"])
    result["path_id"] = str(result["path_id"])
    return result
