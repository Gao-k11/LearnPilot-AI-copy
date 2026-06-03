from __future__ import annotations

from .models import KnowledgeNode, LearningResource


DEFAULT_KNOWLEDGE_GRAPH = [
    KnowledgeNode("变量", importance=1.0),
    KnowledgeNode("条件判断", prerequisites=("变量",), importance=1.0),
    KnowledgeNode("循环", prerequisites=("变量", "条件判断"), importance=1.1),
    KnowledgeNode("函数", prerequisites=("变量", "条件判断"), importance=1.2),
    KnowledgeNode("列表", prerequisites=("循环",), importance=1.0),
    KnowledgeNode("项目实践", prerequisites=("函数", "列表"), importance=1.3),
]


DEFAULT_RESOURCES = [
    LearningResource("r001", "变量与赋值微课", ("变量",), 0.25, "video", 12, 0.86),
    LearningResource("r002", "条件判断例题讲解", ("条件判断",), 0.35, "example", 18, 0.88),
    LearningResource("r003", "循环结构闯关练习", ("循环",), 0.48, "quiz", 25, 0.91),
    LearningResource("r004", "函数拆解与参数训练", ("函数",), 0.55, "example", 30, 0.9),
    LearningResource("r005", "列表操作速查与练习", ("列表",), 0.5, "text", 20, 0.82),
    LearningResource("r006", "小型成绩管理项目", ("项目实践", "函数", "列表"), 0.72, "project", 60, 0.93),
    LearningResource("r007", "循环常见错题集", ("循环", "条件判断"), 0.58, "quiz", 35, 0.87),
    LearningResource("r008", "函数与列表综合案例", ("函数", "列表"), 0.68, "project", 45, 0.89),
]
