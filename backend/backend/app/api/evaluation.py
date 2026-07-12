from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models import User
from backend.app.schemas.dto import (
    EvaluationDetailResponse,
    EvaluationHistoryItem,
    EvaluationHistoryResponse,
    EvaluationStartResponse,
    EvaluationSubmitAnswersRequest,
    EvaluationSubmitDetailedResponse,
    EvaluationWrongItem,
)
from backend.app.services.learning_service import learning_service


router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluation"])


def _to_detailed_response(payload: dict) -> EvaluationSubmitDetailedResponse:
    wrong_items = [
        EvaluationWrongItem(**item) if not isinstance(item, EvaluationWrongItem) else item
        for item in payload.get("wrong_items") or []
    ]
    return EvaluationSubmitDetailedResponse(
        evaluation_id=payload.get("evaluation_id"),
        score=payload.get("score"),
        accuracy=payload.get("accuracy"),
        correct_count=payload.get("correct_count"),
        total_count=payload.get("total_count"),
        mastery_score=payload["mastery_score"],
        feedback=payload["feedback"],
        wrong_items=wrong_items,
        weak_points=list(payload.get("weak_points") or []),
        path_adjustment=payload.get("path_adjustment"),
        updated_profile=payload.get("updated_profile"),
        profile_update=dict(payload.get("profile_update") or {}),
    )


@router.get("/start", response_model=EvaluationStartResponse)
def start_evaluation(
    path_id: int | None = Query(default=None, gt=0),
    course_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvaluationStartResponse:
    try:
        result = learning_service.start_evaluation(
            db,
            current_user.id,
            path_id,
            course_id,
            limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return EvaluationStartResponse(**result)


@router.post("/submit", response_model=EvaluationSubmitDetailedResponse)
def submit_evaluation(
    payload: EvaluationSubmitAnswersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvaluationSubmitDetailedResponse:
    try:
        if payload.answers:
            if payload.path_id is not None:
                learning_service._resolve_owned_path(db, payload.path_id, current_user.id)
            result = learning_service.submit_evaluation_answers(
                db,
                current_user.id,
                payload.path_id,
                payload.course_id,
                payload.study_minutes,
                [item.model_dump() for item in payload.answers],
            )
            return _to_detailed_response(result)

        if payload.correct_count is None or payload.total_count is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either answers or correct_count/total_count is required",
            )
        if payload.path_id is not None:
            learning_service._resolve_owned_path(db, payload.path_id, current_user.id)
        result = learning_service.submit_evaluation_summary(
            db,
            current_user.id,
            payload.path_id,
            payload.correct_count,
            payload.total_count,
            payload.completed_resource_count,
            payload.study_minutes,
        )
        return _to_detailed_response(result)
    except ValueError as exc:
        message = str(exc)
        status_code = status.HTTP_404_NOT_FOUND if "not found" in message.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=message) from exc


@router.get("", response_model=EvaluationHistoryResponse)
def list_evaluations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvaluationHistoryResponse:
    items = learning_service.list_evaluations(db, current_user.id, limit=20)
    return EvaluationHistoryResponse(
        items=[EvaluationHistoryItem(**item) for item in items],
        total=len(items),
    )


@router.get("/{evaluation_id}", response_model=EvaluationDetailResponse)
def get_evaluation_detail(
    evaluation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvaluationDetailResponse:
    try:
        result = learning_service.get_evaluation_detail(db, current_user.id, evaluation_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    wrong_items = [EvaluationWrongItem(**item) for item in result.get("wrong_items") or []]
    return EvaluationDetailResponse(
        evaluation_id=result["evaluation_id"],
        path_id=result.get("path_id"),
        score=result.get("score"),
        accuracy=result.get("accuracy"),
        correct_count=result.get("correct_count"),
        total_count=result.get("total_count"),
        mastery_score=result["mastery_score"],
        feedback=result["feedback"],
        wrong_items=wrong_items,
        weak_points=list(result.get("weak_points") or []),
        path_adjustment=result.get("path_adjustment"),
        created_at=result.get("created_at"),
        profile_update=dict(result.get("profile_update") or {}),
    )
