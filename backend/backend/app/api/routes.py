from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.adapters.ml_service_client import MLServiceClient
from backend.app.core.database import check_database, get_db
from backend.app.core.config import get_settings
from backend.app.core.security import create_access_token, get_current_user, hash_password, optional_user, require_role, verify_password
from backend.app.models import Course, CourseResource, ImportJob, KnowledgePoint, Question, User
from backend.app.schemas.dto import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthResponse,
    CourseResourceOut,
    ImportJobOut,
    LearningStartRequest,
    LearningStartResponse,
    PathNodeOut,
    PathPlanRequest,
    PathPlanResponse,
    ProfileAnalyzeRequest,
    ProfileAnalyzeResponse,
    QuestionOut,
    ResourceImportRequest,
    ResourceGenerateRequest,
    ResourceGenerateResponse,
    ResourceOut,
    StudentProfileOut,
    TutorAskRequest,
    TutorAskResponse,
    UserOut,
)
from backend.app.services.import_service import resource_import_service
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
    settings = get_settings()
    ml_status = False
    if settings.use_ml_service:
        try:
            ml_status = MLServiceClient(timeout=2.0).health().get("status") == "ok"
        except Exception:
            ml_status = False
    redis_status = _check_redis(settings.redis_url)
    qwen_configured = bool(settings.dashscope_api_key) or settings.learnpilot_llm_mode.lower() in {"template", "offline"}
    return {
        "status": "ok",
        "database": check_database(),
        "ml_service": ml_status,
        "redis": redis_status,
        "qwen_configured": qwen_configured,
        "llm_mode": settings.learnpilot_llm_mode,
    }


@router.post("/api/v1/auth/register", response_model=AuthResponse, tags=["auth"])
def register(payload: AuthRegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.strip() if payload.email else None
    if email and db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already exists")
    is_admin = payload.username == "admin" or payload.role == "admin"
    user = User(
        username=payload.username,
        display_name=payload.display_name or payload.username,
        email=email,
        role="admin" if is_admin else payload.role,
        is_admin=is_admin,
        status="active",
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthResponse(access_token=create_access_token(user), user=to_user_out(user))


@router.post("/api/v1/auth/login", response_model=AuthResponse, tags=["auth"])
def login(payload: AuthLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    return AuthResponse(access_token=create_access_token(user), user=to_user_out(user))


@router.get("/api/v1/auth/me", response_model=UserOut, tags=["auth"])
def me(user: User = Depends(get_current_user)) -> UserOut:
    return to_user_out(user)


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


@router.post("/api/v1/courses/{course_id}/resources/import", response_model=ImportJobOut, tags=["course"])
def import_course_resource(
    course_id: int,
    payload: ResourceImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher", "admin")),
) -> ImportJobOut:
    if db.get(Course, course_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    job = resource_import_service.import_payload(db, course_id, user.id, payload.filename, payload.source_type, payload.content)
    return to_import_job_out(job)


@router.get("/api/v1/import-jobs/{job_id}", response_model=ImportJobOut, tags=["course"])
def get_import_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ImportJobOut:
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import job not found")
    if user.role == "student" and job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return to_import_job_out(job)


@router.get("/api/v1/courses/{course_id}/resources", response_model=list[CourseResourceOut], tags=["course"])
def list_course_resources(course_id: int, db: Session = Depends(get_db)) -> list[CourseResourceOut]:
    return [
        CourseResourceOut(
            id=item.id,
            course_id=item.course_id,
            knowledge_point_id=item.knowledge_point_id,
            title=item.title,
            resource_type=item.resource_type,
            content=item.content,
            source=item.source,
            source_type=item.source_type,
            status=item.status,
            version=item.version,
        )
        for item in db.query(CourseResource).filter(CourseResource.course_id == course_id).all()
    ]


@router.get("/api/v1/courses/{course_id}/questions", response_model=list[QuestionOut], tags=["course"])
def list_course_questions(course_id: int, db: Session = Depends(get_db)) -> list[QuestionOut]:
    return [
        QuestionOut(
            id=item.id,
            course_id=item.course_id,
            knowledge_point_id=item.knowledge_point_id,
            question_type=item.question_type,
            stem=item.stem,
            answer=item.answer,
            explanation=item.explanation,
            difficulty=item.difficulty,
            source=item.source,
        )
        for item in db.query(Question).filter(Question.course_id == course_id).all()
    ]


@router.post("/api/v1/profile/analyze", response_model=ProfileAnalyzeResponse, tags=["profile"])
def analyze_profile(
    payload: ProfileAnalyzeRequest, db: Session = Depends(get_db), current_user: User | None = Depends(optional_user)
) -> ProfileAnalyzeResponse:
    db_profile, profile = learning_service.analyze_profile(db, resolve_user_id(payload.user_id, current_user), payload.text)
    return ProfileAnalyzeResponse(profile_id=db_profile.id, profile=to_profile_out(profile))


@router.post("/api/v1/resources/generate", response_model=ResourceGenerateResponse, tags=["resource"])
def generate_resources(
    payload: ResourceGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_user),
) -> ResourceGenerateResponse:
    user_id = resolve_user_id(payload.user_id, current_user)
    resources = learning_service.generate_resources(
        db,
        user_id,
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
def ask_tutor(
    payload: TutorAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TutorAskResponse:
    answer = learning_service.ask_tutor(
        db,
        current_user.id,
        payload.question,
        payload.profile.model_dump() if payload.profile else None,
        payload.history,
    )
    return TutorAskResponse(**answer)


@router.post("/api/v1/learning/start", response_model=LearningStartResponse, tags=["workflow"])
def start_learning(
    payload: LearningStartRequest, db: Session = Depends(get_db), current_user: User | None = Depends(optional_user)
) -> LearningStartResponse:
    user_id = resolve_user_id(payload.user_id, current_user)
    profile, resources, path, nodes = learning_service.start_learning(
        db,
        user_id,
        payload.course_id,
        payload.requirement,
    )
    return LearningStartResponse(
        profile=to_profile_out(profile),
        resources=[to_resource_out(item) for item in resources],
        path=to_path_response(path, nodes),
        ml_trace=(learning_service.last_ml_result or {}).get("agent_traces", []),
        retrieval_evidence=(learning_service.last_ml_result or {}).get("retrieval_evidence", []),
        generation_quality=(learning_service.last_ml_result or {}).get("generation_quality"),
    )


def _check_redis(redis_url: str) -> bool:
    try:
        import redis

        client = redis.Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
        return bool(client.ping())
    except Exception:
        return False
def to_user_out(user: User) -> UserOut:
    return UserOut(id=user.id, username=user.username, display_name=user.display_name, role=user.role)


def resolve_user_id(payload_user_id: int | None, current_user: User | None) -> int:
    return current_user.id if current_user else payload_user_id or 1


def to_import_job_out(job: ImportJob) -> ImportJobOut:
    return ImportJobOut(
        id=job.id,
        course_id=job.course_id,
        user_id=job.user_id,
        source_type=job.source_type,
        filename=job.filename,
        status=job.status,
        message=job.message,
        result=job.result,
    )

