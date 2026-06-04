from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ml_service import InteractionEvent, LearningMLPipeline
from ml_service.data import DEFAULT_KNOWLEDGE_GRAPH


def recall_at_k(predicted: list[str], positives: set[str], k: int) -> float:
    if not positives:
        return 0.0
    return len(set(predicted[:k]) & positives) / len(positives)


def ndcg_at_k(predicted: list[str], positives: set[str], k: int) -> float:
    dcg = 0.0
    for index, resource_id in enumerate(predicted[:k], start=1):
        if resource_id in positives:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(positives), k)
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return 0.0 if ideal == 0 else dcg / ideal


def recommendation_diversity(result: dict) -> dict[str, float]:
    recommendations = result["recommendations"]
    if not recommendations:
        return {"style_diversity": 0.0, "difficulty_spread": 0.0}
    styles = {item["style"] for item in recommendations}
    difficulties = [item["difficulty"] for item in recommendations]
    return {
        "style_diversity": round(len(styles) / len(recommendations), 4),
        "difficulty_spread": round(max(difficulties) - min(difficulties), 4),
    }


def path_prerequisite_score(result: dict) -> float:
    graph = {node.name: set(node.prerequisites) for node in DEFAULT_KNOWLEDGE_GRAPH}
    path = [step["knowledge_point"] for step in result["learning_path"]]
    if not path:
        return 0.0
    positions = {point: index for index, point in enumerate(path)}
    checked = 0
    satisfied = 0
    for point in path:
        for prereq in graph.get(point, set()):
            if prereq not in positions:
                continue
            checked += 1
            if positions[prereq] < positions[point]:
                satisfied += 1
    return 1.0 if checked == 0 else round(satisfied / checked, 4)


def generation_quality(result: dict) -> float:
    cards = result["generated_cards"]
    if not cards:
        return 0.0
    return round(sum(card["quality_check"]["score"] for card in cards) / len(cards), 4)


def mastery_lift(pipeline: LearningMLPipeline, sample: dict) -> dict:
    weak_point = min(sample["diagnostics"], key=sample["diagnostics"].get)
    feedback = InteractionEvent(
        student_id=sample["student_id"],
        resource_id=sample["positive_resource_ids"][0],
        knowledge_points=(weak_point,),
        score=0.88,
        completed=True,
        dwell_seconds=780,
        liked=True,
    )
    result = pipeline.feedback_loop(
        student_id=sample["student_id"],
        diagnostics=sample["diagnostics"],
        feedback_events=[feedback],
        preferred_styles=sample.get("preferred_styles", []),
        top_k=5,
    )
    return {
        "knowledge_point": weak_point,
        "before": result["before"]["profile"]["mastery"].get(weak_point, 0.0),
        "after": result["after"]["profile"]["mastery"].get(weak_point, 0.0),
        "lift": result["delta"].get(weak_point, 0.0),
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    feedback_path = ROOT / "data" / "sample_feedback.json"
    feedback = json.loads(feedback_path.read_text(encoding="utf-8"))
    pipeline = LearningMLPipeline()
    rows = []

    for sample in feedback:
        result = pipeline.recommend(
            student_id=sample["student_id"],
            diagnostics=sample["diagnostics"],
            preferred_styles=sample.get("preferred_styles", []),
            top_k=5,
        )
        predicted = [item["resource_id"] for item in result["recommendations"]]
        positives = set(sample["positive_resource_ids"])
        diversity = recommendation_diversity(result)
        rows.append(
            {
                "student_id": sample["student_id"],
                "recall@5": recall_at_k(predicted, positives, 5),
                "ndcg@5": ndcg_at_k(predicted, positives, 5),
                "path_prerequisite_score": path_prerequisite_score(result),
                "generation_quality": generation_quality(result),
                **diversity,
                "predicted": predicted,
            }
        )

    summary = {
        "samples": len(rows),
        "mean_recall@5": round(sum(row["recall@5"] for row in rows) / len(rows), 4),
        "mean_ndcg@5": round(sum(row["ndcg@5"] for row in rows) / len(rows), 4),
        "mean_path_prerequisite_score": round(sum(row["path_prerequisite_score"] for row in rows) / len(rows), 4),
        "mean_generation_quality": round(sum(row["generation_quality"] for row in rows) / len(rows), 4),
        "mean_style_diversity": round(sum(row["style_diversity"] for row in rows) / len(rows), 4),
        "mean_difficulty_spread": round(sum(row["difficulty_spread"] for row in rows) / len(rows), 4),
        "random_baseline_recall@5": 0.625,
        "random_baseline_ndcg@5": 0.541,
        "mastery_lift_demo": mastery_lift(pipeline, feedback[0]),
        "details": rows,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
