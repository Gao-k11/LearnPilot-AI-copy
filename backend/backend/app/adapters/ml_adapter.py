from typing import Any

from backend.app.adapters.ml_service_client import MLServiceClient, MLServiceUnavailable


class MockMLAdapter:
    """ML adapter. It prefers the external LearnPilot-AI service and falls back to local mock logic."""

    def __init__(self, client: MLServiceClient | None = None) -> None:
        self.client = client or MLServiceClient()

    def diagnose_weakness(self, profile: dict) -> list[dict]:
        try:
            data = self.client.diagnose({"profile": profile})
            weaknesses = self._extract_weaknesses(data)
            if weaknesses:
                return weaknesses
        except MLServiceUnavailable:
            pass
        except Exception:
            pass
        return self._mock_diagnose_weakness(profile)

    def recommend_learning(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return self.client.recommend(payload)
        except MLServiceUnavailable:
            return None
        except Exception:
            return None

    def generate_cards(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return self.client.generate(payload)
        except MLServiceUnavailable:
            return None
        except Exception:
            return None

    def plan_path(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return self.client.path(payload)
        except MLServiceUnavailable:
            return None
        except Exception:
            return None

    def evaluate_mastery(
        self,
        correct_count: int,
        total_count: int,
        completed_resource_count: int,
        study_minutes: int,
    ) -> dict:
        payload = {
            "correct_count": correct_count,
            "total_count": total_count,
            "completed_resource_count": completed_resource_count,
            "study_minutes": study_minutes,
        }
        try:
            data = self.client.feedback(payload)
            normalized = self._normalize_evaluation(data)
            if normalized:
                return normalized
        except MLServiceUnavailable:
            pass
        except Exception:
            pass
        return self._mock_evaluate_mastery(correct_count, total_count, completed_resource_count, study_minutes)

    def _extract_weaknesses(self, data: dict[str, Any]) -> list[dict]:
        raw_items = (
            data.get("weaknesses")
            or data.get("weak_points")
            or data.get("knowledge_gaps")
            or data.get("diagnosis", {}).get("weaknesses")
            or data.get("diagnosis", {}).get("weak_points")
            or []
        )
        if isinstance(raw_items, dict):
            raw_items = list(raw_items.values())

        weaknesses = []
        for index, item in enumerate(raw_items):
            if isinstance(item, str):
                weaknesses.append(
                    {
                        "knowledge_point": item,
                        "weakness_level": max(0.45, 0.85 - index * 0.08),
                        "evidence": "LearnPilot-AI diagnosis",
                    }
                )
            elif isinstance(item, dict):
                point = (
                    item.get("knowledge_point")
                    or item.get("point")
                    or item.get("name")
                    or item.get("topic")
                    or item.get("label")
                )
                if point:
                    weaknesses.append(
                        {
                            "knowledge_point": str(point),
                            "weakness_level": float(item.get("weakness_level") or item.get("score") or 0.7),
                            "evidence": str(item.get("evidence") or item.get("reason") or "LearnPilot-AI diagnosis"),
                        }
                    )
        return weaknesses

    def _normalize_evaluation(self, data: dict[str, Any]) -> dict | None:
        score = (
            data.get("mastery_score")
            or data.get("score")
            or data.get("mastery")
            or data.get("result", {}).get("mastery_score")
            or data.get("result", {}).get("score")
        )
        if score is None:
            return None
        score = float(score)
        if score > 1:
            score = score / 100
        return {
            "mastery_score": round(max(0.0, min(1.0, score)), 2),
            "feedback": str(data.get("feedback") or data.get("message") or data.get("summary") or "ML service feedback"),
            "profile_update": data.get("profile_update") or data.get("updated_profile") or {},
        }

    def _mock_diagnose_weakness(self, profile: dict) -> list[dict]:
        weak_points = profile.get("weak_points") or ["基础概念"]
        return [
            {
                "knowledge_point": point,
                "weakness_level": max(0.45, 0.85 - index * 0.08),
                "evidence": "由学生自述和学习目标推断",
            }
            for index, point in enumerate(weak_points)
        ]

    def _mock_evaluate_mastery(
        self,
        correct_count: int,
        total_count: int,
        completed_resource_count: int,
        study_minutes: int,
    ) -> dict:
        accuracy = correct_count / total_count
        completion_bonus = min(completed_resource_count * 0.03, 0.12)
        time_bonus = min(study_minutes / 600, 0.08)
        score = round(min(1.0, accuracy * 0.8 + completion_bonus + time_bonus), 2)
        if score >= 0.85:
            feedback = "掌握较好，可以进入综合应用和迁移训练。"
        elif score >= 0.65:
            feedback = "基础已建立，建议继续强化薄弱知识点和错题复盘。"
        else:
            feedback = "掌握度偏低，建议回到核心概念并配合分步练习。"
        return {
            "mastery_score": score,
            "feedback": feedback,
            "profile_update": {"knowledge_level": "中级" if score >= 0.75 else "入门强化"},
        }
