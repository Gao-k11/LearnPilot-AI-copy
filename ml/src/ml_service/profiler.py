from __future__ import annotations

from collections import Counter

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
        previous_mastery: dict[str, float] | None = None,
    ) -> StudentProfile:
        mastery = {point: self._clamp(value) for point, value in (previous_mastery or {}).items()}
        for point, value in diagnostics.items():
            previous = mastery.get(point)
            mastery[point] = self._clamp(value if previous is None else previous * 0.65 + value * 0.35)
        events = events or []

        for event in events:
            signal = self._event_signal(event)
            for point in event.knowledge_points:
                previous = mastery.get(point, 0.5)
                mastery[point] = self._clamp(previous * 0.75 + signal * 0.25)

        average_mastery = sum(mastery.values()) / max(len(mastery), 1)
        risk_level = "high" if average_mastery < 0.45 else "medium" if average_mastery < 0.7 else "low"
        target_difficulty = self._clamp(average_mastery + 0.12, lower=0.25, upper=0.85)
        weak_points = [point for point, _ in sorted(mastery.items(), key=lambda item: item[1]) if mastery[point] < 0.7]
        recent_focus = self._recent_focus(events, weak_points)
        engagement_score = self._engagement(events)
        learning_velocity = self._learning_velocity(events)
        stability_score = self._stability(events)
        preference_confidence = self._preference_confidence(events, preferred_styles or [])
        forgetting_risk = self._forgetting_risk(average_mastery, stability_score, engagement_score)

        return StudentProfile(
            student_id=student_id,
            mastery=mastery,
            goals=goals or [],
            preferred_styles=list(preferred_styles or []),
            target_difficulty=target_difficulty,
            risk_level=risk_level,
            weak_points=weak_points,
            recent_focus=recent_focus,
            learning_velocity=learning_velocity,
            engagement_score=engagement_score,
            stability_score=stability_score,
            preference_confidence=preference_confidence,
            forgetting_risk=forgetting_risk,
        )

    def _event_signal(self, event: InteractionEvent) -> float:
        score_signal = 0.5 if event.score is None else self._clamp(event.score)
        completion_signal = 0.75 if event.completed else 0.35
        dwell_signal = self._clamp(event.dwell_seconds / 900)
        like_signal = 0.6 if event.liked is None else 0.8 if event.liked else 0.25
        return score_signal * 0.5 + completion_signal * 0.25 + dwell_signal * 0.15 + like_signal * 0.1

    def _clamp(self, value: float, lower: float = 0.0, upper: float = 1.0) -> float:
        return max(lower, min(upper, float(value)))

    def _recent_focus(self, events: list[InteractionEvent], weak_points: list[str]) -> list[str]:
        if not events:
            return weak_points[:3]
        counts: Counter[str] = Counter()
        for event in events[-8:]:
            for point in event.knowledge_points:
                counts[point] += 1
        ordered = [point for point, _ in counts.most_common()]
        return (ordered + [point for point in weak_points if point not in ordered])[:3]

    def _engagement(self, events: list[InteractionEvent]) -> float:
        if not events:
            return 0.5
        signals = []
        for event in events:
            completion = 1.0 if event.completed else 0.35
            dwell = self._clamp(event.dwell_seconds / 900)
            liked = 0.6 if event.liked is None else 1.0 if event.liked else 0.2
            signals.append(completion * 0.45 + dwell * 0.35 + liked * 0.2)
        return round(sum(signals) / len(signals), 4)

    def _learning_velocity(self, events: list[InteractionEvent]) -> float:
        scored = [event.score for event in events if event.score is not None]
        if not scored:
            return 0.5
        recent = scored[-3:]
        return round(self._clamp(sum(recent) / len(recent)), 4)

    def _stability(self, events: list[InteractionEvent]) -> float:
        scored = [float(event.score) for event in events if event.score is not None]
        if len(scored) < 2:
            return 0.5
        mean = sum(scored) / len(scored)
        variance = sum((score - mean) ** 2 for score in scored) / len(scored)
        return round(self._clamp(1.0 - variance * 4), 4)

    def _preference_confidence(self, events: list[InteractionEvent], preferred_styles: list[str]) -> float:
        if not preferred_styles:
            return 0.0
        evidence = len([event for event in events if event.liked is not None or event.completed])
        return round(self._clamp(0.35 + evidence / 12), 4)

    def _forgetting_risk(self, average_mastery: float, stability_score: float, engagement_score: float) -> float:
        risk = (1.0 - average_mastery) * 0.5 + (1.0 - stability_score) * 0.3 + (1.0 - engagement_score) * 0.2
        return round(self._clamp(risk), 4)
