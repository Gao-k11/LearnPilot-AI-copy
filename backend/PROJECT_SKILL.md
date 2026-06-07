# 软件杯A3项目后端开发Skill

## 项目背景

项目名称：

基于大模型的个性化资源生成与学习多智能体系统开发

比赛：

中国软件杯 A3 赛题

本人负责：

Python 后端开发

前端接口协议暂未确定。

机器学习同学后续会提供模型能力。

当前目标：

先实现完整可运行后端框架。

后续方便接入前端和机器学习模块。

---

# 技术栈

后端：

Python 3.12

框架：

FastAPI

数据库：

MySQL

数据库名称：

learning_agent

已经创建：

CREATE DATABASE learning_agent
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

---

# 项目目录

D:\software_competitive

项目根目录：

D:\software_competitive

需要自动创建：

backend
mysql
data
generated
docs

---

# 系统核心功能

必须实现：

1. 对话式学习画像构建

2. 多智能体资源生成

3. 个性化学习路径规划

4. 智能辅导

5. 学习效果评估

6. 防幻觉审核

---

# 业务流程

学生输入学习需求

↓

ProfileAgent

分析学生画像

↓

DiagnosisAgent

分析薄弱知识点

↓

RetrieverAgent

查询课程知识库

↓

ResourceAgent

生成学习资源

↓

ReviewAgent

审核内容

↓

PlannerAgent

生成学习路径

↓

TutorAgent

智能辅导

↓

EvaluatorAgent

学习效果评估

↓

更新学生画像

---

# 学习画像模块

输入：

自然语言

例如：

我是软件工程大二学生

正在学习人工智能

CNN比较薄弱

目标是准备期末考试

输出：

{
  major,
  grade,
  course,
  goal,
  weak_points,
  preference,
  cognitive_style,
  knowledge_level
}

---

# 多模态资源模块

必须支持：

1. 讲义

2. 思维导图

3. 练习题

4. 拓展阅读

5. 代码案例

6. 视频脚本

---

# 学习路径模块

根据：

学习目标

薄弱知识点

课程知识结构

自动生成学习步骤

并绑定资源

---

# 智能辅导模块

学生提问

结合：

学生画像

课程资源

历史记录

生成回答

采用：

苏格拉底式引导

---

# 学习效果评估模块

根据：

答题结果

资源完成情况

学习时长

生成：

掌握度评分

并更新画像

---

# 防幻觉模块

审核：

内容长度

敏感词

知识库相关性

引用来源

不通过则重新生成

---

# 数据库表

必须生成建表脚本

user

course

knowledge_point

course_resource

student_profile

student_weakness

learning_resource

learning_path

learning_path_node

evaluation_result

chat_message

---

# Agent设计

ProfileAgent

DiagnosisAgent

RetrieverAgent

ResourceAgent

PlannerAgent

TutorAgent

EvaluatorAgent

ReviewAgent

---

# 机器学习接口预留

统一放入：

adapters/ml_adapter.py

先使用Mock实现

后续替换真实模型

---

# 大模型接口预留

统一放入：

adapters/llm_adapter.py

先使用Mock实现

后续替换真实API

---

# 需要Codex自动生成

1. FastAPI项目

2. requirements.txt

3. .env.example

4. README.md

5. docs/API.md

6. mysql/01_create_tables.sql

7. mysql/02_insert_init_data.sql

8. 所有目录结构

9. Swagger可测试接口

要求：

项目生成后能够直接运行

uvicorn启动成功

Swagger页面正常访问

数据库连接正常