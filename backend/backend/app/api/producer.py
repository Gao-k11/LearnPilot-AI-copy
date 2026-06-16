from __future__ import annotations

import ast
import json
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.security import optional_user
from backend.app.models import (
    ProducerArtifact,
    ProducerChatMessage,
    ProducerTask,
    ResourceCenter,
    User,
)


router = APIRouter(prefix="/producer", tags=["producer"])

DEFAULT_TYPES = ["lecture", "mind_map", "exercise", "video", "code", "dataset", "roadmap"]


class ProducerTaskRequest(BaseModel):
    topic: str = Field(default="通用学习主题", max_length=255)
    requirement: str = ""
    types: list[str] = Field(default_factory=lambda: list(DEFAULT_TYPES))
    task_type: str = Field(default="multi_agent_generation", max_length=64)

    model_config = ConfigDict(extra="allow")


class ProducerChatRequest(BaseModel):
    session_id: str | None = Field(default=None, max_length=64)
    message: str = Field(min_length=1)
    topic: str = Field(default="学习主题", max_length=255)


class ProducerRunRequest(BaseModel):
    language: str = Field(default="python", max_length=32)
    code: str


def _matching_resources(
    db: Session,
    keyword: str,
    resource_types: list[str] | None = None,
    limit: int = 8,
) -> list[ResourceCenter]:
    pattern = f"%{keyword.strip()}%"
    query = db.query(ResourceCenter).filter(ResourceCenter.status == "published")
    if resource_types:
        query = query.filter(ResourceCenter.resource_type.in_(resource_types))
    if keyword.strip():
        query = query.filter(
            or_(
                ResourceCenter.title.ilike(pattern),
                ResourceCenter.description.ilike(pattern),
                ResourceCenter.content.ilike(pattern),
                ResourceCenter.knowledge_point.ilike(pattern),
                ResourceCenter.tags.ilike(pattern),
            )
        )
    return query.order_by(ResourceCenter.views.desc(), ResourceCenter.id.asc()).limit(limit).all()


def _resource_reference(resource: ResourceCenter) -> dict:
    return {
        "id": resource.id,
        "title": resource.title,
        "type": resource.resource_type,
        "url": "" if resource.resource_type == "document" else (resource.url or ""),
        "detail_url": f"/resources/{resource.id}",
        "description": resource.description or resource.summary or "",
    }


def _roadmap_nodes(topic: str) -> list[dict]:
    return [
        {
            "step": 1,
            "title": "基础概念",
            "description": f"理解 {topic} 的定义、适用场景、输入输出和关键术语。",
            "estimated_minutes": 30,
        },
        {
            "step": 2,
            "title": "核心原理",
            "description": f"拆解 {topic} 的核心流程，并通过图示建立知识点之间的联系。",
            "estimated_minutes": 45,
        },
        {
            "step": 3,
            "title": "例题与练习",
            "description": f"完成 {topic} 的选择题、简答题和关键步骤推导。",
            "estimated_minutes": 40,
        },
        {
            "step": 4,
            "title": "代码实操",
            "description": f"运行一个最小 {topic} 示例，观察参数、输入和输出变化。",
            "estimated_minutes": 50,
        },
        {
            "step": 5,
            "title": "综合复盘",
            "description": f"总结 {topic} 的常见误区，形成个人复习清单并完成自测。",
            "estimated_minutes": 30,
        },
    ]


def _exercise_items(topic: str) -> list[dict]:
    return [
        {
            "type": "single_choice",
            "question": f"学习 {topic} 时，最合理的第一步是什么？",
            "options": ["明确问题与输入输出", "直接背诵结论", "跳过基础概念", "只复制代码"],
            "answer": "A",
            "analysis": "先明确问题边界、输入输出和目标，后续原理分析与实践才有清晰依据。",
        },
        {
            "type": "single_choice",
            "question": f"检验自己是否真正理解 {topic} 的有效方法是？",
            "options": ["只看答案", "用自己的话解释并完成新例题", "重复阅读标题", "忽略错误"],
            "answer": "B",
            "analysis": "能够解释原理并迁移到新问题，说明知识已经从记忆转化为理解。",
        },
        {
            "type": "short_answer",
            "question": f"请用三到五句话说明 {topic} 的核心原理和一个典型应用。",
            "options": [],
            "answer": f"答案应包含 {topic} 的定义、关键处理流程、输入输出以及一个具体应用场景。",
            "analysis": "回答时应建立完整因果关系，避免只罗列关键词。",
        },
    ]


def _video_items(db: Session, topic: str) -> list[dict]:
    resources = _matching_resources(db, topic, ["video"], limit=6)
    items = [
        {
            "title": resource.title,
            "url": resource.url or "",
            "description": resource.description or resource.summary or f"{topic} 视频资源",
        }
        for resource in resources
        if resource.url
    ]
    if items:
        return items
    return [
        {
            "title": f"{topic} 基础公开视频",
            "url": "https://www.youtube.com/watch?v=aircAruvnKk",
            "description": "通过动画和直观示例理解神经网络的基本工作方式。",
        },
        {
            "title": f"{topic} 深度学习公开课",
            "url": "https://www.youtube.com/watch?v=IHZwWFHWa-w",
            "description": "适合结合课程讲义进行拓展学习的公开视频。",
        },
    ]


def _python_code(topic: str) -> str:
    return f'''def explain_topic(name):
    steps = [
        "明确输入与输出",
        "拆解核心原理",
        "运行最小案例",
        "记录结果并复盘",
    ]
    return {{"topic": name, "steps": steps}}


result = explain_topic("{topic}")
print(result)
'''


def _code_items(topic: str, language: str) -> list[dict]:
    normalized = language.lower()
    if normalized in {"javascript", "js"}:
        code = (
            f'const topic = "{topic}";\n'
            'const steps = ["明确输入输出", "理解核心原理", "完成最小案例", "复盘结果"];\n'
            'console.log({ topic, steps });\n'
        )
        language_name = "javascript"
    else:
        code = _python_code(topic)
        language_name = "python"
    return [
        {
            "title": f"{topic} 最小示例",
            "code": code,
            "explanation": f"该 {language_name} 示例用可运行的最小结构展示 {topic} 的学习与验证流程，可继续替换为具体算法实现。",
        }
    ]


def _dataset_items(keyword: str) -> list[dict]:
    return [
        {
            "title": "MNIST",
            "description": f"适合进行 {keyword} 入门实验的手写数字图像数据集。",
            "url": "https://www.kaggle.com/datasets/hojjatk/mnist-dataset",
        },
        {
            "title": "CIFAR-10",
            "description": f"包含十类彩色图像，可用于 {keyword} 分类与模型对比实验。",
            "url": "https://www.cs.toronto.edu/~kriz/cifar.html",
        },
        {
            "title": "UCI Machine Learning Repository",
            "description": f"可按任务类型选择适合 {keyword} 实践的公开结构化数据集。",
            "url": "https://archive.ics.uci.edu/",
        },
    ]


def _lecture(topic: str, requirement: str, references: list[dict]) -> dict:
    reference_text = "、".join(item["title"] for item in references[:3]) or "暂无匹配资源"
    content = f"""# {topic} 知识点讲解

## 学习目标
理解 {topic} 的基本定义、核心流程与典型应用，并能根据一个具体问题说明输入、处理过程和输出结果。

## 核心原理
学习 {topic} 时应先确定问题边界，再拆分关键步骤，最后用最小案例验证每一步。不要只记忆结论，要说明每个步骤为什么成立、参数变化会造成什么影响。

## 学习重点
1. 建立术语与实际问题之间的对应关系。
2. 掌握关键流程及其前后依赖。
3. 通过例题和代码验证理解。
4. 记录错误原因并形成复习清单。

## 个性化要求
{requirement or "面向课程学习与复习，兼顾概念理解和实践应用。"}

## 资源库参考
{reference_text}
"""
    return {"title": f"{topic} 知识点讲解", "content": content, "references": references}


def _mind_map(topic: str) -> dict:
    content = f"""# {topic}
- 基础概念
  - 定义与背景
  - 输入与输出
  - 适用场景
- 核心原理
  - 关键步骤
  - 参数与结果
  - 常见变体
- 实践应用
  - 典型例题
  - 代码案例
  - 数据集实验
- 评估复盘
  - 常见误区
  - 自测问题
  - 后续学习路线
"""
    return {"title": f"{topic} 思维导图", "content": content}


def _reading(topic: str, references: list[dict]) -> dict:
    return {
        "title": f"{topic} 拓展阅读",
        "content": (
            f"围绕 {topic}，建议按“概念定义、核心原理、典型案例、工程实践、复盘总结”的顺序阅读。"
            "每完成一份资料，提炼五个关键词、两个仍不清楚的问题和一个可运行实验，避免停留在被动浏览。"
        ),
        "references": references,
    }


def _normalize_types(types: list[str]) -> list[str]:
    aliases = {
        "exercises": "exercise",
        "code_example": "code",
        "code_examples": "code",
        "videos": "video",
        "datasets": "dataset",
    }
    normalized = []
    for item in types or DEFAULT_TYPES:
        value = aliases.get(str(item).strip().lower(), str(item).strip().lower())
        if value and value not in normalized:
            normalized.append(value)
    return normalized or list(DEFAULT_TYPES)


def _build_task_result(db: Session, topic: str, requirement: str, requested_types: list[str]) -> dict:
    references = [
        _resource_reference(item)
        for item in _matching_resources(db, topic, ["document", "ppt", "video"], limit=8)
    ]
    result = {
        "topic": topic,
        "requirement": requirement,
        "requested_types": requested_types,
        "lecture": _lecture(topic, requirement, references),
        "mind_map": _mind_map(topic),
        "exercises": _exercise_items(topic),
        "reading": _reading(topic, references),
        "videos": _video_items(db, topic),
        "code_examples": _code_items(topic, "python"),
        "datasets": _dataset_items(topic),
        "roadmap": {"topic": topic, "nodes": _roadmap_nodes(topic)},
        "reused_resources": references,
        "agent_traces": [
            {
                "agent": "需求分析Agent",
                "action": "解析主题、生成要求和资源类型",
                "output": f"主题为 {topic}，计划生成 {len(requested_types)} 类学习产物。",
            },
            {
                "agent": "资源生成Agent",
                "action": "生成讲解、思维导图、阅读材料并检索资源库",
                "output": f"复用资源库匹配项 {len(references)} 条，并完成结构化学习材料。",
            },
            {
                "agent": "练习题Agent",
                "action": "围绕核心概念生成分层练习",
                "output": f"已生成 {len(_exercise_items(topic))} 道选择与简答练习。",
            },
            {
                "agent": "代码案例Agent",
                "action": "生成安全、可阅读的最小代码案例",
                "output": "已生成 Python 最小案例，运行接口采用模拟执行模式。",
            },
            {
                "agent": "质量评估Agent",
                "action": "检查内容完整性、类型覆盖和链接可用字段",
                "output": "结果包含路线、讲解、练习、视频、代码和数据集，结构检查通过。",
            },
        ],
    }
    return result


def _artifact_rows(task_id: str, result: dict, requested_types: list[str]) -> list[ProducerArtifact]:
    artifacts = []
    mapping = {
        "lecture": ("lecture", result["lecture"]["title"], result["lecture"]["content"], ""),
        "mind_map": ("mind_map", result["mind_map"]["title"], result["mind_map"]["content"], ""),
        "exercise": (
            "exercise",
            f"{result['topic']} 练习题",
            json.dumps(result["exercises"], ensure_ascii=False),
            "",
        ),
        "reading": ("reading", result["reading"]["title"], result["reading"]["content"], ""),
        "roadmap": (
            "roadmap",
            f"{result['topic']} 学习路线图",
            json.dumps(result["roadmap"], ensure_ascii=False),
            "",
        ),
        "code": (
            "code",
            result["code_examples"][0]["title"],
            result["code_examples"][0]["code"],
            "",
        ),
        "video": (
            "video",
            result["videos"][0]["title"],
            result["videos"][0]["description"],
            result["videos"][0]["url"],
        ),
        "dataset": (
            "dataset",
            result["datasets"][0]["title"],
            result["datasets"][0]["description"],
            result["datasets"][0]["url"],
        ),
    }
    for requested_type in requested_types:
        artifact_data = mapping.get(requested_type)
        if artifact_data is None:
            continue
        artifact_type, title, content, url = artifact_data
        artifacts.append(
            ProducerArtifact(
                task_id=task_id,
                artifact_type=artifact_type,
                title=title,
                content=content,
                url=url,
                metadata_json={"topic": result["topic"], "source": "producer_multi_agent"},
            )
        )
    return artifacts


def _task_or_404(db: Session, task_id: str) -> ProducerTask:
    task = db.query(ProducerTask).filter(ProducerTask.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producer task not found")
    return task


@router.post("/task")
def create_task(
    payload: ProducerTaskRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(optional_user),
) -> dict:
    task_id = uuid4().hex
    topic = payload.topic.strip() or "通用学习主题"
    requested_types = _normalize_types(payload.types)
    task = ProducerTask(
        task_id=task_id,
        user_id=current_user.id if current_user else None,
        topic=topic,
        requirement=payload.requirement,
        task_type=payload.task_type,
        status="pending",
        progress=0,
    )
    db.add(task)
    db.commit()

    try:
        task.status = "running"
        task.progress = 10
        db.commit()
        result = _build_task_result(db, topic, payload.requirement, requested_types)
        db.add_all(_artifact_rows(task_id, result, requested_types))
        task.result_json = result
        task.status = "completed"
        task.progress = 100
        task.error_message = None
        db.commit()
    except Exception as exc:
        db.rollback()
        failed_task = _task_or_404(db, task_id)
        failed_task.status = "failed"
        failed_task.error_message = str(exc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Producer task failed") from exc

    return {
        "task_id": task_id,
        "status": task.status,
        "progress": task.progress,
        "message": "任务创建成功",
    }


@router.get("/task/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)) -> dict:
    task = _task_or_404(db, task_id)
    return {
        "task_id": task.task_id,
        "status": task.status,
        "progress": task.progress,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


@router.get("/result/{task_id}")
def get_task_result(task_id: str, db: Session = Depends(get_db)) -> dict:
    task = _task_or_404(db, task_id)
    return {
        "task_id": task.task_id,
        "status": task.status,
        "result": task.result_json or {},
    }


@router.post("/chat")
def producer_chat(payload: ProducerChatRequest, db: Session = Depends(get_db)) -> dict:
    session_id = payload.session_id or uuid4().hex
    message = payload.message.strip()
    reply = (
        f"{payload.topic} 可以从基础概念、核心原理、例题验证和代码实践四个层次理解。"
        f"针对“{message}”，建议先明确相关术语和输入输出，再用一个最小案例逐步验证。"
        "如果某一步无法解释原因，就把它记录为薄弱点，并配合练习题和路线图继续学习。"
    )
    db.add_all(
        [
            ProducerChatMessage(session_id=session_id, role="user", content=message),
            ProducerChatMessage(session_id=session_id, role="assistant", content=reply),
        ]
    )
    db.commit()
    return {"session_id": session_id, "reply": reply}


@router.get("/roadmap")
def get_roadmap(topic: str = Query(min_length=1, max_length=255)) -> dict:
    return {"topic": topic, "nodes": _roadmap_nodes(topic)}


@router.get("/exercises")
def get_exercises(topic: str = Query(min_length=1, max_length=255)) -> dict:
    return {"topic": topic, "items": _exercise_items(topic)}


@router.get("/videos")
def get_videos(
    topic: str = Query(min_length=1, max_length=255),
    db: Session = Depends(get_db),
) -> dict:
    return {"topic": topic, "items": _video_items(db, topic)}


@router.get("/code")
def get_code(
    topic: str = Query(min_length=1, max_length=255),
    language: str = Query(default="python", max_length=32),
) -> dict:
    return {"topic": topic, "language": language.lower(), "items": _code_items(topic, language)}


def _simulate_python_output(code: str) -> tuple[bool, str, str]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, "", f"语法检查失败：{exc.msg}"

    output_lines = []
    for node in tree.body:
        if not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "print"
        ):
            continue
        values = []
        for argument in node.value.args:
            try:
                values.append(str(ast.literal_eval(argument)))
            except (ValueError, TypeError):
                values.append("<表达式结果>")
        output_lines.append(" ".join(values))
    output = "\n".join(output_lines) or "模拟运行完成（安全模式未执行用户代码）"
    return True, output, ""


@router.post("/run")
def run_code(payload: ProducerRunRequest) -> dict:
    language = payload.language.lower()
    if language == "python":
        success, output, error = _simulate_python_output(payload.code)
    else:
        literal = re.search(r"console\.log\(\s*(['\"])(.*?)\1\s*\)", payload.code, re.DOTALL)
        success, output, error = True, literal.group(2) if literal else "模拟运行完成（安全模式未执行用户代码）", ""
    return {"success": success, "output": output, "error": error}


@router.get("/datasets")
def get_datasets(keyword: str = Query(min_length=1, max_length=255)) -> dict:
    return {"keyword": keyword, "items": _dataset_items(keyword)}
