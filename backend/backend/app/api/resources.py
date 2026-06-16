from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models import ResourceCenter


router = APIRouter(prefix="/resources", tags=["resources"])


def _resource_payload(resource: ResourceCenter, include_content: bool = False) -> dict:
    resource_type = (resource.resource_type or "").lower()
    open_type = "content" if resource_type == "document" else "url"
    payload = {
        "id": resource.id,
        "title": resource.title,
        "description": resource.description or "",
        "type": resource_type,
        "resource_type": resource_type,
        "category": resource.category or "",
        "open_type": open_type,
        "detail_url": f"/resources/{resource.id}",
        "url": "" if resource_type == "document" else (resource.url or ""),
        "cover_url": resource.cover_url or "",
        "author": resource.author or "",
        "views": resource.views,
        "likes": resource.likes,
        "knowledge_point": resource.knowledge_point or "",
        "tags": resource.tags or "",
        "difficulty": resource.difficulty or "",
        "summary": resource.summary or "",
        "created_at": resource.created_at.isoformat() if resource.created_at else None,
        "updated_at": resource.updated_at.isoformat() if resource.updated_at else None,
    }
    if include_content:
        payload["content"] = resource.content or ""
    return payload


@router.get("")
def list_resources(
    type: str = Query(default="all"),
    category: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    sort: str = Query(default="default"),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(ResourceCenter).filter(ResourceCenter.status == "published")
    if type != "all":
        query = query.filter(ResourceCenter.resource_type == type)
    if category:
        query = query.filter(ResourceCenter.category == category)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                ResourceCenter.title.like(pattern),
                ResourceCenter.description.like(pattern),
                ResourceCenter.content.like(pattern),
            )
        )

    if sort == "latest":
        query = query.order_by(ResourceCenter.created_at.desc())
    elif sort == "hot":
        query = query.order_by((ResourceCenter.views + ResourceCenter.likes).desc())
    else:
        query = query.order_by(ResourceCenter.id.asc())

    resources = query.all()
    return {"items": [_resource_payload(item) for item in resources], "total": len(resources)}


@router.get("/{resource_id}")
def get_resource(resource_id: int, db: Session = Depends(get_db)) -> dict:
    resource = db.get(ResourceCenter, resource_id)
    if resource is None or resource.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return _resource_payload(resource, include_content=True)


@router.get("/{resource_id}/view")
def view_resource(resource_id: int, db: Session = Depends(get_db)) -> dict:
    resource = db.get(ResourceCenter, resource_id)
    if resource is None or resource.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    resource.views += 1
    db.commit()
    db.refresh(resource)
    return _resource_payload(resource, include_content=True)


@router.post("/{resource_id}/view")
def add_resource_view(resource_id: int, db: Session = Depends(get_db)) -> dict:
    resource = db.get(ResourceCenter, resource_id)
    if resource is None or resource.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    resource.views += 1
    db.commit()
    return {"id": resource.id, "views": resource.views}


@router.post("/{resource_id}/like")
def add_resource_like(resource_id: int, db: Session = Depends(get_db)) -> dict:
    resource = db.get(ResourceCenter, resource_id)
    if resource is None or resource.status != "published":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    resource.likes += 1
    db.commit()
    return {"id": resource.id, "likes": resource.likes}
