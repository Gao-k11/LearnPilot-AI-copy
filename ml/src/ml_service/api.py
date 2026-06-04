from __future__ import annotations

try:
    from fastapi import FastAPI
    from pydantic import BaseModel, Field, field_validator
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Please run `pip install -r ml/requirements.txt` before starting the API service.") from exc

from .demo_cases import DEMO_CASES
from .models import LearningStyle
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


class RecommendRequest(BaseModel):
    student: StudentRequest
    top_k: int = Field(default=6, ge=1, le=20)


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


class FeedbackRequest(BaseModel):
    student: StudentRequest
    feedback_events: list[InteractionEventRequest]
    top_k: int = Field(default=6, ge=1, le=20)


app = FastAPI(title="Personalized Learning ML Service", version="1.0.0")
pipeline = LearningMLPipeline()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/demo-cases")
def demo_cases() -> dict:
    return DEMO_CASES


@app.post("/diagnose")
def diagnose(request: DiagnoseRequest) -> dict:
    return pipeline.diagnose(request.answers)


@app.post("/recommend")
def recommend(request: RecommendRequest) -> dict:
    return pipeline.run_learning_loop(
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
    result = pipeline.run_learning_loop(
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
    return pipeline.feedback_loop(
        student_id=request.student.student_id,
        diagnostics=request.student.diagnostics,
        feedback_events=_events_from_dicts(request.feedback_events, request.student.student_id),
        goals=request.student.goals,
        preferred_styles=request.student.preferred_styles,
        previous_mastery=request.student.previous_mastery,
        top_k=request.top_k,
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
