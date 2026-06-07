from pydantic import BaseModel, Field


class ProfileAnalyzeRequest(BaseModel):
    user_id: int = Field(default=1, description="学生用户 ID")
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
    user_id: int = 1
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
    user_id: int = 1
    question: str
    profile: StudentProfileOut | None = None
    history: list[str] = []


class TutorAskResponse(BaseModel):
    answer: str
    hints: list[str]
    next_action: str


class EvaluationSubmitRequest(BaseModel):
    user_id: int = 1
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


class LearningStartRequest(BaseModel):
    user_id: int = 1
    course_id: int | None = 1
    requirement: str


class LearningStartResponse(BaseModel):
    profile: StudentProfileOut
    resources: list[ResourceOut]
    path: PathPlanResponse
