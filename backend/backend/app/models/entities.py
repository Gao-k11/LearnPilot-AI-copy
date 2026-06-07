from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(32), default="student", nullable=False)


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


class LearningPathNode(TimestampMixin, Base):
    __tablename__ = "learning_path_node"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    path_id: Mapped[int] = mapped_column(ForeignKey("learning_path.id"), nullable=False)
    resource_id: Mapped[int | None] = mapped_column(ForeignKey("learning_resource.id"))
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)


class EvaluationResult(TimestampMixin, Base):
    __tablename__ = "evaluation_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    path_id: Mapped[int | None] = mapped_column(ForeignKey("learning_path.id"))
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    profile_update: Mapped[dict | None] = mapped_column(JSON)


class ChatMessage(TimestampMixin, Base):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[str | None] = mapped_column(String(64))
