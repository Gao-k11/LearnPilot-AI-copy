from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from backend.app.models import (
    EvaluationResult,
    LearningPath,
    PathFeedback,
    ProducerTask,
    ResourceCenter,
    StudentProfile,
    User,
)

PRODUCER_STATUSES = ("pending", "running", "completed", "failed")
EVALUATION_BUCKETS = ("0-59", "60-79", "80-89", "90-100")


def _round1(value: float) -> float:
    return round(float(value), 1)


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _percent(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return _round1(numerator / denominator * 100)


def _normalize_day(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    return text[:10]


def _active_users_query(query):
    return query.filter(func.coalesce(User.status, "active") != "deleted")


def _admin_users_query(query):
    return query.filter(
        or_(
            User.is_admin.is_(True),
            func.lower(User.role) == "admin",
            User.username == "admin",
        )
    )


def _utc_day_window() -> tuple[datetime, datetime, list[str], list[str]]:
    now = datetime.utcnow()
    today_start = datetime.combine(now.date(), time.min)
    seven_day_start = today_start - timedelta(days=6)
    day_starts = [today_start - timedelta(days=offset) for offset in range(6, -1, -1)]
    day_keys = [day.date().isoformat() for day in day_starts]
    display_dates = [day.strftime("%m-%d") for day in day_starts]
    return today_start, seven_day_start, day_keys, display_dates


def _daily_counts(
    db: Session,
    model,
    seven_day_start: datetime,
    day_keys: list[str],
    query_filter=None,
) -> list[int]:
    query = (
        db.query(func.date(model.created_at).label("day"), func.count().label("cnt"))
        .filter(model.created_at >= seven_day_start)
    )
    if query_filter is not None:
        query = query_filter(query)
    rows = query.group_by(func.date(model.created_at)).all()
    count_map = {_normalize_day(row.day): _safe_int(row.cnt) for row in rows}
    return [count_map.get(day_key, 0) for day_key in day_keys]


def _build_overview(db: Session, today_start: datetime, seven_day_start: datetime) -> dict[str, Any]:
    user_count = _safe_int(_active_users_query(db.query(User)).count())
    active_user_count = user_count
    admin_user_count = _safe_int(
        _active_users_query(_admin_users_query(db.query(User))).count()
    )
    today_user_count = _safe_int(
        _active_users_query(db.query(User))
        .filter(User.created_at >= today_start)
        .count()
    )
    last7_days_user_count = _safe_int(
        _active_users_query(db.query(User))
        .filter(User.created_at >= seven_day_start)
        .count()
    )
    profile_user_count = _safe_int(
        db.query(func.count(func.distinct(StudentProfile.user_id))).scalar()
    )
    profile_coverage_rate = _percent(profile_user_count, user_count)

    path_count = _safe_int(db.query(LearningPath).count())
    active_path_count = _safe_int(
        db.query(LearningPath).filter(func.lower(LearningPath.status) == "active").count()
    )
    completed_path_count = _safe_int(
        db.query(LearningPath).filter(func.lower(LearningPath.status) == "completed").count()
    )
    average_path_progress = _round1(
        db.query(func.avg(func.coalesce(LearningPath.progress, 0))).scalar() or 0
    )
    last7_days_path_count = _safe_int(
        db.query(LearningPath).filter(LearningPath.created_at >= seven_day_start).count()
    )

    evaluation_count = _safe_int(db.query(EvaluationResult).count())
    average_evaluation_score = _round1(
        (db.query(func.avg(EvaluationResult.mastery_score)).scalar() or 0) * 100
    )
    last7_days_evaluation_count = _safe_int(
        db.query(EvaluationResult)
        .filter(EvaluationResult.created_at >= seven_day_start)
        .count()
    )

    producer_task_count = _safe_int(db.query(ProducerTask).count())
    producer_completed_count = _safe_int(
        db.query(ProducerTask).filter(func.lower(ProducerTask.status) == "completed").count()
    )
    producer_failed_count = _safe_int(
        db.query(ProducerTask).filter(func.lower(ProducerTask.status) == "failed").count()
    )
    producer_running_count = _safe_int(
        db.query(ProducerTask).filter(func.lower(ProducerTask.status) == "running").count()
    )
    producer_pending_count = _safe_int(
        db.query(ProducerTask).filter(func.lower(ProducerTask.status) == "pending").count()
    )
    producer_success_rate = _percent(producer_completed_count, producer_task_count)
    last7_days_producer_task_count = _safe_int(
        db.query(ProducerTask).filter(ProducerTask.created_at >= seven_day_start).count()
    )

    resource_count = _safe_int(db.query(ResourceCenter).count())
    published_resource_count = _safe_int(
        db.query(ResourceCenter).filter(func.lower(ResourceCenter.status) == "published").count()
    )
    unpublished_resource_count = max(0, resource_count - published_resource_count)
    last7_days_resource_count = _safe_int(
        db.query(ResourceCenter).filter(ResourceCenter.created_at >= seven_day_start).count()
    )

    path_feedback_count = _safe_int(db.query(PathFeedback).count())
    average_path_feedback_rating = _round1(
        db.query(func.avg(PathFeedback.rating)).scalar() or 0
    )

    return {
        "userCount": user_count,
        "activeUserCount": active_user_count,
        "adminUserCount": admin_user_count,
        "todayUserCount": today_user_count,
        "last7DaysUserCount": last7_days_user_count,
        "profileUserCount": profile_user_count,
        "profileCoverageRate": profile_coverage_rate,
        "pathCount": path_count,
        "activePathCount": active_path_count,
        "completedPathCount": completed_path_count,
        "averagePathProgress": average_path_progress,
        "last7DaysPathCount": last7_days_path_count,
        "evaluationCount": evaluation_count,
        "averageEvaluationScore": average_evaluation_score,
        "last7DaysEvaluationCount": last7_days_evaluation_count,
        "producerTaskCount": producer_task_count,
        "producerCompletedCount": producer_completed_count,
        "producerFailedCount": producer_failed_count,
        "producerRunningCount": producer_running_count,
        "producerPendingCount": producer_pending_count,
        "producerSuccessRate": producer_success_rate,
        "last7DaysProducerTaskCount": last7_days_producer_task_count,
        "resourceCount": resource_count,
        "publishedResourceCount": published_resource_count,
        "unpublishedResourceCount": unpublished_resource_count,
        "last7DaysResourceCount": last7_days_resource_count,
        "pathFeedbackCount": path_feedback_count,
        "averagePathFeedbackRating": average_path_feedback_rating,
    }


def _build_trends(db: Session, seven_day_start: datetime, day_keys: list[str], display_dates: list[str]) -> dict[str, Any]:
    return {
        "dates": display_dates,
        "newUsers": _daily_counts(
            db,
            User,
            seven_day_start,
            day_keys,
            query_filter=_active_users_query,
        ),
        "newPaths": _daily_counts(db, LearningPath, seven_day_start, day_keys),
        "newEvaluations": _daily_counts(db, EvaluationResult, seven_day_start, day_keys),
        "newProducerTasks": _daily_counts(db, ProducerTask, seven_day_start, day_keys),
    }


def _build_producer_status_distribution(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.query(func.lower(ProducerTask.status).label("status"), func.count().label("cnt"))
        .group_by(func.lower(ProducerTask.status))
        .all()
    )
    count_map: dict[str, int] = {}
    for row in rows:
        status_key = str(row.status or "").strip().lower()
        if not status_key:
            continue
        count_map[status_key] = count_map.get(status_key, 0) + _safe_int(row.cnt)
    return [{"name": name, "value": count_map.get(name, 0)} for name in PRODUCER_STATUSES]


def _build_evaluation_score_distribution(db: Session) -> list[dict[str, Any]]:
    score_pct = EvaluationResult.mastery_score * 100
    bucket_expr = case(
        (score_pct < 60, "0-59"),
        (score_pct < 80, "60-79"),
        (score_pct < 90, "80-89"),
        else_="90-100",
    )
    rows = (
        db.query(bucket_expr.label("bucket"), func.count().label("cnt"))
        .group_by(bucket_expr)
        .all()
    )
    count_map = {str(row.bucket): _safe_int(row.cnt) for row in rows}
    return [{"name": name, "value": count_map.get(name, 0)} for name in EVALUATION_BUCKETS]


def _build_resource_type_distribution(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.query(ResourceCenter.resource_type, func.count().label("cnt"))
        .group_by(ResourceCenter.resource_type)
        .all()
    )
    result: list[dict[str, Any]] = []
    for row in rows:
        name = (row.resource_type or "").strip() or "其他"
        result.append({"name": name, "value": _safe_int(row.cnt)})
    result.sort(key=lambda item: (-item["value"], item["name"]))
    return result


def _build_distributions(db: Session) -> dict[str, Any]:
    return {
        "producerStatus": _build_producer_status_distribution(db),
        "evaluationScoreBuckets": _build_evaluation_score_distribution(db),
        "resourceType": _build_resource_type_distribution(db),
    }


def build_admin_statistics(db: Session) -> dict[str, Any]:
    today_start, seven_day_start, day_keys, display_dates = _utc_day_window()
    overview = _build_overview(db, today_start, seven_day_start)
    trends = _build_trends(db, seven_day_start, day_keys, display_dates)
    distributions = _build_distributions(db)
    return {
        "overview": overview,
        "trends": trends,
        "distributions": distributions,
        "userCount": overview["userCount"],
        "resourceCount": overview["resourceCount"],
        "pathCount": overview["pathCount"],
        "feedbackCount": overview["pathFeedbackCount"],
        "producerTaskCount": overview["producerTaskCount"],
        "todayUserCount": overview["todayUserCount"],
    }
