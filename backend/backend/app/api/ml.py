from __future__ import annotations

import re
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
    "major": 0,
    "grade": 0,
    "course": 0,
    "goal": 1,
    "weak_points": 2,
    "weakness": 2,
    "preference": 3,
    "style": 4,
    "cognitive_style": 4,
    "foundation": 5,
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


def _answers_by_id(answers: list[AnswerItem]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in answers:
        question_id = (item.question_id or "").strip().lower()
        answer = item.answer.strip()
        if question_id and answer:
            result[question_id] = answer
    return result


def _split_weak_points(answer: str) -> list[str]:
    parts = re.split(r"\s*(?:、|，|,|；|;|和|与|及|以及)\s*", answer.strip())
    result = []
    for part in parts:
        item = part.strip(" \t\r\n。.!！?？")
        if item and item not in result:
            result.append(item)
    return result


def _normalize_cognitive_style(answer: str) -> str:
    if "循序渐进" in answer:
        return "循序渐进型"
    if "案例" in answer:
        return "案例驱动型"
    if "实践" in answer or "实操" in answer or "代码" in answer:
        return "实践优先型"
    if "图解" in answer or "可视化" in answer:
        return "图解理解型"
    return answer.strip()


def _knowledge_level_from_foundation(answer: str) -> str:
    if any(keyword in answer for keyword in ("基础弱", "比较弱", "零基础")):
        return "foundation"
    if any(keyword in answer for keyword in ("学过", "了解")):
        return "basic"
    return "unknown"


def _preference_items(answer: str) -> list[str]:
    aliases = ("视频", "文字", "讲义", "案例", "项目", "刷题", "练习题", "老师讲解", "代码")
    result = [item for item in aliases if item in answer]
    if result:
        return result
    return _split_weak_points(answer)


def _knowledge_dashboard(foundation: str) -> list[dict]:
    python_score = 80 if "Python" in foundation or "python" in foundation or "了解" in foundation else 55
    ml_score = 55 if "机器学习" in foundation or "学过" in foundation else 45
    dl_score = 35 if "深度学习" in foundation and any(key in foundation for key in ("弱", "薄弱")) else 45
    return [
        {"name": "Python", "value": python_score},
        {"name": "机器学习", "value": ml_score},
        {"name": "深度学习", "value": dl_score},
    ]


def _weak_point_risks(points: list[str]) -> list[dict]:
    default_risks = [75, 80, 65, 60, 55]
    return [
        {"name": point, "risk": default_risks[index] if index < len(default_risks) else 60}
        for index, point in enumerate(points)
    ]


def _engagement_dashboard(answer: str) -> list[dict]:
    values = [65, 70, 60, 75, 68, 55, 50]
    if re.search(r"(\d+(?:\.\d+)?)\s*小时", answer):
        values = [70, 72, 68, 74, 70, 56, 52]
    if "分心" in answer:
        values = [max(value - 5, 0) for value in values]
    if "周末" in answer and any(word in answer for word in ("少", "少一点", "较少")):
        values[-2:] = [55, 50]
    return [
        {"day": day, "value": value}
        for day, value in zip(("周一", "周二", "周三", "周四", "周五", "周六", "周日"), values, strict=False)
    ]


def _forgetting_risk(answer: str) -> list[dict]:
    values = {"算法": 50, "CNN": 70, "反向传播": 75, "模型训练流程": 65}
    return [
        {"name": item, "value": values.get(item, 60)}
        for item in _split_weak_points(answer)
    ]


def _feedback_dashboard(answer: str) -> dict:
    tags = ["积极", "努力"]
    if "案例" in answer and "案例学习" not in tags:
        tags.append("案例学习")
    if "基础" in answer and "基础优先" not in tags:
        tags.append("基础优先")
    return {
        "analysis": answer or "学习目标清晰，建议保持稳定投入，并结合案例和练习逐步巩固。",
        "tags": tags,
    }


def _dashboard_from_answers(profile: dict, answers: list[AnswerItem]) -> dict:
    answer_map = _answers_by_id(answers)
    foundation = answer_map.get("foundation", "")
    weak_points = list(profile.get("weak_points") or [])
    preference_text = profile.get("preference") or answer_map.get("preference", "")
    preferences = _preference_items(preference_text)
    forgetting = answer_map.get("forgetting", "")
    forgetting_risk = _forgetting_risk(forgetting) if forgetting else [
        {"name": item["name"], "value": item["risk"]} for item in _weak_point_risks(weak_points[:2])
    ]
    feedback = _feedback_dashboard(answer_map.get("feedback", ""))
    cognition_main = profile.get("cognitive_style") or ("综合型" if len(preferences) >= 2 else "循序渐进型")
    if cognition_main == "循序渐进型" and len(preferences) >= 2 and not answer_map.get("style"):
        cognition_main = "综合型"

    weak_text = "、".join(weak_points) or "核心知识点"
    return {
        "goal": {
            "progress": 70,
            "analysis": "当前目标明确，适合按照知识点分阶段推进。",
        },
        "knowledge": _knowledge_dashboard(foundation),
        "weakPoints": _weak_point_risks(weak_points),
        "preferences": preferences,
        "cognition": {
            "main": cognition_main,
            "parts": [
                {"name": "逻辑", "value": 60},
                {"name": "实践", "value": 70},
                {"name": "记忆", "value": 50},
            ],
        },
        "engagement": _engagement_dashboard(answer_map.get("engagement", "")),
        "forgettingRisk": forgetting_risk,
        "feedback": feedback,
        "summary": (
            f"该学生专业方向为{profile.get('major') or '当前课程'}，目标是{profile.get('goal') or '提升学习效果'}。"
            f"建议围绕{weak_text}生成讲义、练习题和代码案例。"
        ),
    }


def _profile_from_answers(answers: list[AnswerItem]) -> dict:
    profile = _build_profile(_answers_for_builder(answers))
    for item in answers:
        question_id = (item.question_id or "").strip().lower()
        answer = item.answer.strip()
        if not answer:
            continue

        if question_id == "major":
            profile["major"] = answer
        elif question_id == "grade":
            profile["grade"] = answer
        elif question_id == "course":
            profile["course"] = answer
        elif question_id == "goal":
            profile["goal"] = answer
        elif question_id in {"weak_points", "weakness"}:
            profile["weak_points"] = _split_weak_points(answer)
        elif question_id == "preference":
            profile["preference"] = answer
        elif question_id in {"style", "cognitive_style"}:
            profile["cognitive_style"] = _normalize_cognitive_style(answer)
        elif question_id in {"foundation", "knowledge_level"}:
            profile["knowledge_level"] = _knowledge_level_from_foundation(answer)

    profile["weak_points"] = list(profile.get("weak_points") or [])
    profile["preference"] = profile.get("preference") or "混合资源"
    if not profile.get("cognitive_style") and len(_preference_items(profile["preference"])) >= 2:
        profile["cognitive_style"] = "综合型"
    profile["cognitive_style"] = profile.get("cognitive_style") or "循序渐进型"
    profile["knowledge_level"] = profile.get("knowledge_level") or "unknown"
    return profile


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
    profile = _profile_from_answers(payload.answers)
    profile["preference"] = profile["preference"] or "混合资源"
    profile["cognitive_style"] = profile["cognitive_style"] or "循序渐进型"
    dashboard = _dashboard_from_answers(profile, payload.answers)
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
            key: profile[key]
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
        "dashboard": dashboard,
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
