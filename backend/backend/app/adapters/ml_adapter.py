from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.adapters.ml_service_client import MLServiceClient, MLServiceUnavailable
from backend.app.models import Course, CourseResource, FeedbackEvent, KnowledgePoint, StudentProfile, StudentWeakness


STYLE_MAP = {
    "lecture": "video",
    "video_script": "video",
    "reading": "text",
    "review_card": "text",
    "mind_map": "text",
    "exercise": "quiz",
    "code_example": "project",
}

DIFFICULTY_MAP = {
    "easy": 0.3,
    "medium": 0.55,
    "hard": 0.8,
}

DEFAULT_STYLES = ["example", "quiz", "text"]


class MLAdapter:
    """Bridge backend database state to the LearnPilot-AI ML HTTP service."""

    def __init__(self, client: MLServiceClient | None = None) -> None:
        self.client = client or MLServiceClient()
        self.last_fallback_reason: str | None = None

    def build_recommend_payload(
        self,
        db: Session,
        user_id: int,
        course_id: int | None,
        requirement: str,
    ) -> dict[str, Any]:
        profile = self._latest_profile(db, user_id)
        weaknesses = self._latest_weaknesses(db, user_id, profile.id if profile else None)
        knowledge_points = self._knowledge_points(db, course_id)
        resources = self._resources(db, course_id, knowledge_points)

        diagnostics = self._diagnostics_from_weaknesses(weaknesses)
        if not diagnostics:
            diagnostics = self._diagnostics_from_requirement(requirement, knowledge_points)

        previous_mastery = {
            point: round(max(0.0, min(1.0, score)), 4)
            for point, score in diagnostics.items()
        }
        goals = [requirement]
        if profile and profile.goal and profile.goal not in goals:
            goals.append(profile.goal)

        return {
            "student": {
                "student_id": str(user_id),
                "diagnostics": diagnostics,
                "goals": goals,
                "preferred_styles": self._preferred_styles(profile),
                "events": [],
                "previous_mastery": previous_mastery,
            },
            "top_k": 6,
            "resources": resources,
            "knowledge_graph": self._knowledge_graph(knowledge_points),
            "course_context": self._course_context(db, course_id, requirement),
        }

    def recommend_learning(
        self,
        db: Session | None = None,
        user_id: int | None = None,
        course_id: int | None = None,
        requirement: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        try:
            if payload is None and isinstance(db, dict):
                payload = db
                db = None
            if payload is None:
                if db is None or user_id is None or requirement is None:
                    raise ValueError("db, user_id and requirement are required when payload is not provided")
                payload = self.build_recommend_payload(db, user_id, course_id, requirement)
            data = self.client.recommend(payload)
            self.last_fallback_reason = None
            return self.normalize_ml_result(data)
        except MLServiceUnavailable as exc:
            self.last_fallback_reason = str(exc)
            return None
        except Exception as exc:
            self.last_fallback_reason = str(exc)
            return None

    def normalize_ml_result(self, data: dict[str, Any]) -> dict[str, Any]:
        result = data.get("result") if isinstance(data.get("result"), dict) else data
        if not isinstance(result, dict):
            return {}

        normalized = dict(result)
        profile = normalized.get("profile") if isinstance(normalized.get("profile"), dict) else {}
        if profile:
            profile.setdefault("goal", "; ".join(profile.get("goals", [])) if isinstance(profile.get("goals"), list) else None)
            profile.setdefault("course", None)
            profile.setdefault("preference", ", ".join(profile.get("preferred_styles", [])) if isinstance(profile.get("preferred_styles"), list) else None)
            profile.setdefault("knowledge_level", profile.get("learning_stage"))
            normalized["profile"] = profile

        normalized["weak_points"] = self._extract_weak_points(normalized, profile)
        normalized["resources"] = self._normalize_resources(normalized)
        return normalized

    def diagnose_weakness(self, profile: dict) -> list[dict]:
        weak_points = profile.get("weak_points") or profile.get("weaknesses") or []
        if weak_points:
            return self._weak_points_to_items(weak_points, "Student profile")
        return self._mock_diagnose_weakness(profile)

    def generate_cards(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return self.client.generate(payload)
        except Exception as exc:
            self.last_fallback_reason = str(exc)
            return None

    def feedback_learning(
        self,
        db: Session,
        user_id: int,
        course_id: int | None,
        feedback_events: list[FeedbackEvent],
        top_k: int = 6,
    ) -> dict[str, Any] | None:
        try:
            profile = self._latest_profile(db, user_id)
            weaknesses = self._latest_weaknesses(db, user_id, profile.id if profile else None)
            knowledge_points = self._knowledge_points(db, course_id)
            diagnostics = self._diagnostics_from_profile(profile) or self._diagnostics_from_weaknesses(weaknesses)
            if not diagnostics:
                diagnostics = {point.name: 0.5 for point in knowledge_points} or {"general_foundation": 0.45}
            payload = {
                "student": {
                    "student_id": str(user_id),
                    "diagnostics": diagnostics,
                    "goals": [profile.goal] if profile and profile.goal else [],
                    "preferred_styles": self._preferred_styles(profile),
                    "events": [],
                    "previous_mastery": self._diagnostics_from_profile(profile),
                },
                "feedback_events": [self._feedback_event_payload(event) for event in feedback_events],
                "top_k": top_k,
                "resources": self._resources(db, course_id, knowledge_points),
                "knowledge_graph": self._knowledge_graph(knowledge_points),
                "course_context": self._course_context(db, course_id, profile.goal if profile and profile.goal else ""),
            }
            data = self.client.feedback(payload)
            self.last_fallback_reason = None
            return data
        except Exception as exc:
            self.last_fallback_reason = str(exc)
            return None

    def plan_path(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            return self.client.path(payload)
        except Exception as exc:
            self.last_fallback_reason = str(exc)
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
        except Exception as exc:
            self.last_fallback_reason = str(exc)
        return self._mock_evaluate_mastery(correct_count, total_count, completed_resource_count, study_minutes)

    def _diagnostics_from_profile(self, profile: StudentProfile | None) -> dict[str, float]:
        if profile and isinstance(profile.mastery, dict):
            return {
                str(point): round(max(0.0, min(1.0, float(score))), 4)
                for point, score in profile.mastery.items()
                if isinstance(score, int | float)
            }
        return {}

    def _feedback_event_payload(self, event: FeedbackEvent) -> dict[str, Any]:
        return {
            "resource_id": f"learning_resource:{event.resource_id}" if event.resource_id else "",
            "knowledge_points": event.knowledge_points or [],
            "score": event.score,
            "completed": event.completed,
            "dwell_seconds": event.dwell_seconds,
            "liked": event.liked,
        }

    def _latest_profile(self, db: Session, user_id: int) -> StudentProfile | None:
        return (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id == user_id)
            .order_by(StudentProfile.id.desc())
            .first()
        )

    def _latest_weaknesses(self, db: Session, user_id: int, profile_id: int | None) -> list[StudentWeakness]:
        query = db.query(StudentWeakness).filter(StudentWeakness.user_id == user_id)
        if profile_id is not None:
            profile_items = query.filter(StudentWeakness.profile_id == profile_id).all()
            if profile_items:
                return profile_items
        return query.order_by(StudentWeakness.id.desc()).limit(20).all()

    def _knowledge_points(self, db: Session, course_id: int | None) -> list[KnowledgePoint]:
        query = db.query(KnowledgePoint)
        if course_id is not None:
            query = query.filter(KnowledgePoint.course_id == course_id)
        return query.order_by(KnowledgePoint.id.asc()).all()

    def _resources(
        self,
        db: Session,
        course_id: int | None,
        knowledge_points: list[KnowledgePoint],
    ) -> list[dict[str, Any]]:
        point_by_id = {item.id: item for item in knowledge_points}
        query = db.query(CourseResource)
        if course_id is not None:
            query = query.filter(CourseResource.course_id == course_id)
        resources = []
        for item in query.order_by(CourseResource.id.asc()).all():
            point = point_by_id.get(item.knowledge_point_id)
            point_name = point.name if point else item.title
            difficulty = self._difficulty_value(point.difficulty if point else None)
            resources.append(
                {
                    "resource_id": f"course_resource:{item.id}",
                    "title": item.title,
                    "knowledge_points": [point_name],
                    "difficulty": difficulty,
                    "style": STYLE_MAP.get(item.resource_type, "text"),
                    "estimated_minutes": self._estimated_minutes(item.resource_type),
                    "quality": 0.86,
                    "content": item.content,
                    "tags": [item.resource_type, "backend_course_resource"],
                }
            )
        return resources

    def _knowledge_graph(self, knowledge_points: list[KnowledgePoint]) -> list[dict[str, Any]]:
        point_by_id = {item.id: item for item in knowledge_points}
        nodes = []
        for item in knowledge_points:
            prerequisites = []
            if item.parent_id and item.parent_id in point_by_id:
                prerequisites.append(point_by_id[item.parent_id].name)
            nodes.append(
                {
                    "name": item.name,
                    "prerequisites": prerequisites,
                    "importance": 1.2 if item.difficulty == "hard" else 1.0,
                }
            )
        return nodes

    def _course_context(self, db: Session, course_id: int | None, requirement: str) -> dict[str, Any]:
        course = db.get(Course, course_id) if course_id is not None else None
        return {
            "course_id": course_id,
            "course_name": course.name if course else None,
            "requirement": requirement,
        }

    def _diagnostics_from_weaknesses(self, weaknesses: list[StudentWeakness]) -> dict[str, float]:
        return {
            item.knowledge_point: round(max(0.0, min(1.0, 1.0 - float(item.weakness_level))), 4)
            for item in weaknesses
        }

    def _diagnostics_from_requirement(self, requirement: str, knowledge_points: list[KnowledgePoint]) -> dict[str, float]:
        diagnostics = {}
        for point in knowledge_points:
            diagnostics[point.name] = 0.35 if point.name and point.name in requirement else 0.62
        if diagnostics:
            return diagnostics
        return {"general_foundation": 0.45}

    def _preferred_styles(self, profile: StudentProfile | None) -> list[str]:
        text = " ".join(
            value
            for value in [
                profile.preference if profile else None,
                profile.cognitive_style if profile else None,
            ]
            if value
        ).lower()
        styles = []
        if any(token in text for token in ["video", "视频", "讲解"]):
            styles.append("video")
        if any(token in text for token in ["quiz", "exercise", "练习", "题"]):
            styles.append("quiz")
        if any(token in text for token in ["example", "案例", "例"]):
            styles.append("example")
        if any(token in text for token in ["project", "项目", "实战"]):
            styles.append("project")
        if any(token in text for token in ["text", "阅读", "文档"]):
            styles.append("text")
        return styles or DEFAULT_STYLES

    def _extract_weak_points(self, data: dict[str, Any], profile: dict | None = None) -> list[str]:
        raw_items = (
            (profile or {}).get("weak_points")
            or data.get("weak_points")
            or data.get("weaknesses")
            or data.get("knowledge_gaps")
            or data.get("diagnosis", {}).get("weak_points")
            or data.get("diagnosis", {}).get("weaknesses")
            or []
        )
        weak_points = []
        if isinstance(raw_items, dict):
            raw_items = list(raw_items.values())
        for item in raw_items:
            if isinstance(item, str):
                weak_points.append(item)
            elif isinstance(item, dict):
                point = item.get("knowledge_point") or item.get("point") or item.get("name") or item.get("topic")
                if point:
                    weak_points.append(str(point))
        return weak_points

    def _normalize_resources(self, data: dict[str, Any]) -> list[dict[str, str]]:
        raw_items = data.get("generated_cards") or data.get("resources") or data.get("recommendations") or []
        if isinstance(raw_items, dict):
            raw_items = list(raw_items.values())
        resources = []
        for index, item in enumerate(raw_items, start=1):
            if not isinstance(item, dict):
                continue
            content = (
                item.get("content")
                or item.get("explanation")
                or item.get("snippet")
                or item.get("summary")
                or self._card_to_content(item)
            )
            if not content:
                continue
            resources.append(
                {
                    "title": str(item.get("title") or item.get("source_title") or f"ML resource {index}"),
                    "resource_type": str(item.get("resource_type") or item.get("style") or "reading"),
                    "content": str(content),
                }
            )
        return resources

    def _card_to_content(self, item: dict[str, Any]) -> str:
        parts = [
            item.get("explanation"),
            item.get("example"),
            item.get("practice"),
            item.get("answer"),
            item.get("mistake_analysis"),
            item.get("review_tip"),
        ]
        return "\n\n".join(str(part) for part in parts if part)

    def _weak_points_to_items(self, weak_points: list[Any], evidence: str) -> list[dict]:
        items = []
        for index, point in enumerate(weak_points):
            if isinstance(point, dict):
                name = point.get("knowledge_point") or point.get("name") or point.get("point")
                weakness_level = float(point.get("weakness_level") or 0.7)
            else:
                name = str(point)
                weakness_level = max(0.45, 0.85 - index * 0.08)
            if name:
                items.append({"knowledge_point": name, "weakness_level": weakness_level, "evidence": evidence})
        return items

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
        return self._weak_points_to_items(weak_points, "Local fallback diagnosis")

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

    def _difficulty_value(self, difficulty: str | None) -> float:
        return DIFFICULTY_MAP.get((difficulty or "medium").lower(), 0.55)

    def _estimated_minutes(self, resource_type: str) -> int:
        return {
            "lecture": 25,
            "video_script": 18,
            "reading": 20,
            "review_card": 12,
            "mind_map": 15,
            "exercise": 30,
            "code_example": 40,
        }.get(resource_type, 25)


MockMLAdapter = MLAdapter
