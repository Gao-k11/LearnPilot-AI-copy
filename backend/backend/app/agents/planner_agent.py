class PlannerAgent:
    name = "PlannerAgent"

    def run(self, goal: str, weak_points: list[str], resource_ids: list[int]) -> dict:
        focus_text = "、".join(weak_points) if weak_points else "课程核心知识点"
        node_templates = [
            {
                "title": "基础概念学习",
                "objective": f"围绕“{goal}”，梳理 {focus_text} 的基本定义、适用场景和常见术语，形成一页概念笔记。",
                "estimated_minutes": 30,
            },
            {
                "title": "核心原理理解",
                "objective": f"深入理解 {focus_text} 的关键原理、输入输出关系和推导逻辑，能用自己的话解释核心机制。",
                "estimated_minutes": 45,
            },
            {
                "title": "例题训练",
                "objective": f"完成与 {focus_text} 相关的典型例题训练，记录解题步骤、易错点和需要回看的视频或讲义位置。",
                "estimated_minutes": 50,
            },
            {
                "title": "代码实操",
                "objective": f"使用 Python 或课程指定工具完成一个 {focus_text} 的最小实践案例，能够运行代码并解释关键参数。",
                "estimated_minutes": 60,
            },
            {
                "title": "阶段测评",
                "objective": f"围绕“{goal}”完成一次阶段自测，检查概念理解、计算题、应用题和代码题的掌握情况。",
                "estimated_minutes": 40,
            },
            {
                "title": "错题复盘",
                "objective": f"复盘阶段测评和练习中的错误，归纳 {focus_text} 的薄弱环节，并更新下一轮学习计划。",
                "estimated_minutes": 35,
            },
        ]

        nodes = []
        for index, template in enumerate(node_templates, start=1):
            nodes.append(
                {
                    "step_order": index,
                    "title": template["title"],
                    "objective": template["objective"],
                    "estimated_minutes": template["estimated_minutes"],
                    "resource_id": self._pick_resource_id(resource_ids, index - 1),
                }
            )
        return {"title": f"{goal} 个性化学习路径", "goal": goal, "nodes": nodes}

    def _pick_resource_id(self, resource_ids: list[int], index: int) -> int | None:
        if not resource_ids:
            return None
        if index < len(resource_ids):
            return resource_ids[index]
        return resource_ids[index % len(resource_ids)]
