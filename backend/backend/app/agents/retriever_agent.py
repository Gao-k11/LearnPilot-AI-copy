from sqlalchemy.orm import Session

from backend.app.models import CourseResource


class RetrieverAgent:
    name = "RetrieverAgent"

    def run(self, db: Session, course_id: int | None, weak_points: list[str]) -> list[CourseResource]:
        query = db.query(CourseResource)
        if course_id:
            query = query.filter(CourseResource.course_id == course_id)
        resources = query.limit(20).all()
        if not weak_points:
            return resources
        matched = [
            item
            for item in resources
            if any(point.lower() in f"{item.title} {item.content}".lower() for point in weak_points)
        ]
        return matched or resources
