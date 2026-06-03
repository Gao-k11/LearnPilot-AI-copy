from __future__ import annotations

from .models import LearningResource


class ResourceRetriever:
    """Small RAG-style retriever over local course resources."""

    def retrieve(self, query: str, resources: list[LearningResource], top_k: int = 3) -> list[dict]:
        scored = []
        query_terms = set(query.lower())
        for resource in resources:
            point_hit = 1.0 if query in resource.knowledge_points else 0.0
            title_overlap = len(query_terms & set(resource.title.lower())) / max(len(query_terms), 1)
            score = point_hit * 0.8 + title_overlap * 0.2 + resource.quality * 0.05
            scored.append((score, resource))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "resource_id": resource.resource_id,
                "title": resource.title,
                "knowledge_points": list(resource.knowledge_points),
                "style": resource.style,
                "difficulty": resource.difficulty,
                "snippet": f"{resource.title} 覆盖 {', '.join(resource.knowledge_points)}，适合作为生成依据。",
            }
            for _, resource in scored[:top_k]
        ]
