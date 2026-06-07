from backend.app.adapters.llm_adapter import MockLLMAdapter


class ResourceAgent:
    name = "ResourceAgent"

    def __init__(self, llm: MockLLMAdapter | None = None) -> None:
        self.llm = llm or MockLLMAdapter()

    def run(self, topic: str, weak_points: list[str], resource_types: list[str]) -> list[dict]:
        return [
            {
                "title": f"{topic} - {resource_type}",
                "resource_type": resource_type,
                "content": self._generate_content(topic, resource_type, weak_points),
            }
            for resource_type in resource_types
        ]

    def _generate_content(self, topic: str, resource_type: str, weak_points: list[str]) -> str:
        weak_text = "、".join(weak_points) if weak_points else topic
        generators = {
            "lecture": self._lecture,
            "mind_map": self._mind_map,
            "exercise": self._exercise,
            "reading": self._reading,
            "code_example": self._code_example,
            "video_script": self._video_script,
        }
        generator = generators.get(resource_type)
        if generator is None:
            return self.llm.generate_resource(topic, resource_type, weak_points)
        return generator(topic, weak_text)

    def _lecture(self, topic: str, weak_text: str) -> str:
        return f"""学习目标：
1. 理解 {topic} 的基本定义、适用场景和学习价值。
2. 掌握 {weak_text} 的关键知识点，并能用自己的话解释。
3. 能够完成一道基础例题，并指出解题过程中的关键步骤。

核心概念：
- 主题对象：{topic}
- 重点知识：{weak_text}
- 输入输出：明确问题输入、处理过程和期望结果。
- 应用场景：考试题、课程项目、工程案例和综合复习。

关键流程：
1. 阅读题目或材料，定位涉及的知识点。
2. 写出核心概念和关键公式或步骤。
3. 用一个最小例子验证理解。
4. 完成练习后复盘错误原因。

常见误区：
- 只记结论，不理解概念之间的关系。
- 忽略输入条件，直接套用模板。
- 例题会做，但无法迁移到新题型。
- 代码能运行，但不能解释参数含义。

例题解析：
题目：请说明 {topic} 中 {weak_text} 的作用，并举一个应用例子。
解析：先给出概念定义，再说明它解决的问题，最后用一个具体场景连接输入、处理步骤和输出结果。作答时要避免只写关键词，应写出完整因果关系。"""

    def _mind_map(self, topic: str, weak_text: str) -> str:
        return f"""{topic}
- 基础概念
  - 定义与背景
  - 核心术语
  - 适用场景
- 核心原理
  - 输入与输出
  - 关键流程
  - {weak_text}
- 训练与应用
  - 典型例题
  - 代码实操
  - 参数与结果解释
- 测评与复盘
  - 自测题
  - 错题原因
  - 下一轮学习计划"""

    def _exercise(self, topic: str, weak_text: str) -> str:
        return f"""选择题：
1. 关于 {topic} 的学习，下列说法最合理的是哪一项？
A. 只需要记住定义
B. 需要理解概念、流程、例题和应用场景
C. 不需要练习
D. 只看代码即可
参考答案：B

填空题：
1. 学习 {topic} 时，应先明确问题的输入、处理过程和______。
参考答案：输出结果

简答题：
1. 请用 3-5 句话说明 {weak_text} 在 {topic} 中的作用，并举一个具体例子。
参考答案要点：定义清楚、作用明确、例子具体、逻辑完整。

代码题：
1. 编写一个 Python 函数，接收一组学习得分，返回平均分，并根据平均分输出“需要复习”或“可以进入下一阶段”。
要求：代码能运行，变量命名清晰，并写出一次测试结果。"""

    def _reading(self, topic: str, weak_text: str) -> str:
        return f"""拓展阅读主题：
- {topic} 的课程基础与典型应用
- {weak_text} 的常见题型和实践场景
- 从概念理解到代码实现的学习迁移

推荐关键词：
- {topic}
- {weak_text}
- 核心概念
- 模型评估
- 实践案例
- 错题复盘

阅读任务：
1. 找到 2 篇课程资料或教材章节，标注与 {weak_text} 相关的段落。
2. 提炼 5 个关键词，并为每个关键词写一句解释。
3. 记录 3 个仍不理解的问题，带到下一次智能辅导中提问。
4. 用 100 字总结 {topic} 的学习收获。"""

    def _code_example(self, topic: str, weak_text: str) -> str:
        return f"""可运行 Python 示例代码：

```python
def evaluate_learning(scores):
    if not scores:
        return {{"average": 0, "level": "需要补充练习"}}

    average = sum(scores) / len(scores)
    if average >= 85:
        level = "掌握较好"
    elif average >= 60:
        level = "基础达标，建议复盘薄弱点"
    else:
        level = "需要补充练习"

    return {{"average": round(average, 2), "level": level}}


if __name__ == "__main__":
    topic = "{topic}"
    weak_points = "{weak_text}"
    scores = [72, 80, 65, 90]
    result = evaluate_learning(scores)
    print("学习主题:", topic)
    print("薄弱点:", weak_points)
    print("评估结果:", result)
```

运行说明：
1. 将代码保存为 `learning_demo.py`。
2. 执行 `python learning_demo.py`。
3. 修改 `scores`，观察平均分和学习建议如何变化。"""

    def _video_script(self, topic: str, weak_text: str) -> str:
        return f"""分镜 1：引入问题
画面描述：屏幕展示学生的学习目标“{topic}”，旁边列出薄弱点“{weak_text}”。
字幕：今天我们用 5 分钟梳理 {topic} 的学习路径。
讲解词：先明确目标，再定位薄弱点，最后用练习和复盘完成闭环。

分镜 2：讲解核心概念
画面描述：出现三层结构图：概念、流程、例题。
字幕：先理解概念，再掌握流程。
讲解词：学习 {topic} 时，不要只背结论，要能解释每一步为什么成立。

分镜 3：演示例题
画面描述：展示一道与 {weak_text} 相关的例题，逐步高亮解题步骤。
字幕：例题训练关注步骤和依据。
讲解词：每一步都要写出依据，这样才能发现自己真正卡住的位置。

分镜 4：代码或实践
画面描述：展示简短 Python 代码和运行结果。
字幕：用最小案例验证理解。
讲解词：代码实操不是为了复杂，而是为了把抽象概念变成可观察结果。

分镜 5：复盘总结
画面描述：屏幕展示错题清单、关键词和下一步计划。
字幕：复盘决定下一轮学习质量。
讲解词：把错误归类，更新学习计划，下一次学习会更有针对性。"""
