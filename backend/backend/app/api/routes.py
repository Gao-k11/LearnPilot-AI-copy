from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import check_database, get_db
from backend.app.models import Course, KnowledgePoint
from backend.app.schemas.dto import (
    EvaluationSubmitRequest,
    EvaluationSubmitResponse,
    LearningStartRequest,
    LearningStartResponse,
    PathNodeOut,
    PathPlanRequest,
    PathPlanResponse,
    ProfileAnalyzeRequest,
    ProfileAnalyzeResponse,
    ResourceGenerateRequest,
    ResourceGenerateResponse,
    ResourceOut,
    StudentProfileOut,
    TutorAskRequest,
    TutorAskResponse,
)
from backend.app.services.learning_service import learning_service

router = APIRouter()


def to_profile_out(profile: dict) -> StudentProfileOut:
    return StudentProfileOut(**profile)


def to_resource_out(resource) -> ResourceOut:
    return ResourceOut(
        id=resource.id,
        title=resource.title,
        resource_type=resource.resource_type,
        content=resource.content,
        review_status=resource.review_status,
        review_notes=resource.review_notes,
    )


def to_path_response(path, nodes) -> PathPlanResponse:
    return PathPlanResponse(
        path_id=path.id,
        title=path.title,
        goal=path.goal,
        nodes=[
            PathNodeOut(
                id=node.id,
                step_order=node.step_order,
                title=node.title,
                objective=node.objective,
                estimated_minutes=node.estimated_minutes,
                resource_id=node.resource_id,
            )
            for node in nodes
        ],
    )


@router.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "database": check_database()}


@router.get("/api/v1/courses", tags=["course"])
def list_courses(db: Session = Depends(get_db)) -> list[dict]:
    return [{"id": item.id, "name": item.name, "description": item.description} for item in db.query(Course).all()]


@router.get("/api/v1/knowledge-points", tags=["course"])
def list_knowledge_points(course_id: int | None = None, db: Session = Depends(get_db)) -> list[dict]:
    query = db.query(KnowledgePoint)
    if course_id:
        query = query.filter(KnowledgePoint.course_id == course_id)
    return [
        {
            "id": item.id,
            "course_id": item.course_id,
            "name": item.name,
            "description": item.description,
            "difficulty": item.difficulty,
        }
        for item in query.all()
    ]


@router.post("/api/v1/profile/analyze", response_model=ProfileAnalyzeResponse, tags=["profile"])
def analyze_profile(payload: ProfileAnalyzeRequest, db: Session = Depends(get_db)) -> ProfileAnalyzeResponse:
    db_profile, profile = learning_service.analyze_profile(db, payload.user_id, payload.text)
    return ProfileAnalyzeResponse(profile_id=db_profile.id, profile=to_profile_out(profile))


@router.post("/api/v1/resources/generate", response_model=ResourceGenerateResponse, tags=["resource"])
def generate_resources(payload: ResourceGenerateRequest, db: Session = Depends(get_db)) -> ResourceGenerateResponse:
    resources = learning_service.generate_resources(
        db,
        payload.user_id,
        payload.course_id,
        payload.topic,
        payload.weak_points,
        payload.resource_types,
    )
    return ResourceGenerateResponse(resources=[to_resource_out(item) for item in resources])


@router.post("/api/v1/paths/plan", response_model=PathPlanResponse, tags=["path"])
def plan_path(payload: PathPlanRequest, db: Session = Depends(get_db)) -> PathPlanResponse:
    path, nodes = learning_service.plan_path(
        db, payload.user_id, payload.course_id, payload.goal, payload.weak_points, payload.resource_ids
    )
    return to_path_response(path, nodes)


@router.post("/api/v1/tutor/ask", response_model=TutorAskResponse, tags=["tutor"])
def ask_tutor(payload: TutorAskRequest, db: Session = Depends(get_db)) -> TutorAskResponse:
    answer = learning_service.ask_tutor(
        db,
        payload.user_id,
        payload.question,
        payload.profile.model_dump() if payload.profile else None,
        payload.history,
    )
    return TutorAskResponse(**answer)


@router.post("/api/v1/evaluations/submit", response_model=EvaluationSubmitResponse, tags=["evaluation"])
def submit_evaluation(
    payload: EvaluationSubmitRequest, db: Session = Depends(get_db)
) -> EvaluationSubmitResponse:
    evaluation = learning_service.evaluate(
        db,
        payload.user_id,
        payload.path_id,
        payload.correct_count,
        payload.total_count,
        payload.completed_resource_count,
        payload.study_minutes,
    )
    return EvaluationSubmitResponse(
        evaluation_id=evaluation.id,
        mastery_score=evaluation.mastery_score,
        feedback=evaluation.feedback,
        profile_update=evaluation.profile_update or {},
    )


@router.post("/api/v1/learning/start", response_model=LearningStartResponse, tags=["workflow"])
def start_learning(payload: LearningStartRequest, db: Session = Depends(get_db)) -> LearningStartResponse:
    profile, resources, path, nodes = learning_service.start_learning(
        db,
        payload.user_id,
        payload.course_id,
        payload.requirement,
    )
    return LearningStartResponse(
        profile=to_profile_out(profile),
        resources=[to_resource_out(item) for item in resources],
        path=to_path_response(path, nodes),
    )
