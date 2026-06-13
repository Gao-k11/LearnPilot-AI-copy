from typing import Any

from sqlalchemy.orm import Session

from backend.app.adapters.ml_adapter import MLAdapter
from backend.app.agents.diagnosis_agent import DiagnosisAgent
from backend.app.agents.evaluator_agent import EvaluatorAgent
from backend.app.agents.planner_agent import PlannerAgent
from backend.app.agents.profile_agent import ProfileAgent
from backend.app.agents.retriever_agent import RetrieverAgent
from backend.app.agents.resource_agent import ResourceAgent
from backend.app.agents.review_agent import ReviewAgent
from backend.app.agents.tutor_agent import TutorAgent
from backend.app.models import (
    ChatMessage,
    EvaluationResult,
    LearningPath,
    LearningPathNode,
    LearningResource,
    StudentProfile,
    StudentWeakness,
)


class LearningService:
    def __init__(self) -> None:
        self.profile_agent = ProfileAgent()
        self.diagnosis_agent = DiagnosisAgent()
        self.retriever_agent = RetrieverAgent()
        self.resource_agent = ResourceAgent()
        self.review_agent = ReviewAgent()
        self.planner_agent = PlannerAgent()
        self.tutor_agent = TutorAgent()
        self.evaluator_agent = EvaluatorAgent()
        self.ml_adapter = MLAdapter()

    def analyze_profile(self, db: Session, user_id: int, text: str) -> tuple[StudentProfile, dict]:
        try:
            profile = self.profile_agent.run(text)
            db_profile = (
                db.query(StudentProfile)
                .filter(StudentProfile.user_id == user_id)
                .order_by(StudentProfile.id.desc())
                .first()
            )

            if db_profile is None:
                db_profile = StudentProfile(user_id=user_id, raw_text=text)

            db_profile.major = profile.get("major")
            db_profile.grade = profile.get("grade")
            db_profile.course = profile.get("course")
            db_profile.goal = profile.get("goal")
            db_profile.preference = profile.get("preference")
            db_profile.cognitive_style = profile.get("cognitive_style")
            db_profile.knowledge_level = profile.get("knowledge_level")
            db_profile.raw_text = text

            db.add(db_profile)
            db.flush()

            db.query(StudentWeakness).filter(StudentWeakness.profile_id == db_profile.id).delete(
                synchronize_session=False
            )
            weaknesses = self.diagnosis_agent.run(profile)
            for weakness in weaknesses:
                db.add(
                    StudentWeakness(
                        user_id=user_id,
                        profile_id=db_profile.id,
                        knowledge_point=weakness["knowledge_point"],
                        weakness_level=weakness["weakness_level"],
                        evidence=weakness["evidence"],
                    )
                )

            db.flush()
            db.commit()
            db.refresh(db_profile)
            profile["weak_points"] = [item["knowledge_point"] for item in weaknesses]
            return db_profile, profile
        except Exception:
            db.rollback()
            raise

    def generate_resources(
        self,
        db: Session,
        user_id: int,
        course_id: int | None,
        topic: str,
        weak_points: list[str],
        resource_types: list[str],
        reference_titles: list[str] | None = None,
    ) -> list[LearningResource]:
        try:
            if reference_titles:
                reference_hint = f"{topic} (reference resources: {', '.join(reference_titles[:3])})"
            else:
                reference_hint = topic

            generated = self.resource_agent.run(reference_hint, weak_points, resource_types)
            resources = []
            for item in generated:
                reviewed = self.review_agent.run(item)
                resource = LearningResource(
                    user_id=user_id,
                    course_id=course_id,
                    title=reviewed["title"],
                    resource_type=reviewed["resource_type"],
                    content=reviewed["content"],
                    review_status=reviewed["review_status"],
                    review_notes=reviewed.get("review_notes"),
                )
                db.add(resource)
                resources.append(resource)

            db.flush()
            db.commit()
            for resource in resources:
                db.refresh(resource)
            return resources
        except Exception:
            db.rollback()
            raise

    def save_resource_items(
        self,
        db: Session,
        user_id: int,
        course_id: int | None,
        items: list[dict],
    ) -> list[LearningResource]:
        try:
            resources = []
            for item in items:
                reviewed = self.review_agent.run(item)
                resource = LearningResource(
                    user_id=user_id,
                    course_id=course_id,
                    title=reviewed["title"],
                    resource_type=reviewed["resource_type"],
                    content=reviewed["content"],
                    review_status=reviewed["review_status"],
                    review_notes=reviewed.get("review_notes"),
                )
                db.add(resource)
                resources.append(resource)

            db.flush()
            db.commit()
            for resource in resources:
                db.refresh(resource)
            return resources
        except Exception:
            db.rollback()
            raise

    def retrieve_course_resources(self, db: Session, course_id: int | None, weak_points: list[str]) -> list[str]:
        resources = self.retriever_agent.run(db, course_id, weak_points)
        return [item.title for item in resources]

    def plan_path(
        self,
        db: Session,
        user_id: int,
        course_id: int | None,
        goal: str,
        weak_points: list[str],
        resource_ids: list[int],
    ) -> tuple[LearningPath, list[LearningPathNode]]:
        try:
            plan = self.planner_agent.run(goal, weak_points, resource_ids)
            path = LearningPath(user_id=user_id, course_id=course_id, title=plan["title"], goal=goal)
            db.add(path)
            db.flush()

            nodes = []
            for node in plan["nodes"]:
                db_node = LearningPathNode(
                    path_id=path.id,
                    resource_id=node.get("resource_id"),
                    step_order=node["step_order"],
                    title=node["title"],
                    objective=node["objective"],
                    estimated_minutes=node["estimated_minutes"],
                )
                db.add(db_node)
                nodes.append(db_node)

            db.flush()
            db.commit()
            db.refresh(path)
            for node in nodes:
                db.refresh(node)
            return path, nodes
        except Exception:
            db.rollback()
            raise

    def start_learning(
        self,
        db: Session,
        user_id: int,
        course_id: int | None,
        requirement: str,
    ) -> tuple[dict, list[LearningResource], LearningPath, list[LearningPathNode]]:
        ml_result = self.ml_adapter.recommend_learning(
            db=db,
            user_id=user_id,
            course_id=course_id,
            requirement=requirement,
        )
        if not ml_result:
            return self._start_learning_with_local_agents(db, user_id, course_id, requirement)

        profile = self._extract_ml_profile(ml_result) or self.profile_agent.run(requirement)
        weak_points = self._extract_ml_weak_points(ml_result, profile)
        if not weak_points:
            weak_points = [item["knowledge_point"] for item in self.diagnosis_agent.run(profile)]
        profile["weak_points"] = weak_points

        self._save_profile_and_weaknesses(db, user_id, requirement, profile, weak_points)

        resource_items = self._extract_ml_resources(ml_result)
        if resource_items:
            resources = self.save_resource_items(db, user_id, course_id, resource_items)
        else:
            reference_titles = self.retrieve_course_resources(db, course_id, weak_points)
            resources = self.generate_resources(
                db,
                user_id,
                course_id,
                profile.get("course") or "课程学习",
                weak_points,
                ["lecture", "mind_map", "exercise", "reading", "code_example", "video_script"],
                reference_titles,
            )

        path_payload = self._extract_ml_path(ml_result)
        if path_payload:
            path, nodes = self._save_path_payload(
                db,
                user_id,
                course_id,
                path_payload,
                profile.get("goal") or "提升课程掌握度",
                [item.id for item in resources],
                weak_points,
            )
        else:
            path, nodes = self.plan_path(
                db,
                user_id,
                course_id,
                profile.get("goal") or "提升课程掌握度",
                weak_points,
                [item.id for item in resources],
            )

        return profile, resources, path, nodes

    def _start_learning_with_local_agents(
        self,
        db: Session,
        user_id: int,
        course_id: int | None,
        requirement: str,
    ) -> tuple[dict, list[LearningResource], LearningPath, list[LearningPathNode]]:
        _, profile = self.analyze_profile(db, user_id, requirement)
        topic = profile.get("course") or "课程学习"
        weak_points = profile.get("weak_points", [])
        reference_titles = self.retrieve_course_resources(db, course_id, weak_points)
        resources = self.generate_resources(
            db,
            user_id,
            course_id,
            topic,
            weak_points,
            ["lecture", "mind_map", "exercise", "reading", "code_example", "video_script"],
            reference_titles,
        )
        path, nodes = self.plan_path(
            db,
            user_id,
            course_id,
            profile.get("goal") or "提升课程掌握度",
            weak_points,
            [item.id for item in resources],
        )
        return profile, resources, path, nodes

    def _save_profile_and_weaknesses(
        self,
        db: Session,
        user_id: int,
        raw_text: str,
        profile: dict,
        weak_points: list[str],
    ) -> StudentProfile:
        try:
            db_profile = (
                db.query(StudentProfile)
                .filter(StudentProfile.user_id == user_id)
                .order_by(StudentProfile.id.desc())
                .first()
            )
            if db_profile is None:
                db_profile = StudentProfile(user_id=user_id, raw_text=raw_text)

            db_profile.major = profile.get("major")
            db_profile.grade = profile.get("grade")
            db_profile.course = profile.get("course")
            db_profile.goal = profile.get("goal")
            db_profile.preference = profile.get("preference")
            db_profile.cognitive_style = profile.get("cognitive_style")
            db_profile.knowledge_level = profile.get("knowledge_level")
            db_profile.raw_text = raw_text
            db.add(db_profile)
            db.flush()

            db.query(StudentWeakness).filter(StudentWeakness.profile_id == db_profile.id).delete(
                synchronize_session=False
            )
            for index, point in enumerate(weak_points):
                db.add(
                    StudentWeakness(
                        user_id=user_id,
                        profile_id=db_profile.id,
                        knowledge_point=str(point),
                        weakness_level=max(0.45, 0.85 - index * 0.08),
                        evidence="LearnPilot-AI recommendation" if weak_points else "Local diagnosis",
                    )
                )

            db.flush()
            db.commit()
            db.refresh(db_profile)
            return db_profile
        except Exception:
            db.rollback()
            raise

    def _extract_ml_profile(self, data: dict[str, Any]) -> dict | None:
        profile = (
            data.get("profile")
            or data.get("student_profile")
            or data.get("learner_profile")
            or data.get("result", {}).get("profile")
            or data.get("data", {}).get("profile")
        )
        if not isinstance(profile, dict):
            return None
        return {
            "major": profile.get("major"),
            "grade": profile.get("grade"),
            "course": profile.get("course") or profile.get("subject"),
            "goal": profile.get("goal") or profile.get("learning_goal"),
            "weak_points": profile.get("weak_points") or profile.get("weaknesses") or profile.get("knowledge_gaps") or [],
            "preference": profile.get("preference") or profile.get("learning_preference"),
            "cognitive_style": profile.get("cognitive_style"),
            "knowledge_level": profile.get("knowledge_level") or profile.get("level"),
        }

    def _extract_ml_weak_points(self, data: dict[str, Any], profile: dict) -> list[str]:
        raw_items = (
            profile.get("weak_points")
            or data.get("weak_points")
            or data.get("weaknesses")
            or data.get("knowledge_gaps")
            or data.get("diagnosis", {}).get("weak_points")
            or data.get("diagnosis", {}).get("weaknesses")
            or []
        )
        if isinstance(raw_items, dict):
            raw_items = list(raw_items.values())

        weak_points = []
        for item in raw_items:
            if isinstance(item, str):
                weak_points.append(item)
            elif isinstance(item, dict):
                point = item.get("knowledge_point") or item.get("point") or item.get("name") or item.get("topic")
                if point:
                    weak_points.append(str(point))
        return weak_points

    def _extract_ml_resources(self, data: dict[str, Any]) -> list[dict]:
        raw_items = (
            data.get("resources")
            or data.get("generated_cards")
            or data.get("cards")
            or data.get("learning_resources")
            or data.get("recommendations")
            or data.get("result", {}).get("resources")
            or data.get("result", {}).get("generated_cards")
            or data.get("result", {}).get("recommendations")
            or data.get("data", {}).get("resources")
            or data.get("data", {}).get("generated_cards")
            or data.get("data", {}).get("recommendations")
            or []
        )
        if isinstance(raw_items, dict):
            raw_items = list(raw_items.values())

        resources = []
        for index, item in enumerate(raw_items, start=1):
            if isinstance(item, str):
                resources.append(
                    {
                        "title": f"ML 生成资源 {index}",
                        "resource_type": "reading",
                        "content": item,
                    }
                )
            elif isinstance(item, dict):
                content = (
                    item.get("content")
                    or item.get("body")
                    or item.get("text")
                    or item.get("summary")
                    or self._ml_card_to_content(item)
                )
                if not content:
                    continue
                resources.append(
                    {
                        "title": str(item.get("title") or item.get("name") or f"ML 生成资源 {index}"),
                        "resource_type": str(item.get("resource_type") or item.get("type") or "reading"),
                        "content": str(content),
                    }
                )
        return resources

    def _ml_card_to_content(self, item: dict) -> str:
        parts = [
            item.get("explanation"),
            item.get("example"),
            item.get("practice"),
            item.get("answer"),
            item.get("mistake_analysis"),
            item.get("review_tip"),
        ]
        return "\n\n".join(str(part) for part in parts if part)

    def _extract_ml_path(self, data: dict[str, Any]) -> dict | None:
        path_payload = (
            data.get("learning_path")
            or data.get("path")
            or data.get("study_path")
            or data.get("result", {}).get("learning_path")
            or data.get("data", {}).get("learning_path")
        )
        if isinstance(path_payload, list):
            return {"nodes": path_payload}
        if isinstance(path_payload, dict):
            return path_payload
        return None

    def _save_path_payload(
        self,
        db: Session,
        user_id: int,
        course_id: int | None,
        path_payload: dict,
        fallback_goal: str,
        resource_ids: list[int],
        weak_points: list[str],
    ) -> tuple[LearningPath, list[LearningPathNode]]:
        try:
            goal = str(path_payload.get("goal") or fallback_goal)
            title = str(path_payload.get("title") or path_payload.get("name") or f"{goal} 个性化学习路径")
            raw_nodes = path_payload.get("nodes") or path_payload.get("steps") or path_payload.get("items") or []
            if isinstance(raw_nodes, dict):
                raw_nodes = list(raw_nodes.values())

            local_plan = self.planner_agent.run(goal, weak_points, resource_ids)
            normalized_nodes = []
            for index, item in enumerate(raw_nodes, start=1):
                if not isinstance(item, dict):
                    continue
                normalized_nodes.append(
                    {
                        "step_order": int(item.get("step_order") or item.get("order") or index),
                        "title": str(item.get("title") or item.get("name") or f"第 {index} 步"),
                        "objective": str(item.get("objective") or item.get("description") or item.get("task") or goal),
                        "estimated_minutes": int(item.get("estimated_minutes") or item.get("duration_minutes") or 40),
                        "resource_id": item.get("resource_id"),
                    }
                )

            if len(normalized_nodes) < 6:
                used_orders = {node["step_order"] for node in normalized_nodes}
                for node in local_plan["nodes"]:
                    if len(normalized_nodes) >= 6:
                        break
                    if node["step_order"] not in used_orders:
                        normalized_nodes.append(node)

            for index, node in enumerate(normalized_nodes, start=1):
                node["step_order"] = index
                if not node.get("resource_id") and resource_ids:
                    node["resource_id"] = resource_ids[(index - 1) % len(resource_ids)]

            path = LearningPath(user_id=user_id, course_id=course_id, title=title, goal=goal)
            db.add(path)
            db.flush()

            nodes = []
            for node in normalized_nodes:
                db_node = LearningPathNode(
                    path_id=path.id,
                    resource_id=node.get("resource_id"),
                    step_order=node["step_order"],
                    title=node["title"],
                    objective=node["objective"],
                    estimated_minutes=node["estimated_minutes"],
                )
                db.add(db_node)
                nodes.append(db_node)

            db.flush()
            db.commit()
            db.refresh(path)
            for node in nodes:
                db.refresh(node)
            return path, nodes
        except Exception:
            db.rollback()
            raise

    def ask_tutor(self, db: Session, user_id: int, question: str, profile: dict | None, history: list[str]) -> dict:
        try:
            user_message = ChatMessage(user_id=user_id, role="user", content=question, agent_name="TutorAgent")
            db.add(user_message)
            db.flush()

            answer = self.tutor_agent.run(question, profile, history)
            assistant_message = ChatMessage(
                user_id=user_id,
                role="assistant",
                content=answer["answer"],
                agent_name="TutorAgent",
            )
            db.add(assistant_message)
            db.flush()
            db.commit()
            db.refresh(user_message)
            db.refresh(assistant_message)
            return answer
        except Exception:
            db.rollback()
            raise

    def evaluate(
        self,
        db: Session,
        user_id: int,
        path_id: int | None,
        correct_count: int,
        total_count: int,
        completed_resource_count: int,
        study_minutes: int,
    ) -> EvaluationResult:
        try:
            result = self.evaluator_agent.run(correct_count, total_count, completed_resource_count, study_minutes)
            evaluation = EvaluationResult(
                user_id=user_id,
                path_id=path_id,
                mastery_score=result["mastery_score"],
                feedback=result["feedback"],
                profile_update=result["profile_update"],
            )
            db.add(evaluation)
            db.flush()

            if result.get("profile_update"):
                db_profile = (
                    db.query(StudentProfile)
                    .filter(StudentProfile.user_id == user_id)
                    .order_by(StudentProfile.id.desc())
                    .first()
                )
                knowledge_level = result["profile_update"].get("knowledge_level")
                if db_profile is not None and knowledge_level:
                    db_profile.knowledge_level = knowledge_level
                    db.add(db_profile)

            db.commit()
            db.refresh(evaluation)
            return evaluation
        except Exception:
            db.rollback()
            raise


learning_service = LearningService()
