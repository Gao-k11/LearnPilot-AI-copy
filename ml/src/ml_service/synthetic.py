from __future__ import annotations

import json
import random
from dataclasses import asdict
from pathlib import Path

from .models import InteractionEvent, KnowledgeNode, LearningResource


SEED = 20260605
STAGES = (
    ("foundation", ("变量", "数据类型", "输入输出", "条件判断")),
    ("structure", ("循环", "字符串", "列表", "字典", "集合", "元组")),
    ("function", ("函数", "作用域", "递归", "模块", "包管理")),
    ("robustness", ("文件读写", "异常处理", "调试", "测试", "日志")),
    ("object", ("面向对象", "类与对象", "继承", "封装", "多态")),
    ("algorithm", ("排序", "查找", "复杂度", "栈队列", "树结构")),
    ("project", ("项目实践", "需求拆解", "接口设计", "数据持久化", "综合复盘")),
)
STYLES = ("video", "text", "example", "quiz", "project")


def generate_knowledge_graph(target_count: int = 108, seed: int = SEED) -> list[KnowledgeNode]:
    rng = random.Random(seed)
    nodes: list[KnowledgeNode] = []
    previous_stage_points: list[str] = []
    for stage_index, (_, bases) in enumerate(STAGES):
        stage_points = []
        for base in bases:
            variants = [base] + [f"{base}-{i}" for i in range(1, 4)]
            for name in variants:
                if len(nodes) >= target_count:
                    break
                prereq_pool = previous_stage_points[-8:] + stage_points[-4:]
                prereq_count = 0 if not prereq_pool or stage_index == 0 else rng.randint(1, min(2, len(prereq_pool)))
                prerequisites = tuple(rng.sample(prereq_pool, prereq_count)) if prereq_count else ()
                importance = round(rng.uniform(0.75, 1.35), 2)
                nodes.append(KnowledgeNode(name=name, prerequisites=prerequisites, importance=importance))
                stage_points.append(name)
            if len(nodes) >= target_count:
                break
        previous_stage_points.extend(stage_points)
        if len(nodes) >= target_count:
            break
    return nodes


def generate_resources(
    graph: list[KnowledgeNode],
    target_count: int = 540,
    seed: int = SEED,
) -> list[LearningResource]:
    rng = random.Random(seed + 1)
    resources: list[LearningResource] = []
    nodes = {node.name: node for node in graph}
    points = list(nodes)
    for index in range(target_count):
        primary = points[index % len(points)]
        related = [primary]
        if rng.random() < 0.45:
            related.append(rng.choice(points))
        style = rng.choice(STYLES)
        difficulty_base = min(0.92, max(0.12, 0.2 + (index % len(points)) / len(points) * 0.7))
        difficulty = round(min(0.95, max(0.1, difficulty_base + rng.uniform(-0.08, 0.08))), 2)
        minutes = rng.randint(8, 75)
        quality = round(rng.uniform(0.72, 0.96), 2)
        tags = tuple(sorted({style, "python", _stage_for_point(primary), "synthetic"}))
        resource = LearningResource(
            resource_id=f"sr{index + 1:04d}",
            title=f"{primary}{_style_title(style)}",
            knowledge_points=tuple(dict.fromkeys(related)),
            difficulty=difficulty,
            style=style,  # type: ignore[arg-type]
            estimated_minutes=minutes,
            quality=quality,
            content=(
                f"本资源围绕 {primary} 展开，覆盖概念、步骤、常见错误和迁移练习。"
                f"学习者需要关注 {primary} 的适用条件、边界情况和与先修知识的连接。"
            ),
            prerequisites_covered=nodes[primary].prerequisites,
            audience=(_audience_for_difficulty(difficulty),),
            tags=tags,
            question=f"请完成一道关于 {primary} 的{_style_question(style)}，并说明关键步骤。",
            answer=f"答案应正确使用 {primary}，包含输入、处理、输出和边界检查。",
            explanation=f"解析重点是把 {primary} 拆成可验证步骤，并说明常见错因。",
        )
        resources.append(resource)
    return resources


def generate_students_and_events(
    graph: list[KnowledgeNode],
    resources: list[LearningResource],
    student_count: int = 1000,
    event_count: int = 6000,
    seed: int = SEED,
) -> tuple[list[dict], list[InteractionEvent]]:
    rng = random.Random(seed + 2)
    points = [node.name for node in graph]
    students = []
    for index in range(student_count):
        level = rng.choice(("foundation", "practice", "integration", "project"))
        preferred_styles = rng.sample(STYLES, rng.randint(1, 2))
        mastery = {point: round(rng.uniform(0.15, 0.9), 2) for point in rng.sample(points, 12)}
        students.append(
            {
                "student_id": f"stu_{index + 1:04d}",
                "goals": [f"提升 Python {level} 阶段能力"],
                "preferred_styles": preferred_styles,
                "diagnostics": mastery,
                "learning_stage": level,
            }
        )

    resource_by_point: dict[str, list[LearningResource]] = {}
    for resource in resources:
        for point in resource.knowledge_points:
            resource_by_point.setdefault(point, []).append(resource)

    events: list[InteractionEvent] = []
    for index in range(event_count):
        student = students[index % student_count]
        weak_point = min(student["diagnostics"], key=student["diagnostics"].get)
        candidates = resource_by_point.get(weak_point) or resources
        resource = rng.choice(candidates)
        preference_bonus = 0.12 if resource.style in student["preferred_styles"] else -0.03
        difficulty_gap = abs(resource.difficulty - (sum(student["diagnostics"].values()) / len(student["diagnostics"]) + 0.12))
        score = max(0.0, min(1.0, resource.quality - difficulty_gap + preference_bonus + rng.uniform(-0.12, 0.08)))
        completed = score > 0.48 or rng.random() > 0.2
        liked = True if score > 0.68 else False if score < 0.36 else None
        events.append(
            InteractionEvent(
                student_id=student["student_id"],
                resource_id=resource.resource_id,
                knowledge_points=resource.knowledge_points,
                score=round(score, 3),
                completed=completed,
                dwell_seconds=rng.randint(120, 1800),
                liked=liked,
                timestamp=index,
            )
        )
    return students, events


def write_synthetic_dataset(output_dir: Path, seed: int = SEED) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    graph = generate_knowledge_graph(seed=seed)
    resources = generate_resources(graph, seed=seed)
    students, events = generate_students_and_events(graph, resources, seed=seed)
    (output_dir / "knowledge_graph.json").write_text(
        json.dumps([asdict(node) for node in graph], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "resources.json").write_text(
        json.dumps([asdict(resource) for resource in resources], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "students.json").write_text(json.dumps(students, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "events.json").write_text(
        json.dumps([asdict(event) for event in events], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "knowledge_points": len(graph),
        "resources": len(resources),
        "students": len(students),
        "events": len(events),
    }


def load_synthetic_dataset(input_dir: Path) -> tuple[list[KnowledgeNode], list[LearningResource], list[dict], list[InteractionEvent]]:
    graph_path = input_dir / "knowledge_graph.json"
    if not graph_path.exists():
        write_synthetic_dataset(input_dir)
    graph = [KnowledgeNode(**item) for item in json.loads(graph_path.read_text(encoding="utf-8"))]
    resources = [
        LearningResource(
            **{
                **item,
                "knowledge_points": tuple(item.get("knowledge_points", [])),
                "prerequisites_covered": tuple(item.get("prerequisites_covered", [])),
                "audience": tuple(item.get("audience", [])),
                "tags": tuple(item.get("tags", [])),
            }
        )
        for item in json.loads((input_dir / "resources.json").read_text(encoding="utf-8"))
    ]
    students = json.loads((input_dir / "students.json").read_text(encoding="utf-8"))
    events = [
        InteractionEvent(
            **{
                **item,
                "knowledge_points": tuple(item.get("knowledge_points", [])),
            }
        )
        for item in json.loads((input_dir / "events.json").read_text(encoding="utf-8"))
    ]
    return graph, resources, students, events


def _style_title(style: str) -> str:
    return {
        "video": "微课",
        "text": "速查手册",
        "example": "案例讲解",
        "quiz": "闯关练习",
        "project": "项目任务",
    }[style]


def _style_question(style: str) -> str:
    return "项目任务" if style == "project" else "练习题"


def _audience_for_difficulty(difficulty: float) -> str:
    if difficulty < 0.4:
        return "foundation"
    if difficulty < 0.65:
        return "practice"
    if difficulty < 0.8:
        return "integration"
    return "project"


def _stage_for_point(point: str) -> str:
    for stage, bases in STAGES:
        if any(point.startswith(base) for base in bases):
            return stage
    return "general"
