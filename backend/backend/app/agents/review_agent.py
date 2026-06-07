class ReviewAgent:
    name = "ReviewAgent"

    sensitive_words = [
        "暴力",
        "违法",
        "歧视",
        "赌博",
        "诈骗",
        "violence",
        "illegal",
        "discrimination",
    ]

    knowledge_keywords = [
        "学习",
        "课程",
        "知识",
        "概念",
        "例题",
        "代码",
        "测评",
        "复盘",
        "机器学习",
        "人工智能",
        "神经网络",
        "CNN",
        "卷积",
        "池化",
        "反向传播",
        "决策树",
        "支持向量机",
        "聚类",
        "模型",
        "Python",
    ]

    required_sections = {
        "lecture": ["学习目标", "核心概念", "关键流程", "常见误区", "例题解析"],
        "mind_map": ["-", "  -"],
        "exercise": ["选择题", "填空题", "简答题", "代码题"],
        "reading": ["拓展阅读主题", "推荐关键词", "阅读任务"],
        "code_example": ["```python", "def ", 'if __name__ == "__main__"'],
        "video_script": ["分镜", "画面描述", "字幕", "讲解词"],
    }

    def run(self, resource: dict) -> dict:
        title = str(resource.get("title", ""))
        resource_type = str(resource.get("resource_type", ""))
        content = str(resource.get("content", ""))
        combined = f"{title}\n{content}"

        too_short = len(content.strip()) < 120
        has_sensitive_word = self._has_sensitive_word(combined)
        relevance_score = self._score_relevance(combined)
        completeness_score = self._score_completeness(resource_type, content)
        profile_score = self._score_profile_match(title, content)
        accuracy_score = round((relevance_score * 0.45) + (completeness_score * 0.4) + (profile_score * 0.15), 2)
        risk_level = "高" if has_sensitive_word else ("中" if too_short or relevance_score < 0.45 else "低")
        source_basis = "课程知识库" if relevance_score >= 0.55 else "缺少明确课程知识库依据"

        rejected_reasons = []
        if too_short:
            rejected_reasons.append("内容过短")
        if has_sensitive_word:
            rejected_reasons.append("包含敏感词")
        if relevance_score < 0.35:
            rejected_reasons.append("与课程知识库无关")
        if completeness_score < 0.5:
            rejected_reasons.append("内容完整性不足")

        review_status = "rejected" if rejected_reasons else "approved"
        notes = (
            f"准确性评分：{accuracy_score:.2f}；"
            f"相关性评分：{relevance_score:.2f}；"
            f"风险等级：{risk_level}；"
            f"依据：{source_basis}；"
            f"完整性评分：{completeness_score:.2f}；"
            f"画像匹配评分：{profile_score:.2f}"
        )
        if rejected_reasons:
            notes = f"{notes}；拒绝原因：{'、'.join(rejected_reasons)}"

        return {**resource, "review_status": review_status, "review_notes": notes}

    def _has_sensitive_word(self, text: str) -> bool:
        lowered = text.lower()
        return any(word.lower() in lowered for word in self.sensitive_words)

    def _score_relevance(self, text: str) -> float:
        matched_count = sum(1 for keyword in self.knowledge_keywords if keyword.lower() in text.lower())
        if matched_count >= 6:
            return 0.92
        if matched_count >= 4:
            return 0.82
        if matched_count >= 2:
            return 0.62
        if matched_count == 1:
            return 0.38
        return 0.12

    def _score_completeness(self, resource_type: str, content: str) -> float:
        required = self.required_sections.get(resource_type)
        if not required:
            return 0.75 if len(content.strip()) >= 120 else 0.3

        matched_count = sum(1 for section in required if section in content)
        section_score = matched_count / len(required)
        length_bonus = 0.1 if len(content.strip()) >= 240 else 0
        return round(min(1.0, section_score * 0.9 + length_bonus), 2)

    def _score_profile_match(self, title: str, content: str) -> float:
        topic = title.split(" - ", 1)[0].strip()
        if topic and topic in content:
            return 0.9
        if any(keyword in content for keyword in ["薄弱", "复盘", "学习目标", "测评", "练习"]):
            return 0.78
        return 0.55
