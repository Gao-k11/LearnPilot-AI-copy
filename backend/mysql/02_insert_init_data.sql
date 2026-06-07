SET NAMES utf8mb4;
USE learning_agent;

INSERT INTO `user` (id, username, display_name, role)
VALUES (1, 'demo_student', '演示学生', 'student')
ON DUPLICATE KEY UPDATE
  username = VALUES(username),
  display_name = VALUES(display_name),
  role = VALUES(role);

INSERT INTO course (id, name, description)
VALUES
  (1, '人工智能', '人工智能课程包含机器学习、神经网络、CNN等内容'),
  (2, '机器学习', '机器学习课程包含监督学习、无监督学习、模型评估等内容')
ON DUPLICATE KEY UPDATE
  name = VALUES(name),
  description = VALUES(description);

INSERT INTO knowledge_point (id, course_id, name, description, parent_id, difficulty)
VALUES
  (1, 1, 'CNN', '卷积神经网络，包含卷积、池化、特征图和图像分类等核心内容。', NULL, 'hard'),
  (2, 1, '反向传播', '神经网络训练中的梯度计算方法，用于根据损失函数更新模型参数。', NULL, 'hard'),
  (3, 2, '决策树', '基于特征划分构建树形分类或回归模型，具有较强可解释性。', NULL, 'medium'),
  (4, 2, '支持向量机', '通过最大化分类间隔寻找最优超平面的监督学习算法。', NULL, 'hard'),
  (5, 2, '聚类算法', '无监督学习方法，用于根据样本相似度自动发现数据中的群组结构。', NULL, 'medium')
ON DUPLICATE KEY UPDATE
  course_id = VALUES(course_id),
  name = VALUES(name),
  description = VALUES(description),
  parent_id = VALUES(parent_id),
  difficulty = VALUES(difficulty);

INSERT INTO course_resource (id, course_id, knowledge_point_id, title, resource_type, content, source)
VALUES
  (
    1,
    1,
    1,
    'CNN 讲义',
    'lecture',
    '本讲义介绍 CNN 的基本结构，包括卷积层、池化层、激活函数和全连接层，并说明 CNN 如何从图像中提取局部特征。',
    'init_data'
  ),
  (
    2,
    1,
    1,
    'CNN 练习题',
    'exercise',
    '练习内容包括计算卷积输出尺寸、解释池化作用、分析卷积核数量与特征图通道数之间的关系。',
    'init_data'
  ),
  (
    3,
    1,
    2,
    '反向传播讲义',
    'lecture',
    '本讲义讲解反向传播的链式法则、梯度计算流程，以及学习率对神经网络训练效果的影响。',
    'init_data'
  ),
  (
    4,
    2,
    3,
    '决策树案例',
    'code_example',
    '通过一个学生成绩预测案例演示决策树建模流程，包括特征选择、树结构生成、预测结果解释和过拟合控制。',
    'init_data'
  ),
  (
    5,
    2,
    NULL,
    '机器学习拓展阅读',
    'reading',
    '拓展阅读覆盖监督学习、无监督学习、模型评估、泛化能力、交叉验证和常见机器学习应用场景。',
    'init_data'
  )
ON DUPLICATE KEY UPDATE
  course_id = VALUES(course_id),
  knowledge_point_id = VALUES(knowledge_point_id),
  title = VALUES(title),
  resource_type = VALUES(resource_type),
  content = VALUES(content),
  source = VALUES(source);
