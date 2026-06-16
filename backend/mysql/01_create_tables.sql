CREATE DATABASE IF NOT EXISTS learning_agent
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE learning_agent;

CREATE TABLE IF NOT EXISTS `user` (
  id INT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL,
  display_name VARCHAR(64),
  email VARCHAR(255) UNIQUE,
  password_hash VARCHAR(255),
  role VARCHAR(32) NOT NULL DEFAULT 'student',
  is_admin BOOLEAN NOT NULL DEFAULT FALSE,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS course (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(128) NOT NULL,
  description TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS knowledge_point (
  id INT PRIMARY KEY AUTO_INCREMENT,
  course_id INT NOT NULL,
  name VARCHAR(128) NOT NULL,
  description TEXT,
  parent_id INT NULL,
  difficulty VARCHAR(32) NOT NULL DEFAULT 'medium',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_kp_course FOREIGN KEY (course_id) REFERENCES course(id),
  CONSTRAINT fk_kp_parent FOREIGN KEY (parent_id) REFERENCES knowledge_point(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS course_resource (
  id INT PRIMARY KEY AUTO_INCREMENT,
  course_id INT NOT NULL,
  knowledge_point_id INT NULL,
  title VARCHAR(200) NOT NULL,
  resource_type VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  source VARCHAR(255),
  source_type VARCHAR(64) NULL,
  status VARCHAR(32) NULL DEFAULT 'published',
  version VARCHAR(32) NULL DEFAULT 'v1',
  metadata TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_course_resource_course FOREIGN KEY (course_id) REFERENCES course(id),
  CONSTRAINT fk_course_resource_kp FOREIGN KEY (knowledge_point_id) REFERENCES knowledge_point(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS resource_center (
  id INT PRIMARY KEY AUTO_INCREMENT,
  title VARCHAR(200) NOT NULL UNIQUE,
  description TEXT,
  resource_type VARCHAR(32) NOT NULL,
  category VARCHAR(128),
  content TEXT,
  url VARCHAR(1000),
  cover_url VARCHAR(1000),
  author VARCHAR(128),
  views INT NOT NULL DEFAULT 0,
  likes INT NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'published',
  open_type VARCHAR(32) NOT NULL DEFAULT 'content',
  knowledge_point VARCHAR(128),
  tags VARCHAR(255),
  difficulty VARCHAR(32),
  summary TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS student_profile (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  major VARCHAR(128),
  grade VARCHAR(64),
  course VARCHAR(128),
  goal TEXT,
  preference VARCHAR(128),
  cognitive_style VARCHAR(128),
  knowledge_level VARCHAR(64),
  raw_text TEXT NOT NULL,
  mastery TEXT NULL,
  weak_points_json TEXT NULL,
  engagement_score FLOAT,
  forgetting_risk FLOAT,
  learning_stage VARCHAR(64),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_profile_user FOREIGN KEY (user_id) REFERENCES `user`(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS profile_builder_session (
  id INT PRIMARY KEY AUTO_INCREMENT,
  session_id VARCHAR(64) NOT NULL UNIQUE,
  user_id INT NULL,
  current_step INT NOT NULL DEFAULT 1,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  result_profile_json JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_profile_builder_user FOREIGN KEY (user_id) REFERENCES `user`(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS profile_builder_message (
  id INT PRIMARY KEY AUTO_INCREMENT,
  session_id VARCHAR(64) NOT NULL,
  role VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_profile_builder_message_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS ml_profile_answer (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NULL,
  session_id VARCHAR(64) NOT NULL,
  question_id VARCHAR(128) NOT NULL,
  question TEXT,
  answer TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_ml_profile_answer_user FOREIGN KEY (user_id) REFERENCES `user`(id),
  INDEX idx_ml_profile_answer_session (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS producer_task (
  id INT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL UNIQUE,
  user_id INT NULL,
  topic VARCHAR(255) NOT NULL,
  requirement TEXT,
  task_type VARCHAR(64) NOT NULL DEFAULT 'multi_agent_generation',
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  progress INT NOT NULL DEFAULT 0,
  result_json JSON,
  error_message TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_producer_task_user FOREIGN KEY (user_id) REFERENCES `user`(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS producer_artifact (
  id INT PRIMARY KEY AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL,
  artifact_type VARCHAR(64) NOT NULL,
  title VARCHAR(255) NOT NULL,
  content TEXT,
  url VARCHAR(512),
  metadata_json JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_producer_artifact_task_id (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS producer_chat_message (
  id INT PRIMARY KEY AUTO_INCREMENT,
  session_id VARCHAR(64) NOT NULL,
  role VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_producer_chat_session_id (session_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS student_weakness (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  profile_id INT NULL,
  knowledge_point VARCHAR(128) NOT NULL,
  weakness_level FLOAT NOT NULL DEFAULT 0.7,
  evidence TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_weakness_user FOREIGN KEY (user_id) REFERENCES `user`(id),
  CONSTRAINT fk_weakness_profile FOREIGN KEY (profile_id) REFERENCES student_profile(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS learning_resource (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  course_id INT NULL,
  title VARCHAR(200) NOT NULL,
  resource_type VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  review_status VARCHAR(32) NOT NULL DEFAULT 'approved',
  review_notes TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_learning_resource_user FOREIGN KEY (user_id) REFERENCES `user`(id),
  CONSTRAINT fk_learning_resource_course FOREIGN KEY (course_id) REFERENCES course(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS learning_path (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  course_id INT NULL,
  title VARCHAR(200) NOT NULL,
  goal TEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  progress FLOAT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_learning_path_user FOREIGN KEY (user_id) REFERENCES `user`(id),
  CONSTRAINT fk_learning_path_course FOREIGN KEY (course_id) REFERENCES course(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS learning_path_node (
  id INT PRIMARY KEY AUTO_INCREMENT,
  path_id INT NOT NULL,
  resource_id INT NULL,
  step_order INT NOT NULL,
  title VARCHAR(200) NOT NULL,
  objective TEXT NOT NULL,
  description TEXT NULL,
  level VARCHAR(64) NULL,
  estimated_minutes INT NOT NULL DEFAULT 30,
  status VARCHAR(32) NOT NULL DEFAULT 'not_started',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_path_node_path FOREIGN KEY (path_id) REFERENCES learning_path(id),
  CONSTRAINT fk_path_node_resource FOREIGN KEY (resource_id) REFERENCES learning_resource(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS path_node_progress (
  id INT PRIMARY KEY AUTO_INCREMENT,
  path_id INT NOT NULL,
  node_id INT NOT NULL,
  user_id INT NULL,
  completed BOOLEAN NOT NULL DEFAULT FALSE,
  status VARCHAR(32) NOT NULL DEFAULT 'not_started',
  completed_at DATETIME NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_path_progress_path FOREIGN KEY (path_id) REFERENCES learning_path(id),
  CONSTRAINT fk_path_progress_node FOREIGN KEY (node_id) REFERENCES learning_path_node(id),
  CONSTRAINT fk_path_progress_user FOREIGN KEY (user_id) REFERENCES `user`(id),
  UNIQUE KEY uk_path_node_progress (path_id, node_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS path_feedback (
  id INT PRIMARY KEY AUTO_INCREMENT,
  path_id INT NOT NULL,
  user_id INT NULL,
  rating INT NOT NULL,
  comment TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_path_feedback_path FOREIGN KEY (path_id) REFERENCES learning_path(id),
  CONSTRAINT fk_path_feedback_user FOREIGN KEY (user_id) REFERENCES `user`(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS evaluation_result (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  path_id INT NULL,
  mastery_score FLOAT NOT NULL,
  feedback TEXT NOT NULL,
  profile_update JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_evaluation_user FOREIGN KEY (user_id) REFERENCES `user`(id),
  CONSTRAINT fk_evaluation_path FOREIGN KEY (path_id) REFERENCES learning_path(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_message (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  role VARCHAR(32) NOT NULL,
  content TEXT NOT NULL,
  agent_name VARCHAR(64),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_chat_user FOREIGN KEY (user_id) REFERENCES `user`(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS import_job (
  id INT PRIMARY KEY AUTO_INCREMENT,
  course_id INT NOT NULL,
  user_id INT NOT NULL,
  source_type VARCHAR(32) NOT NULL,
  filename VARCHAR(255) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  message TEXT,
  result JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_import_job_course FOREIGN KEY (course_id) REFERENCES course(id),
  CONSTRAINT fk_import_job_user FOREIGN KEY (user_id) REFERENCES `user`(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS resource_chunk (
  id INT PRIMARY KEY AUTO_INCREMENT,
  resource_id INT NOT NULL,
  course_id INT NOT NULL,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  token_count INT NOT NULL DEFAULT 0,
  embedding JSON,
  keywords JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_resource_chunk_resource FOREIGN KEY (resource_id) REFERENCES course_resource(id),
  CONSTRAINT fk_resource_chunk_course FOREIGN KEY (course_id) REFERENCES course(id),
  INDEX idx_resource_chunk_course (course_id),
  FULLTEXT INDEX ft_resource_chunk_content (content)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS question (
  id INT PRIMARY KEY AUTO_INCREMENT,
  course_id INT NOT NULL,
  knowledge_point_id INT NULL,
  question_type VARCHAR(32) NOT NULL DEFAULT 'short_answer',
  stem TEXT NOT NULL,
  answer TEXT,
  explanation TEXT,
  difficulty FLOAT NOT NULL DEFAULT 0.5,
  source VARCHAR(255),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_question_course FOREIGN KEY (course_id) REFERENCES course(id),
  CONSTRAINT fk_question_kp FOREIGN KEY (knowledge_point_id) REFERENCES knowledge_point(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS student_answer (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  course_id INT NULL,
  question_id INT NULL,
  knowledge_point VARCHAR(128),
  answer TEXT,
  score FLOAT,
  correct BOOLEAN,
  elapsed_seconds INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_student_answer_user FOREIGN KEY (user_id) REFERENCES `user`(id),
  CONSTRAINT fk_student_answer_course FOREIGN KEY (course_id) REFERENCES course(id),
  CONSTRAINT fk_student_answer_question FOREIGN KEY (question_id) REFERENCES question(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS feedback_event (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  course_id INT NULL,
  resource_id INT NULL,
  path_id INT NULL,
  knowledge_points JSON,
  score FLOAT,
  completed BOOLEAN NOT NULL DEFAULT FALSE,
  dwell_seconds INT NOT NULL DEFAULT 0,
  liked BOOLEAN,
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_feedback_event_user FOREIGN KEY (user_id) REFERENCES `user`(id),
  CONSTRAINT fk_feedback_event_course FOREIGN KEY (course_id) REFERENCES course(id),
  CONSTRAINT fk_feedback_event_resource FOREIGN KEY (resource_id) REFERENCES learning_resource(id),
  CONSTRAINT fk_feedback_event_path FOREIGN KEY (path_id) REFERENCES learning_path(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
