from __future__ import annotations

from typing import Any

try:
    from fastapi import FastAPI
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Please run `pip install -r ml/requirements.txt` before starting the API service.") from exc

from .demo_cases import DEMO_CASES
from .models import InteractionEvent
from .pipeline import LearningMLPipeline


class StudentRequest(BaseModel):
    student_id: str = Field(examples=["stu_001"])
    diagnostics: dict[str, float] = Field(default_factory=dict)
    goals: list[str] = Field(default_factory=list)
    preferred_styles: list[str] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


class RecommendRequest(BaseModel):
    student: StudentRequest
    top_k: int = 6


class DiagnoseRequest(BaseModel):
    answers: dict[str, float]


class GenerateRequest(BaseModel):
    student: StudentRequest


class FeedbackRequest(BaseModel):
    student: StudentRequest
    feedback_events: list[dict[str, Any]]
    top_k: int = 6


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
        top_k=request.top_k,
    )


def _events_from_dicts(events: list[dict[str, Any]], fallback_student_id: str) -> list[InteractionEvent]:
    return [
        InteractionEvent(
            student_id=event.get("student_id", fallback_student_id),
            resource_id=event.get("resource_id", ""),
            knowledge_points=tuple(event.get("knowledge_points", [])),
            score=event.get("score"),
            completed=event.get("completed", False),
            dwell_seconds=event.get("dwell_seconds", 0),
            liked=event.get("liked"),
        )
        for event in events
    ]
