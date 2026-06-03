DEMO_CASES = {
    "high_risk": {
        "label": "基础薄弱学生",
        "student": {
            "student_id": "stu_high",
            "goals": ["两周内完成 Python 入门"],
            "preferred_styles": ["video", "example"],
            "diagnostics": {"变量": 0.42, "条件判断": 0.28, "循环": 0.22, "函数": 0.18, "列表": 0.2},
        },
    },
    "steady": {
        "label": "中等进阶学生",
        "student": {
            "student_id": "stu_mid",
            "goals": ["完成函数和列表综合练习"],
            "preferred_styles": ["example", "quiz"],
            "diagnostics": {"变量": 0.88, "条件判断": 0.65, "循环": 0.48, "函数": 0.38, "列表": 0.42},
        },
    },
    "advanced": {
        "label": "优秀挑战学生",
        "student": {
            "student_id": "stu_adv",
            "goals": ["独立完成 Python 小项目"],
            "preferred_styles": ["project", "quiz"],
            "diagnostics": {"变量": 0.95, "条件判断": 0.86, "循环": 0.78, "函数": 0.74, "列表": 0.7},
        },
    },
}
