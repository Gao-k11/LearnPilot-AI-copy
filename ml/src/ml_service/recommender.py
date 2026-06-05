from __future__ import annotations

from collections import Counter

from .models import LearningResource, Recommendation, StudentProfile


class ResourceRecommender:
    """Explainable rule-based ranking baseline for the competition demo."""

    def recommend(
        self,
        profile: StudentProfile,
        resources: list[LearningResource],
        top_k: int = 6,
        exclude_ids: set[str] | None = None,
    ) -> list[Recommendation]:
        exclude_ids = exclude_ids or set()
        ranked = [
            self._score_resource(profile, resource)
            for resource in resources
            if resource.resource_id not in exclude_ids
        ]
        ranked.sort(key=lambda item: item.score, reverse=True)
        return self._diversify(ranked, top_k)

    def _score_resource(self, profile: StudentProfile, resource: LearningResource) -> Recommendation:
        weakness = self._weakness_match(profile, resource)
        difficulty_fit = 1.0 - abs(profile.target_difficulty - resource.difficulty)
        style_fit = 1.0 if resource.style in profile.preferred_styles else 0.65
        duration_fit = 1.0 if resource.estimated_minutes <= 25 else 0.82 if resource.estimated_minutes <= 45 else 0.65
        score = (
            weakness * 0.42
            + difficulty_fit * 0.24
            + style_fit * 0.14
            + resource.quality * 0.14
            + duration_fit * 0.06
        )

        reasons = [
            f"匹配薄弱知识点 {', '.join(resource.knowledge_points)}",
            f"难度 {resource.difficulty:.2f} 接近目标难度 {profile.target_difficulty:.2f}",
        ]
        if resource.style in profile.preferred_styles:
            reasons.append(f"符合偏好的学习形式：{resource.style}")
        return Recommendation(resource=resource, score=round(score, 4), reasons=tuple(reasons))

    def score_resource(self, profile: StudentProfile, resource: LearningResource) -> Recommendation:
        return self._score_resource(profile, resource)

    def _weakness_match(self, profile: StudentProfile, resource: LearningResource) -> float:
        if not resource.knowledge_points:
            return 0.0
        gaps = [1.0 - profile.mastery.get(point, 0.5) for point in resource.knowledge_points]
        return sum(gaps) / len(gaps)

    def _diversify(self, ranked: list[Recommendation], top_k: int) -> list[Recommendation]:
        selected: list[Recommendation] = []
        point_counts: Counter[str] = Counter()
        style_counts: Counter[str] = Counter()

        for item in ranked:
            repeated_points = sum(point_counts[point] for point in item.resource.knowledge_points)
            repeated_style = style_counts[item.resource.style]
            penalty = repeated_points * 0.03 + repeated_style * 0.04
            adjusted = Recommendation(item.resource, round(item.score - penalty, 4), item.reasons)
            selected.append(adjusted)
            for point in item.resource.knowledge_points:
                point_counts[point] += 1
            style_counts[item.resource.style] += 1
            selected.sort(key=lambda rec: rec.score, reverse=True)
            selected = selected[:top_k]

        return selected
