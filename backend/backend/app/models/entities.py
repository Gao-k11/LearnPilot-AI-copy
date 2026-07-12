from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base
from backend.app.core.json_codec import UnicodeJSONType


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(64))
    nickname: Mapped[str | None] = mapped_column(String(100), default="")
    gender: Mapped[str | None] = mapped_column(String(20), default="")
    phone: Mapped[str | None] = mapped_column(String(32), default="")
    avatar: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="student", nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class Course(TimestampMixin, Base):
    __tablename__ = "course"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    knowledge_points: Mapped[list["KnowledgePoint"]] = relationship(back_populates="course")


class KnowledgePoint(TimestampMixin, Base):
    __tablename__ = "knowledge_point"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_point.id"))
    difficulty: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)

    course: Mapped[Course] = relationship(back_populates="knowledge_points")


class CourseResource(TimestampMixin, Base):
    __tablename__ = "course_resource"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    knowledge_point_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_point.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(String(255))
    source_type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(32), default="published")
    version: Mapped[str | None] = mapped_column(String(32), default="v1")
    resource_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)


class ResourceCenter(TimestampMixin, Base):
    __tablename__ = "resource_center"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128))
    content: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(1000))
    cover_url: Mapped[str | None] = mapped_column(String(1000))
    author: Mapped[str | None] = mapped_column(String(128))
    views: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="published", nullable=False)
    open_type: Mapped[str] = mapped_column(String(32), default="content", nullable=False)
    knowledge_point: Mapped[str | None] = mapped_column(String(128))
    tags: Mapped[str | None] = mapped_column(String(255))
    difficulty: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[str | None] = mapped_column(Text)


class StudentProfile(TimestampMixin, Base):
    __tablename__ = "student_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    major: Mapped[str | None] = mapped_column(String(128))
    grade: Mapped[str | None] = mapped_column(String(64))
    course: Mapped[str | None] = mapped_column(String(128))
    goal: Mapped[str | None] = mapped_column(Text)
    preference: Mapped[str | None] = mapped_column(String(128))
    cognitive_style: Mapped[str | None] = mapped_column(String(128))
    knowledge_level: Mapped[str | None] = mapped_column(String(64))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    mastery: Mapped[dict | None] = mapped_column(UnicodeJSONType)
    weak_points_json: Mapped[list | None] = mapped_column(UnicodeJSONType)
    engagement_score: Mapped[float | None] = mapped_column(Float)
    forgetting_risk: Mapped[float | None] = mapped_column(Float)
    learning_stage: Mapped[str | None] = mapped_column(String(64))


class ProfileBuilderSession(TimestampMixin, Base):
    __tablename__ = "profile_builder_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    current_step: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    result_profile_json: Mapped[dict | None] = mapped_column(UnicodeJSONType)


class ProfileBuilderMessage(Base):
    __tablename__ = "profile_builder_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class MLProfileAnswer(Base):
    __tablename__ = "ml_profile_answer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(String(128), nullable=False)
    question: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ProducerTask(TimestampMixin, Base):
    __tablename__ = "producer_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    requirement: Mapped[str | None] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(String(64), default="multi_agent_generation", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)


class ProducerArtifact(TimestampMixin, Base):
    __tablename__ = "producer_artifact"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(512))
    metadata_json: Mapped[dict | None] = mapped_column(JSON)


class ProducerChatMessage(Base):
    __tablename__ = "producer_chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class StudentWeakness(TimestampMixin, Base):
    __tablename__ = "student_weakness"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("student_profile.id"))
    knowledge_point: Mapped[str] = mapped_column(String(128), nullable=False)
    weakness_level: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)


class LearningResource(TimestampMixin, Base):
    __tablename__ = "learning_resource"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("course.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), default="approved", nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text)


class LearningPath(TimestampMixin, Base):
    __tablename__ = "learning_path"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("course.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0, nullable=False)


class LearningPathNode(TimestampMixin, Base):
    __tablename__ = "learning_path_node"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    path_id: Mapped[int] = mapped_column(ForeignKey("learning_path.id"), nullable=False)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("learning_resource.id"))
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    level: Mapped[str | None] = mapped_column(String(64))
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="not_started", nullable=False)


class PathNodeProgress(TimestampMixin, Base):
    __tablename__ = "path_node_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    path_id: Mapped[int] = mapped_column(ForeignKey("learning_path.id"), nullable=False, index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("learning_path_node.id"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="not_started", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class PathFeedback(Base):
    __tablename__ = "path_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    path_id: Mapped[int] = mapped_column(ForeignKey("learning_path.id"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"))
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EvaluationResult(TimestampMixin, Base):
    __tablename__ = "evaluation_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    path_id: Mapped[int | None] = mapped_column(ForeignKey("learning_path.id"))
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    profile_update: Mapped[dict | None] = mapped_column(JSON)


class ImportJob(TimestampMixin, Base):
    __tablename__ = "import_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict | None] = mapped_column(JSON)


class ResourceChunk(TimestampMixin, Base):
    __tablename__ = "resource_chunk"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    resource_id: Mapped[int] = mapped_column(ForeignKey("course_resource.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding: Mapped[list | None] = mapped_column(JSON)
    keywords: Mapped[list | None] = mapped_column(JSON)


class Question(TimestampMixin, Base):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("course.id"), nullable=False)
    knowledge_point_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_point.id"))
    question_type: Mapped[str] = mapped_column(String(32), default="short_answer", nullable=False)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str | None] = mapped_column(Text)
    difficulty: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    source: Mapped[str | None] = mapped_column(String(255))


class StudentAnswer(TimestampMixin, Base):
    __tablename__ = "student_answer"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("course.id"))
    question_id: Mapped[int | None] = mapped_column(ForeignKey("question.id"))
    knowledge_point: Mapped[str | None] = mapped_column(String(128))
    answer: Mapped[str | None] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    correct: Mapped[bool | None] = mapped_column(Boolean)
    elapsed_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class FeedbackEvent(TimestampMixin, Base):
    __tablename__ = "feedback_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("course.id"))
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("learning_resource.id"))
    path_id: Mapped[int | None] = mapped_column(ForeignKey("learning_path.id"))
    knowledge_points: Mapped[list | None] = mapped_column(JSON)
    score: Mapped[float | None] = mapped_column(Float)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dwell_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    liked: Mapped[bool | None] = mapped_column(Boolean)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(64))
