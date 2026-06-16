from __future__ import annotations

import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import optional_user
from backend.app.models import (
    ProfileBuilderMessage,
    ProfileBuilderSession,
    StudentProfile,
    User,
)


router = APIRouter(prefix="/profile-builder", tags=["profile-builder"])

QUESTIONS = (
    "请简单介绍你的专业、年级和当前想学习的课程。",
    "你这次学习最希望达成什么目标？",
    "目前哪些知识点最薄弱或最容易卡住？请用逗号分隔。",
    "你更喜欢哪种学习方式，例如图文、视频、练习或代码实操？",
    "你习惯怎样理解新知识，例如先看整体框架、跟随案例，还是逐步推导？",
    "你认为自己目前对这门课程的基础水平如何，例如入门、基础、进阶？",
)


class ProfileBuilderAnswerRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    answer: str = Field(min_length=1)


class ProfileBuilderRegenerateRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)


def _get_session(db: Session, session_id: str) -> ProfileBuilderSession:
    session = (
        db.query(ProfileBuilderSession)
        .filter(ProfileBuilderSession.session_id == session_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile builder session not found")
    return session


def _user_answers(db: Session, session_id: str) -> list[str]:
    messages = (
        db.query(ProfileBuilderMessage)
        .filter(
            ProfileBuilderMessage.session_id == session_id,
            ProfileBuilderMessage.role == "user",
        )
        .order_by(ProfileBuilderMessage.id.asc())
        .all()
    )
    return [message.content.strip() for message in messages]


def _first_match(text: str, patterns: tuple[str, ...], fallback: str) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(" ，,。；;：:")
    return fallback


def _extract_major(introduction: str) -> str:
    major = _first_match(
        introduction,
        (
            r"(?:我是|我读|就读于?|专业是|专业为|学的是)?\s*([^，,。；;\s]{2,24}?)专业",
        ),
        "",
    )
    return re.sub(r"^(?:我是|我读|就读于?)", "", major).strip()


def _extract_grade(introduction: str) -> str:
    return _first_match(
        introduction,
        (
            r"(大[一二三四五]|研[一二三]|博士[一二三四五六]|高[一二三])",
            r"([一二三四五六七八九]年级)",
        ),
        "",
    )


def _extract_course(introduction: str) -> str:
    course = _first_match(
        introduction,
        (
            r"(?:课程是|课程为|当前学习|正在学习|想学习|准备学习)\s*([^，,。；;]+)",
            r"(?:学习方向是|学习方向为)\s*([^，,。；;]+)",
        ),
        "",
    )
    course = re.sub(r"(?:这门)?课程$", "", course).strip()
    course = re.sub(r"(?:，|,)?(?:薄弱点|不熟悉|比较薄弱).*$", "", course).strip()
    return course


def _clean_dimension_answer(answer: str, prefixes: tuple[str, ...]) -> str:
    value = answer.strip(" ，,。；;：:")
    for prefix in prefixes:
        value = re.sub(rf"^{prefix}\s*", "", value, count=1)
    return value.strip(" ，,。；;：:")


def _weak_point_source(text: str, use_full_answer: bool) -> str:
    suffix_match = re.search(
        r"([^，,。；;]+?)(?:比较|较为|很|最)?(?:薄弱|不熟悉|容易卡住|掌握不好)",
        text,
        re.IGNORECASE,
    )
    if suffix_match:
        return suffix_match.group(1)

    prefix_match = re.search(
        r"(?:薄弱点|薄弱知识点|不熟悉的内容|容易卡住的地方)(?:是|有|包括|为)?"
        r"\s*([^。；;]+)",
        text,
        re.IGNORECASE,
    )
    if prefix_match:
        return prefix_match.group(1)
    return text if use_full_answer else ""


def _extract_weak_points(text: str, use_full_answer: bool = False) -> list[str]:
    source = _weak_point_source(text, use_full_answer)
    if not source:
        return []

    source = re.sub(
        r"^(?:我觉得|我认为|目前|主要|我的|在|对于|对)\s*",
        "",
        source.strip(),
    )
    source = re.sub(
        r"(?:这些)?(?:知识点|内容)?(?:比较|较为|很|最)?"
        r"(?:薄弱|不熟悉|容易卡住|掌握不好)$",
        "",
        source,
    )
    items = re.split(r"\s*(?:、|,|，|;|；|和|与|以及|还有|及)\s*", source)
    result = []
    for item in items:
        cleaned = item.strip(" ，,。；;：:")
        cleaned = re.sub(r"^(?:我对|对|在)\s*", "", cleaned)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def _build_profile(answers: list[str]) -> dict:
    padded = answers + [""] * (len(QUESTIONS) - len(answers))
    introduction = padded[0]
    first_round_weak_points = _extract_weak_points(introduction)
    dedicated_weak_points = _extract_weak_points(padded[2], use_full_answer=True)
    weak_points = []
    for item in [*first_round_weak_points, *dedicated_weak_points]:
        if item not in weak_points:
            weak_points.append(item)

    return {
        "major": _extract_major(introduction),
        "grade": _extract_grade(introduction),
        "course": _extract_course(introduction),
        "goal": _clean_dimension_answer(
            padded[1],
            (r"我的目标(?:是|为)", r"目标(?:是|为)", r"我希望", r"希望能够"),
        ),
        "weak_points": weak_points,
        "preference": _clean_dimension_answer(
            padded[3],
            (r"我更喜欢", r"我喜欢", r"更喜欢", r"喜欢", r"我的偏好(?:是|为)", r"偏好(?:是|为)"),
        ),
        "cognitive_style": _clean_dimension_answer(
            padded[4],
            (r"我习惯", r"习惯", r"我通常", r"通常"),
        ),
        "knowledge_level": _clean_dimension_answer(
            padded[5],
            (r"我目前是", r"目前是", r"我的水平(?:是|为)", r"水平(?:是|为)"),
        ),
    }


def _sync_student_profile(
    db: Session,
    builder_session: ProfileBuilderSession,
    profile: dict,
    answers: list[str],
) -> None:
    if builder_session.user_id is None:
        return
    student_profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == builder_session.user_id)
        .order_by(StudentProfile.id.desc())
        .first()
    )
    if student_profile is None:
        student_profile = StudentProfile(
            user_id=builder_session.user_id,
            raw_text="\n".join(answers),
        )
        db.add(student_profile)
    student_profile.major = profile["major"]
    student_profile.grade = profile["grade"]
    student_profile.course = profile["course"]
    student_profile.goal = profile["goal"]
    student_profile.weak_points_json = profile["weak_points"]
    student_profile.preference = profile["preference"]
    student_profile.cognitive_style = profile["cognitive_style"]
    student_profile.knowledge_level = profile["knowledge_level"]
    student_profile.raw_text = "\n".join(answers)


def _finish_session(db: Session, builder_session: ProfileBuilderSession) -> dict:
    answers = _user_answers(db, builder_session.session_id)
    profile = _build_profile(answers)
    builder_session.result_profile_json = profile
    builder_session.status = "completed"
    builder_session.current_step = len(QUESTIONS)
    _sync_student_profile(db, builder_session, profile, answers)
    return profile


@router.post("/start")
def start_profile_builder(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_user),
) -> dict:
    session_id = uuid4().hex
    builder_session = ProfileBuilderSession(
        session_id=session_id,
        user_id=current_user.id if current_user else None,
        current_step=1,
        status="active",
    )
    db.add(builder_session)
    db.add(
        ProfileBuilderMessage(
            session_id=session_id,
            role="assistant",
            content=QUESTIONS[0],
        )
    )
    db.commit()
    return {
        "session_id": session_id,
        "question": QUESTIONS[0],
        "current_step": 1,
        "finished": False,
    }


@router.post("/answer")
def answer_profile_builder(
    payload: ProfileBuilderAnswerRequest,
    db: Session = Depends(get_db),
) -> dict:
    builder_session = _get_session(db, payload.session_id)
    if builder_session.status == "completed":
        return {
            "session_id": builder_session.session_id,
            "question": "",
            "current_step": builder_session.current_step,
            "finished": True,
            "profile": builder_session.result_profile_json or {},
        }

    db.add(
        ProfileBuilderMessage(
            session_id=builder_session.session_id,
            role="user",
            content=payload.answer.strip(),
        )
    )
    db.flush()

    if builder_session.current_step >= len(QUESTIONS):
        profile = _finish_session(db, builder_session)
        db.commit()
        return {
            "session_id": builder_session.session_id,
            "question": "",
            "current_step": builder_session.current_step,
            "finished": True,
            "profile": profile,
        }

    builder_session.current_step += 1
    next_question = QUESTIONS[builder_session.current_step - 1]
    db.add(
        ProfileBuilderMessage(
            session_id=builder_session.session_id,
            role="assistant",
            content=next_question,
        )
    )
    db.commit()
    return {
        "session_id": builder_session.session_id,
        "question": next_question,
        "current_step": builder_session.current_step,
        "finished": False,
    }


@router.get("/result")
def get_profile_builder_result(
    session_id: str = Query(min_length=1, max_length=64),
    db: Session = Depends(get_db),
) -> dict:
    builder_session = _get_session(db, session_id)
    profile = builder_session.result_profile_json
    if profile is None:
        profile = _build_profile(_user_answers(db, session_id))
    return {"session_id": session_id, "profile": profile}


@router.post("/regenerate")
def regenerate_profile_builder(
    payload: ProfileBuilderRegenerateRequest,
    db: Session = Depends(get_db),
) -> dict:
    builder_session = _get_session(db, payload.session_id)
    profile = _finish_session(db, builder_session)
    db.commit()
    return {"session_id": builder_session.session_id, "profile": profile}
