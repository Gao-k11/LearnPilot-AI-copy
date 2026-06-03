from __future__ import annotations

from .models import InteractionEvent, StudentProfile


class StudentProfiler:
    """Builds a compact student profile from diagnostics and behavior logs."""

    def build_profile(
        self,
        student_id: str,
        diagnostics: dict[str, float],
        events: list[InteractionEvent] | None = None,
        goals: list[str] | None = None,
        preferred_styles: list[str] | None = None,
    ) -> StudentProfile:
        mastery = {point: self._clamp(value) for point, value in diagnostics.items()}
        events = events or []

        for event in events:
            signal = self._event_signal(event)
            for point in event.knowledge_points:
                previous = mastery.get(point, 0.5)
                mastery[point] = self._clamp(previous * 0.75 + signal * 0.25)

        average_mastery = sum(mastery.values()) / max(len(mastery), 1)
        risk_level = "high" if average_mastery < 0.45 else "medium" if average_mastery < 0.7 else "low"
        target_difficulty = self._clamp(average_mastery + 0.12, lower=0.25, upper=0.85)

        return StudentProfile(
            student_id=student_id,
            mastery=mastery,
            goals=goals or [],
            preferred_styles=list(preferred_styles or []),
            target_difficulty=target_difficulty,
            risk_level=risk_level,
        )

    def _event_signal(self, event: InteractionEvent) -> float:
        score_signal = 0.5 if event.score is None else self._clamp(event.score)
        completion_signal = 0.75 if event.completed else 0.35
        dwell_signal = self._clamp(event.dwell_seconds / 900)
        like_signal = 0.6 if event.liked is None else 0.8 if event.liked else 0.25
        return score_signal * 0.5 + completion_signal * 0.25 + dwell_signal * 0.15 + like_signal * 0.1

    def _clamp(self, value: float, lower: float = 0.0, upper: float = 1.0) -> float:
        return max(lower, min(upper, float(value)))
