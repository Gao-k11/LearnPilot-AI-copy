from __future__ import annotations

try:
    from fastapi import FastAPI
    from pydantic import BaseModel, Field, field_validator
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Please run `pip install -r ml/requirements.txt` before starting the API service.") from exc

from .demo_cases import DEMO_CASES
from .evaluation import run_builtin_evaluation
from .models import KnowledgeNode, LearningResource, LearningStyle
from .models import InteractionEvent
from .pipeline import LearningMLPipeline


class InteractionEventRequest(BaseModel):
    student_id: str | None = None
    resource_id: str = ""
    knowledge_points: list[str] = Field(default_factory=list)
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    completed: bool = False
    dwell_seconds: int = Field(default=0, ge=0)
    liked: bool | None = None


class StudentRequest(BaseModel):
    student_id: str = Field(examples=["stu_001"])
    diagnostics: dict[str, float] = Field(default_factory=dict)
    goals: list[str] = Field(default_factory=list)
    preferred_styles: list[LearningStyle] = Field(default_factory=list)
    events: list[InteractionEventRequest] = Field(default_factory=list)
    previous_mastery: dict[str, float] = Field(default_factory=dict)

    @field_validator("diagnostics", "previous_mastery")
    @classmethod
    def validate_mastery_scores(cls, value: dict[str, float]) -> dict[str, float]:
        invalid = {point: score for point, score in value.items() if score < 0.0 or score > 1.0}
        if invalid:
            raise ValueError(f"mastery scores must be in [0, 1], invalid={invalid}")
        return value


class ResourceRequest(BaseModel):
    resource_id: str
    title: str
    knowledge_points: list[str] = Field(default_factory=list)
    difficulty: float = Field(default=0.55, ge=0.0, le=1.0)
    style: LearningStyle = "text"
    estimated_minutes: int = Field(default=25, ge=1, le=600)
    quality: float = Field(default=0.8, ge=0.0, le=1.0)
    url: str | None = None
    content: str = ""
    prerequisites_covered: list[str] = Field(default_factory=list)
    audience: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    question: str = ""
    answer: str = ""
    explanation: str = ""


class KnowledgeNodeRequest(BaseModel):
    name: str
    prerequisites: list[str] = Field(default_factory=list)
    importance: float = Field(default=1.0, ge=0.0, le=3.0)


class CourseContextRequest(BaseModel):
    course_id: int | str | None = None
    course_name: str | None = None
    requirement: str | None = None


class RecommendRequest(BaseModel):
    student: StudentRequest
    top_k: int = Field(default=6, ge=1, le=20)
    resources: list[ResourceRequest] | None = None
    knowledge_graph: list[KnowledgeNodeRequest] | None = None
    course_context: CourseContextRequest | None = None


class DiagnoseRequest(BaseModel):
    answers: dict[str, float]

    @field_validator("answers")
    @classmethod
    def validate_answers(cls, value: dict[str, float]) -> dict[str, float]:
        invalid = {point: score for point, score in value.items() if score < 0.0 or score > 1.0}
        if invalid:
            raise ValueError(f"answers must be in [0, 1], invalid={invalid}")
        return value


class GenerateRequest(BaseModel):
    student: StudentRequest
    resources: list[ResourceRequest] | None = None
    knowledge_graph: list[KnowledgeNodeRequest] | None = None
    course_context: CourseContextRequest | None = None


class FeedbackRequest(BaseModel):
    student: StudentRequest
    feedback_events: list[InteractionEventRequest]
    top_k: int = Field(default=6, ge=1, le=20)
    resources: list[ResourceRequest] | None = None
    knowledge_graph: list[KnowledgeNodeRequest] | None = None
    course_context: CourseContextRequest | None = None


class UpdateProfileRequest(BaseModel):
    student: StudentRequest


app = FastAPI(title="Personalized Learning ML Service", version="1.0.0")
pipeline = LearningMLPipeline()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/demo-cases")
def demo_cases() -> dict:
    return DEMO_CASES


@app.get("/train/status")
def train_status() -> dict:
    return pipeline.recommendation_agent.status()


@app.get("/evaluate")
def evaluate() -> dict:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    return run_builtin_evaluation(root, write_report=False)


@app.post("/diagnose")
def diagnose(request: DiagnoseRequest) -> dict:
    return pipeline.diagnose(request.answers)


@app.post("/recommend")
def recommend(request: RecommendRequest) -> dict:
    active_pipeline = _pipeline_for_request(request.resources, request.knowledge_graph)
    return active_pipeline.run_learning_loop(
        student_id=request.student.student_id,
        diagnostics=request.student.diagnostics,
        events=_events_from_dicts(request.student.events, request.student.student_id),
        goals=request.student.goals,
        preferred_styles=request.student.preferred_styles,
        previous_mastery=request.student.previous_mastery,
        top_k=request.top_k,
    )


@app.post("/path")
def path(request: RecommendRequest) -> dict:
    result = recommend(request)
    return {
        "profile": result["profile"],
        "learning_path": result["learning_path"],
        "knowledge_graph": result["knowledge_graph"],
        "agent_traces": [trace for trace in result["agent_traces"] if trace["agent"] == "规划 Agent"],
    }


@app.post("/generate")
def generate(request: GenerateRequest) -> dict:
    active_pipeline = _pipeline_for_request(request.resources, request.knowledge_graph)
    result = active_pipeline.run_learning_loop(
        student_id=request.student.student_id,
        diagnostics=request.student.diagnostics,
        events=_events_from_dicts(request.student.events, request.student.student_id),
        goals=request.student.goals,
        preferred_styles=request.student.preferred_styles,
        previous_mastery=request.student.previous_mastery,
        top_k=5,
    )
    return {
        "generated_cards": result["generated_cards"],
        "agent_traces": [trace for trace in result["agent_traces"] if trace["agent"] == "生成与评估 Agent"],
    }


@app.post("/feedback")
def feedback(request: FeedbackRequest) -> dict:
    active_pipeline = _pipeline_for_request(request.resources, request.knowledge_graph)
    return active_pipeline.feedback_loop(
        student_id=request.student.student_id,
        diagnostics=request.student.diagnostics,
        feedback_events=_events_from_dicts(request.feedback_events, request.student.student_id),
        goals=request.student.goals,
        preferred_styles=request.student.preferred_styles,
        previous_mastery=request.student.previous_mastery,
        top_k=request.top_k,
    )


@app.post("/student/update-profile")
def update_profile(request: UpdateProfileRequest) -> dict:
    return pipeline.update_profile(
        student_id=request.student.student_id,
        diagnostics=request.student.diagnostics,
        events=_events_from_dicts(request.student.events, request.student.student_id),
        goals=request.student.goals,
        preferred_styles=request.student.preferred_styles,
        previous_mastery=request.student.previous_mastery,
    )


def _events_from_dicts(events: list[InteractionEventRequest], fallback_student_id: str) -> list[InteractionEvent]:
    return [
        InteractionEvent(
            student_id=event.student_id or fallback_student_id,
            resource_id=event.resource_id,
            knowledge_points=tuple(event.knowledge_points),
            score=event.score,
            completed=event.completed,
            dwell_seconds=event.dwell_seconds,
            liked=event.liked,
        )
        for event in events
    ]


def _pipeline_for_request(
    resources: list[ResourceRequest] | None,
    knowledge_graph: list[KnowledgeNodeRequest] | None,
) -> LearningMLPipeline:
    if not resources and not knowledge_graph:
        return pipeline
    return LearningMLPipeline(
        resources=_resources_from_request(resources) if resources else None,
        knowledge_graph=_knowledge_graph_from_request(knowledge_graph) if knowledge_graph else None,
    )


def _resources_from_request(resources: list[ResourceRequest]) -> list[LearningResource]:
    return [
        LearningResource(
            resource_id=item.resource_id,
            title=item.title,
            knowledge_points=tuple(item.knowledge_points),
            difficulty=item.difficulty,
            style=item.style,
            estimated_minutes=item.estimated_minutes,
            quality=item.quality,
            url=item.url,
            content=item.content,
            prerequisites_covered=tuple(item.prerequisites_covered),
            audience=tuple(item.audience),
            tags=tuple(item.tags),
            question=item.question,
            answer=item.answer,
            explanation=item.explanation,
        )
        for item in resources
    ]


def _knowledge_graph_from_request(nodes: list[KnowledgeNodeRequest]) -> list[KnowledgeNode]:
    return [
        KnowledgeNode(
            name=item.name,
            prerequisites=tuple(item.prerequisites),
            importance=item.importance,
        )
        for item in nodes
    ]
