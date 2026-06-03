from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


LearningStyle = Literal["video", "text", "example", "quiz", "project"]


@dataclass(frozen=True)
class InteractionEvent:
    student_id: str
    resource_id: str
    knowledge_points: tuple[str, ...]
    score: float | None = None
    completed: bool = False
    dwell_seconds: int = 0
    liked: bool | None = None


@dataclass(frozen=True)
class LearningResource:
    resource_id: str
    title: str
    knowledge_points: tuple[str, ...]
    difficulty: float
    style: LearningStyle
    estimated_minutes: int
    quality: float = 0.8
    url: str | None = None


@dataclass(frozen=True)
class KnowledgeNode:
    name: str
    prerequisites: tuple[str, ...] = ()
    importance: float = 1.0


@dataclass
class StudentProfile:
    student_id: str
    mastery: dict[str, float] = field(default_factory=dict)
    goals: list[str] = field(default_factory=list)
    preferred_styles: list[LearningStyle] = field(default_factory=list)
    target_difficulty: float = 0.5
    risk_level: Literal["low", "medium", "high"] = "medium"


@dataclass(frozen=True)
class Recommendation:
    resource: LearningResource
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class LearningStep:
    knowledge_point: str
    target_mastery: float
    resources: tuple[Recommendation, ...]
    rationale: str
