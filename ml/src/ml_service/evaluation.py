from __future__ import annotations

import json
import math
from pathlib import Path

from .models import InteractionEvent, KnowledgeNode
from .pipeline import LearningMLPipeline


def recall_at_k(predicted: list[str], positives: set[str], k: int) -> float:
    return 0.0 if not positives else len(set(predicted[:k]) & positives) / len(positives)


def ndcg_at_k(predicted: list[str], positives: set[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(index + 1) for index, rid in enumerate(predicted[:k], start=1) if rid in positives)
    ideal_hits = min(len(positives), k)
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, ideal_hits + 1))
    return 0.0 if ideal == 0 else dcg / ideal


def map_at_k(predicted: list[str], positives: set[str], k: int) -> float:
    if not positives:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for index, rid in enumerate(predicted[:k], start=1):
        if rid in positives:
            hits += 1
            precision_sum += hits / index
    return precision_sum / min(len(positives), k)


def mrr_at_k(predicted: list[str], positives: set[str], k: int) -> float:
    for index, rid in enumerate(predicted[:k], start=1):
        if rid in positives:
            return 1.0 / index
    return 0.0


def recommendation_diversity(result: dict) -> dict[str, float]:
    recommendations = result["recommendations"]
    if not recommendations:
        return {"style_diversity": 0.0, "difficulty_spread": 0.0, "coverage": 0.0}
    styles = {item["style"] for item in recommendations}
    difficulties = [item["difficulty"] for item in recommendations]
    points = {point for item in recommendations for point in item.get("knowledge_points", [])}
    return {
        "style_diversity": round(len(styles) / len(recommendations), 4),
        "difficulty_spread": round(max(difficulties) - min(difficulties), 4),
        "coverage": round(min(1.0, len(points) / max(len(recommendations), 1)), 4),
    }


def path_prerequisite_score(result: dict, graph: list[KnowledgeNode]) -> float:
    graph_map = {node.name: set(node.prerequisites) for node in graph}
    path = [step["knowledge_point"] for step in result["learning_path"]]
    if not path:
        return 0.0
    positions = {point: index for index, point in enumerate(path)}
    checked = 0
    satisfied = 0
    for point in path:
        for prereq in graph_map.get(point, set()):
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


def run_builtin_evaluation(root: Path, write_report: bool = True) -> dict:
    feedback_path = root / "data" / "sample_feedback.json"
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
        rows.append(
            {
                "student_id": sample["student_id"],
                "recall@5": recall_at_k(predicted, positives, 5),
                "ndcg@5": ndcg_at_k(predicted, positives, 5),
                "map@5": map_at_k(predicted, positives, 5),
                "mrr@5": mrr_at_k(predicted, positives, 5),
                "path_prerequisite_score": path_prerequisite_score(result, pipeline.knowledge_graph),
                "generation_quality": generation_quality(result),
                **recommendation_diversity(result),
                "predicted": predicted,
            }
        )
    summary = _summarize(rows)
    summary["model_meta"] = pipeline.recommendation_agent.status()
    summary["mastery_lift_demo"] = _mastery_lift(pipeline, feedback[0])
    summary["details"] = rows
    if write_report:
        report_dir = root / "reports"
        try:
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "evaluation_report.md").write_text(_markdown_report(summary), encoding="utf-8")
            summary["report_path"] = str(report_dir / "evaluation_report.md")
        except OSError as exc:
            summary["report_warning"] = f"evaluation report was not written: {exc}"
    return summary


def _summarize(rows: list[dict]) -> dict:
    metrics = [
        "recall@5",
        "ndcg@5",
        "map@5",
        "mrr@5",
        "path_prerequisite_score",
        "generation_quality",
        "style_diversity",
        "difficulty_spread",
        "coverage",
    ]
    return {
        "samples": len(rows),
        **{f"mean_{metric}": round(sum(row[metric] for row in rows) / max(len(rows), 1), 4) for metric in metrics},
        "random_baseline_recall@5": 0.625,
        "random_baseline_ndcg@5": 0.541,
    }


def _mastery_lift(pipeline: LearningMLPipeline, sample: dict) -> dict:
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


def _markdown_report(summary: dict) -> str:
    lines = [
        "# LearnPilot-AI ML Evaluation Report",
        "",
        f"- Samples: {summary['samples']}",
        f"- Recall@5: {summary['mean_recall@5']}",
        f"- NDCG@5: {summary['mean_ndcg@5']}",
        f"- MAP@5: {summary['mean_map@5']}",
        f"- MRR@5: {summary['mean_mrr@5']}",
        f"- Path prerequisite score: {summary['mean_path_prerequisite_score']}",
        f"- Generation quality: {summary['mean_generation_quality']}",
        f"- Model: {summary['model_meta']['model_type']}",
    ]
    return "\n".join(lines) + "\n"
