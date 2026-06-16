from pydantic import BaseModel, Field


class AuthRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6)
    display_name: str | None = None
    role: str = Field(default="student", pattern="^(student|teacher|admin)$")


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfileAnalyzeRequest(BaseModel):
    user_id: int | None = Field(default=None, description="学生用户 ID；认证后可省略")
    text: str = Field(..., description="学生自然语言学习需求")


class StudentProfileOut(BaseModel):
    major: str | None = None
    grade: str | None = None
    course: str | None = None
    goal: str | None = None
    weak_points: list[str] = []
    preference: str | None = None
    cognitive_style: str | None = None
    knowledge_level: str | None = None


class ProfileAnalyzeResponse(BaseModel):
    profile_id: int | None = None
    profile: StudentProfileOut


class ResourceGenerateRequest(BaseModel):
    user_id: int | None = None
    course_id: int | None = 1
    topic: str
    weak_points: list[str] = []
    resource_types: list[str] = Field(
        default=["lecture", "mind_map", "exercise", "reading", "code_example", "video_script"]
    )


class ResourceOut(BaseModel):
    id: int | None = None
    title: str
    resource_type: str
    content: str
    review_status: str = "approved"
    review_notes: str | None = None


class ResourceGenerateResponse(BaseModel):
    resources: list[ResourceOut]


class PathPlanRequest(BaseModel):
    user_id: int = 1
    course_id: int | None = 1
    goal: str
    weak_points: list[str] = []
    resource_ids: list[int] = []


class PathNodeOut(BaseModel):
    id: int | None = None
    step_order: int
    title: str
    objective: str
    estimated_minutes: int
    resource_id: int | None = None


class PathPlanResponse(BaseModel):
    path_id: int | None = None
    title: str
    goal: str
    nodes: list[PathNodeOut]


class TutorAskRequest(BaseModel):
    user_id: int | None = None
    course_id: int | None = None
    question: str
    profile: StudentProfileOut | None = None
    history: list[str] = []


class TutorAskResponse(BaseModel):
    answer: str
    hints: list[str]
    next_action: str


class EvaluationSubmitRequest(BaseModel):
    user_id: int | None = None
    course_id: int | None = None
    path_id: int | None = None
    correct_count: int = Field(ge=0)
    total_count: int = Field(gt=0)
    completed_resource_count: int = Field(ge=0, default=0)
    study_minutes: int = Field(ge=0, default=0)


class EvaluationSubmitResponse(BaseModel):
    evaluation_id: int | None = None
    mastery_score: float
    feedback: str
    profile_update: dict
    path_adjustment: str | None = None
    updated_profile: dict | None = None


class LearningStartRequest(BaseModel):
    user_id: int | None = None
    course_id: int | None = 1
    requirement: str


class LearningStartResponse(BaseModel):
    profile: StudentProfileOut
    resources: list[ResourceOut]
    path: PathPlanResponse
    ml_trace: list[dict] = []
    retrieval_evidence: list[dict] = []
    generation_quality: dict | None = None


class ResourceImportRequest(BaseModel):
    filename: str
    source_type: str = Field(default="markdown", pattern="^(markdown|pdf_text|question_json|mistake_json)$")
    content: str


class ImportJobOut(BaseModel):
    id: int
    course_id: int
    user_id: int
    source_type: str
    filename: str
    status: str
    message: str | None = None
    result: dict | None = None


class CourseResourceOut(BaseModel):
    id: int
    course_id: int
    knowledge_point_id: int | None = None
    title: str
    resource_type: str
    content: str
    source: str | None = None
    source_type: str
    status: str
    version: str


class QuestionOut(BaseModel):
    id: int
    course_id: int
    knowledge_point_id: int | None = None
    question_type: str
    stem: str
    answer: str | None = None
    explanation: str | None = None
    difficulty: float
    source: str | None = None
