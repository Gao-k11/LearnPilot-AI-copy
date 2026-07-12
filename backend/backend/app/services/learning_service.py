from typing import Any
import json
import re

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
    Course,
    EvaluationResult,
    FeedbackEvent,
    LearningPath,
    LearningPathNode,
    LearningResource,
    Question,
    ResourceChunk,
    StudentAnswer,
    StudentProfile,
    StudentWeakness,
)


class LearningService:
    REQUIRED_RESOURCE_TYPES = (
        "lecture",
        "exercise",
        "mind_map",
        "reading",
        "code_example",
        "video_script",
    )

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
        self.last_ml_result: dict[str, Any] | None = None

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
        self.last_ml_result = ml_result
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
            resource_items = self._ensure_resource_type_coverage(
                resource_items,
                profile.get("course") or "课程学习",
                weak_points,
            )
            resources = self.save_resource_items(db, user_id, course_id, resource_items)
        else:
            reference_titles = self.retrieve_course_resources(db, course_id, weak_points)
            resources = self.generate_resources(
                db,
                user_id,
                course_id,
                profile.get("course") or "课程学习",
                weak_points,
                list(self.REQUIRED_RESOURCE_TYPES),
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
            list(self.REQUIRED_RESOURCE_TYPES),
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
            db_profile.mastery = profile.get("mastery") if isinstance(profile.get("mastery"), dict) else None
            db_profile.weak_points_json = weak_points
            db_profile.engagement_score = profile.get("engagement_score")
            db_profile.forgetting_risk = profile.get("forgetting_risk")
            db_profile.learning_stage = profile.get("learning_stage")
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
            "mastery": profile.get("mastery") if isinstance(profile.get("mastery"), dict) else {},
            "engagement_score": profile.get("engagement_score"),
            "forgetting_risk": profile.get("forgetting_risk"),
            "learning_stage": profile.get("learning_stage"),
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
        raw_items = []
        containers = [
            data,
            data.get("result") if isinstance(data.get("result"), dict) else {},
            data.get("data") if isinstance(data.get("data"), dict) else {},
        ]
        for container in containers:
            for key in ("resources", "generated_cards", "cards", "learning_resources", "recommendations"):
                value = container.get(key)
                if isinstance(value, dict):
                    raw_items.extend(value.values())
                elif isinstance(value, list):
                    raw_items.extend(value)

        resources = []
        seen = set()
        for index, item in enumerate(raw_items, start=1):
            if isinstance(item, str):
                resource = {
                    "title": f"ML 生成资源 {index}",
                    "resource_type": "reading",
                    "content": item,
                }
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
                resource = {
                    "title": str(item.get("title") or item.get("name") or f"ML 生成资源 {index}"),
                    "resource_type": str(item.get("resource_type") or item.get("type") or "reading"),
                    "content": str(content),
                }
            else:
                continue

            identity = (resource["title"], resource["resource_type"], resource["content"])
            if identity not in seen:
                seen.add(identity)
                resources.append(resource)
        return resources

    def _ensure_resource_type_coverage(
        self,
        ml_resources: list[dict],
        topic: str,
        weak_points: list[str],
    ) -> list[dict]:
        resources = list(ml_resources)
        existing_types = {
            str(item.get("resource_type") or "").strip().lower()
            for item in resources
            if isinstance(item, dict)
        }
        missing_types = [
            resource_type
            for resource_type in self.REQUIRED_RESOURCE_TYPES
            if resource_type not in existing_types
        ]
        if not missing_types:
            return resources

        generated = self.resource_agent.run(topic, weak_points, missing_types)
        resources.extend(generated)
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

            evidence = self._retrieve_tutor_evidence(db, question, limit=5)
            trimmed_history = list(history or [])[-10:]
            answer = self.tutor_agent.run(question, profile, trimmed_history, evidence)
            if evidence:
                answer["evidence"] = evidence
            else:
                answer.setdefault("evidence", [])
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
            latest_path = db.get(LearningPath, path_id) if path_id else None
            course_id = latest_path.course_id if latest_path else None
            knowledge_points = self._knowledge_points_from_path(db, path_id)
            score = correct_count / total_count
            feedback_event = FeedbackEvent(
                user_id=user_id,
                course_id=course_id,
                path_id=path_id,
                knowledge_points=knowledge_points,
                score=score,
                completed=completed_resource_count > 0,
                dwell_seconds=study_minutes * 60,
                liked=True if score >= 0.75 else False if score < 0.45 else None,
                event_metadata={
                    "correct_count": correct_count,
                    "total_count": total_count,
                    "completed_resource_count": completed_resource_count,
                },
            )
            db.add(feedback_event)
            db.flush()

            result = self.evaluator_agent.run(correct_count, total_count, completed_resource_count, study_minutes)
            ml_feedback = self.ml_adapter.feedback_learning(db, user_id, course_id, [feedback_event])
            if isinstance(ml_feedback, dict):
                after = ml_feedback.get("after", {})
                profile = after.get("profile", {}) if isinstance(after, dict) else {}
                if isinstance(profile, dict):
                    result["profile_update"] = {
                        **result.get("profile_update", {}),
                        "mastery": profile.get("mastery", {}),
                        "weak_points": profile.get("weak_points", []),
                        "learning_stage": profile.get("learning_stage"),
                        "engagement_score": profile.get("engagement_score"),
                        "forgetting_risk": profile.get("forgetting_risk"),
                        "path_adjustment": ml_feedback.get("path_adjustment"),
                    }
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
                if db_profile is not None:
                    if knowledge_level:
                        db_profile.knowledge_level = knowledge_level
                    if isinstance(result["profile_update"].get("mastery"), dict):
                        db_profile.mastery = result["profile_update"]["mastery"]
                    if isinstance(result["profile_update"].get("weak_points"), list):
                        db_profile.weak_points_json = result["profile_update"]["weak_points"]
                    db_profile.learning_stage = result["profile_update"].get("learning_stage") or db_profile.learning_stage
                    db_profile.engagement_score = result["profile_update"].get("engagement_score") or db_profile.engagement_score
                    db_profile.forgetting_risk = result["profile_update"].get("forgetting_risk") or db_profile.forgetting_risk
                    db.add(db_profile)

            db.commit()
            db.refresh(evaluation)
            return evaluation
        except Exception:
            db.rollback()
            raise

    def _retrieve_tutor_evidence(self, db: Session, question: str, limit: int = 5) -> list[dict]:
        tokens = [token for token in question.replace("？", " ").replace("?", " ").split() if token]
        query = db.query(ResourceChunk)
        chunks = query.limit(80).all()
        scored = []
        for chunk in chunks:
            score = sum(1 for token in tokens if token.lower() in chunk.content.lower())
            if score or any(char in chunk.content for char in question[:12]):
                scored.append((score, chunk))
        scored.sort(key=lambda item: item[0], reverse=True)
        evidence = []
        for _, chunk in scored[:limit]:
            resource = db.get(LearningResource, chunk.resource_id)
            evidence.append(
                {
                    "chunk_id": chunk.id,
                    "resource_id": chunk.resource_id,
                    "title": resource.title if resource else f"资源 #{chunk.resource_id}",
                    "source": f"resource:{chunk.resource_id}" if chunk.resource_id else f"chunk:{chunk.id}",
                    "snippet": chunk.content[:240],
                }
            )
        return evidence

    def _knowledge_points_from_path(self, db: Session, path_id: int | None) -> list[str]:
        if path_id is None:
            return []
        nodes = db.query(LearningPathNode).filter(LearningPathNode.path_id == path_id).all()
        points = []
        for node in nodes:
            title = node.title or node.objective
            if title:
                points.append(title.split()[0])
        return points[:5]

    def _resolve_owned_path(self, db: Session, path_id: int, user_id: int) -> LearningPath:
        path = db.get(LearningPath, path_id)
        if path is None or path.status == "deleted" or path.user_id != user_id:
            raise ValueError("Learning path not found")
        return path

    def _question_meta(self, question: Question) -> dict:
        knowledge_point = ""
        options: list[dict] = []
        explain_text = question.explanation or ""
        raw = (question.explanation or "").strip()
        if raw.startswith("{"):
            try:
                payload = json.loads(raw)
                if isinstance(payload, dict):
                    options = payload.get("options") or []
                    knowledge_point = str(payload.get("knowledge_point") or "")
                    explain_text = str(payload.get("explain_text") or explain_text)
            except json.JSONDecodeError:
                pass
        if not options:
            qtype = (question.question_type or "").lower()
            if qtype in {"true_false", "judgment", "判断"}:
                options = [
                    {"value": "true", "text": "正确"},
                    {"value": "false", "text": "错误"},
                ]
            else:
                options = [
                    {"value": "A", "text": "选项 A"},
                    {"value": "B", "text": "选项 B"},
                    {"value": "C", "text": "选项 C"},
                    {"value": "D", "text": "选项 D"},
                ]
        return {
            "options": options,
            "knowledge_point": knowledge_point,
            "explain_text": explain_text,
        }

    def _public_question(self, question: Question) -> dict:
        meta = self._question_meta(question)
        qtype = (question.question_type or "single_choice").lower()
        if qtype in {"judgment", "判断"}:
            qtype = "true_false"
        return {
            "id": question.id,
            "type": qtype,
            "stem": question.stem,
            "options": meta["options"],
            "knowledge_point": meta["knowledge_point"] or None,
            "difficulty": float(question.difficulty or 0.5),
        }

    def _normalize_answer(self, value: str) -> str:
        text = str(value or "").strip().lower()
        mapping = {
            "对": "true",
            "错": "false",
            "正确": "true",
            "错误": "false",
            "yes": "true",
            "no": "false",
            "t": "true",
            "f": "false",
        }
        return mapping.get(text, text)

    def _grade_question(self, question: Question, user_answer: str) -> bool:
        expected = self._normalize_answer(question.answer or "")
        actual = self._normalize_answer(user_answer)
        qtype = (question.question_type or "").lower()
        if qtype in {"true_false", "judgment", "判断"}:
            return actual == expected
        if qtype in {"single_choice", "single", "choice"}:
            return actual[:1] == expected[:1]
        if not expected:
            return False
        keywords = [part.strip().lower() for part in re.split(r"[,，;；\s]+", expected) if part.strip()]
        if not keywords:
            return actual == expected
        return any(keyword in actual for keyword in keywords)

    def _evaluation_topics(
        self,
        db: Session,
        user_id: int,
        path_id: int | None,
        course_id: int | None,
    ) -> tuple[int | None, list[str]]:
        topics: list[str] = []
        resolved_course_id = course_id
        if path_id is not None:
            path = self._resolve_owned_path(db, path_id, user_id)
            resolved_course_id = resolved_course_id or path.course_id
            nodes = (
                db.query(LearningPathNode)
                .filter(LearningPathNode.path_id == path.id)
                .order_by(LearningPathNode.step_order.asc())
                .all()
            )
            for node in nodes:
                if node.title:
                    topics.append(node.title)
                if node.objective:
                    topics.append(node.objective[:48])

        profile = (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id == user_id)
            .order_by(StudentProfile.id.desc())
            .first()
        )
        if profile:
            if profile.course:
                topics.append(profile.course)
            if profile.weak_points_json:
                topics.extend(str(item) for item in profile.weak_points_json if item)
            if profile.goal:
                topics.append(profile.goal[:48])

        if resolved_course_id:
            course = db.get(Course, resolved_course_id)
            if course and course.name:
                topics.append(course.name)
        else:
            first_course = db.query(Course).order_by(Course.id.asc()).first()
            if first_course:
                resolved_course_id = first_course.id
                topics.append(first_course.name)

        deduped: list[str] = []
        for topic in topics:
            cleaned = str(topic).strip()
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)
        if not deduped:
            deduped = ["课程核心概念"]
        return resolved_course_id, deduped

    def _build_generated_question(
        self,
        course_id: int,
        topic: str,
        variant_index: int,
    ) -> Question:
        templates = [
            {
                "type": "single_choice",
                "stem": f"关于「{topic}」，哪一项描述最准确？",
                "options": [
                    {"value": "A", "text": f"先明确{topic}的定义、输入输出和适用场景"},
                    {"value": "B", "text": "只记忆结论，不做例题和复盘"},
                    {"value": "C", "text": "跳过基础概念，直接做综合题"},
                    {"value": "D", "text": "只复制代码，不解释原理"},
                ],
                "answer": "A",
                "explain_text": f"学习{topic}时应先建立概念框架，再结合练习验证理解。",
            },
            {
                "type": "single_choice",
                "stem": f"以下哪种方式最能检验你对「{topic}」的掌握程度？",
                "options": [
                    {"value": "A", "text": "只看参考答案"},
                    {"value": "B", "text": "用自己的话解释并完成一题变式练习"},
                    {"value": "C", "text": "重复阅读标题"},
                    {"value": "D", "text": "忽略错题"},
                ],
                "answer": "B",
                "explain_text": "能解释并迁移到变式题，说明对知识点形成了可应用的理解。",
            },
            {
                "type": "true_false",
                "stem": f"学习「{topic}」时，只记住名词定义就足够应对考试。",
                "options": [
                    {"value": "true", "text": "正确"},
                    {"value": "false", "text": "错误"},
                ],
                "answer": "false",
                "explain_text": f"{topic}需要结合原理、例题和易错点复盘，单靠死记定义通常不够。",
            },
            {
                "type": "single_choice",
                "stem": f"遇到「{topic}」相关错题时，优先应该做什么？",
                "options": [
                    {"value": "A", "text": "归类错因并回到对应知识点复习"},
                    {"value": "B", "text": "直接跳到下一章"},
                    {"value": "C", "text": "删除错题记录"},
                    {"value": "D", "text": "只记最终答案"},
                ],
                "answer": "A",
                "explain_text": "错题复盘应回到知识点和错因，才能避免重复犯错。",
            },
            {
                "type": "true_false",
                "stem": f"在{topic}学习中，结合一个最小可运行案例有助于理解关键流程。",
                "options": [
                    {"value": "true", "text": "正确"},
                    {"value": "false", "text": "错误"},
                ],
                "answer": "true",
                "explain_text": "最小案例能把抽象概念转化为可观察的输入、过程和输出。",
            },
        ]
        template = templates[variant_index % len(templates)]
        meta = {
            "options": template["options"],
            "knowledge_point": topic,
            "explain_text": template["explain_text"],
        }
        return Question(
            course_id=course_id,
            question_type=template["type"],
            stem=template["stem"],
            answer=template["answer"],
            explanation=json.dumps(meta, ensure_ascii=False),
            difficulty=0.5,
            source=f"generated:evaluation:{topic}:{variant_index}",
        )

    def _ensure_questions(
        self,
        db: Session,
        course_id: int,
        topics: list[str],
        limit: int,
    ) -> list[Question]:
        selected = (
            db.query(Question)
            .filter(Question.course_id == course_id)
            .order_by(Question.id.desc())
            .limit(limit * 3)
            .all()
        )
        picked: list[Question] = []
        seen_stems: set[str] = set()
        for question in selected:
            if len(picked) >= limit:
                break
            if question.stem in seen_stems:
                continue
            seen_stems.add(question.stem)
            picked.append(question)

        variant = 0
        topic_index = 0
        while len(picked) < limit:
            topic = topics[topic_index % len(topics)]
            generated = self._build_generated_question(course_id, topic, variant)
            db.add(generated)
            db.flush()
            picked.append(generated)
            variant += 1
            topic_index += 1
        db.commit()
        for question in picked:
            db.refresh(question)
        return picked[:limit]

    def start_evaluation(
        self,
        db: Session,
        user_id: int,
        path_id: int | None,
        course_id: int | None,
        limit: int,
    ) -> dict:
        if path_id is not None:
            self._resolve_owned_path(db, path_id, user_id)
        resolved_course_id, topics = self._evaluation_topics(db, user_id, path_id, course_id)
        if resolved_course_id is None:
            raise ValueError("Course not found for evaluation")
        questions = self._ensure_questions(db, resolved_course_id, topics, limit)
        return {
            "path_id": path_id,
            "course_id": resolved_course_id,
            "total": len(questions),
            "questions": [self._public_question(question) for question in questions],
        }

    def submit_evaluation_answers(
        self,
        db: Session,
        user_id: int,
        path_id: int | None,
        course_id: int | None,
        study_minutes: int,
        answers: list[dict],
    ) -> dict:
        if not answers:
            raise ValueError("answers must not be empty")
        if path_id is not None:
            path = self._resolve_owned_path(db, path_id, user_id)
            course_id = course_id or path.course_id

        wrong_items: list[dict] = []
        correct_count = 0
        total_count = len(answers)

        for item in answers:
            question = db.get(Question, int(item["question_id"]))
            if question is None:
                raise ValueError(f"Question {item['question_id']} not found")
            user_answer = str(item.get("answer") or "")
            elapsed_seconds = int(item.get("elapsed_seconds") or 0)
            is_correct = self._grade_question(question, user_answer)
            if is_correct:
                correct_count += 1
            meta = self._question_meta(question)
            if not is_correct:
                wrong_items.append(
                    {
                        "question_id": question.id,
                        "stem": question.stem,
                        "user_answer": user_answer,
                        "correct_answer": str(question.answer or ""),
                        "explanation": meta["explain_text"] or question.explanation or "",
                        "knowledge_point": meta["knowledge_point"] or None,
                    }
                )
            db.add(
                StudentAnswer(
                    user_id=user_id,
                    course_id=course_id or question.course_id,
                    question_id=question.id,
                    knowledge_point=meta["knowledge_point"] or None,
                    answer=user_answer,
                    score=1.0 if is_correct else 0.0,
                    correct=is_correct,
                    elapsed_seconds=elapsed_seconds,
                )
            )
        db.flush()

        evaluation = self.evaluate(
            db,
            user_id,
            path_id,
            correct_count,
            total_count,
            0,
            study_minutes,
        )

        accuracy = correct_count / total_count if total_count else 0.0
        score = round(accuracy * 100, 1)
        weak_points = list(
            dict.fromkeys(
                item["knowledge_point"]
                for item in wrong_items
                if item.get("knowledge_point")
            )
        )

        profile_update = dict(evaluation.profile_update or {})
        profile_update.update(
            {
                "wrong_items": wrong_items,
                "weak_points": weak_points or profile_update.get("weak_points", []),
                "accuracy": round(accuracy, 4),
                "score": score,
                "correct_count": correct_count,
                "total_count": total_count,
            }
        )
        evaluation.profile_update = profile_update
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)

        path_adjustment = profile_update.get("path_adjustment")
        updated_profile = profile_update if profile_update.get("mastery") else None
        return {
            "evaluation_id": evaluation.id,
            "score": score,
            "accuracy": round(accuracy, 4),
            "correct_count": correct_count,
            "total_count": total_count,
            "mastery_score": evaluation.mastery_score,
            "feedback": evaluation.feedback,
            "wrong_items": wrong_items,
            "weak_points": weak_points,
            "path_adjustment": path_adjustment,
            "updated_profile": updated_profile,
            "profile_update": profile_update,
        }

    def submit_evaluation_summary(
        self,
        db: Session,
        user_id: int,
        path_id: int | None,
        correct_count: int,
        total_count: int,
        completed_resource_count: int,
        study_minutes: int,
    ) -> dict:
        evaluation = self.evaluate(
            db,
            user_id,
            path_id,
            correct_count,
            total_count,
            completed_resource_count,
            study_minutes,
        )
        accuracy = correct_count / total_count if total_count else 0.0
        score = round(accuracy * 100, 1)
        profile_update = dict(evaluation.profile_update or {})
        profile_update.update(
            {
                "accuracy": round(accuracy, 4),
                "score": score,
                "correct_count": correct_count,
                "total_count": total_count,
            }
        )
        evaluation.profile_update = profile_update
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)
        path_adjustment = profile_update.get("path_adjustment")
        updated_profile = profile_update if profile_update.get("mastery") else None
        return {
            "evaluation_id": evaluation.id,
            "score": score,
            "accuracy": round(accuracy, 4),
            "correct_count": correct_count,
            "total_count": total_count,
            "mastery_score": evaluation.mastery_score,
            "feedback": evaluation.feedback,
            "wrong_items": [],
            "weak_points": list(profile_update.get("weak_points") or []),
            "path_adjustment": path_adjustment,
            "updated_profile": updated_profile,
            "profile_update": profile_update,
        }

    def list_evaluations(self, db: Session, user_id: int, limit: int = 20) -> list[dict]:
        rows = (
            db.query(EvaluationResult)
            .filter(EvaluationResult.user_id == user_id)
            .order_by(EvaluationResult.created_at.desc())
            .limit(limit)
            .all()
        )
        items = []
        for row in rows:
            payload = row.profile_update or {}
            items.append(
                {
                    "evaluation_id": row.id,
                    "path_id": row.path_id,
                    "score": payload.get("score"),
                    "accuracy": payload.get("accuracy"),
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "feedback": row.feedback,
                }
            )
        return items

    def get_evaluation_detail(self, db: Session, user_id: int, evaluation_id: int) -> dict:
        row = db.get(EvaluationResult, evaluation_id)
        if row is None or row.user_id != user_id:
            raise ValueError("Evaluation not found")
        payload = row.profile_update or {}
        return {
            "evaluation_id": row.id,
            "path_id": row.path_id,
            "score": payload.get("score"),
            "accuracy": payload.get("accuracy"),
            "correct_count": payload.get("correct_count"),
            "total_count": payload.get("total_count"),
            "mastery_score": row.mastery_score,
            "feedback": row.feedback,
            "wrong_items": payload.get("wrong_items") or [],
            "weak_points": payload.get("weak_points") or [],
            "path_adjustment": payload.get("path_adjustment"),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "profile_update": payload,
        }


learning_service = LearningService()
