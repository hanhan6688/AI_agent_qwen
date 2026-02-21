-- 初始化数据库脚本
-- 创建初始用户（明文密码）

-- 注意：Spring Boot的JPA会自动创建表结构（ddl-auto: update）
-- 这个脚本主要用于插入初始数据

-- 插入管理员用户（密码: admin123）
INSERT INTO users (username, password, email, document_count, created_at, updated_at)
VALUES ('admin', 'admin123', 'admin@example.com', 0, NOW(), NOW())
ON CONFLICT (username) DO NOTHING;

-- 插入测试用户（密码: test123）
INSERT INTO users (username, password, email, document_count, created_at, updated_at)
VALUES ('testuser', 'test123', 'test@example.com', 0, NOW(), NOW())
ON CONFLICT (username) DO NOTHING;

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at DESC);

-- 添加注释
COMMENT ON TABLE users IS '用户表';
COMMENT ON COLUMN users.user_id IS '用户ID';
COMMENT ON COLUMN users.username IS '用户名';
COMMENT ON COLUMN users.password IS '密码（明文存储，仅供本地开发测试使用）';
COMMENT ON COLUMN users.email IS '邮箱';
COMMENT ON COLUMN users.document_count IS '上传的文档数量';
COMMENT ON COLUMN users.created_at IS '创建时间';
COMMENT ON COLUMN users.updated_at IS '更新时间';

COMMENT ON TABLE tasks IS '任务表';
COMMENT ON COLUMN tasks.task_id IS '任务ID';
COMMENT ON COLUMN tasks.user_id IS '用户ID（外键）';
COMMENT ON COLUMN tasks.task_name IS '任务名称';
COMMENT ON COLUMN tasks.document_count IS '文档数量';
COMMENT ON COLUMN tasks.file_path IS '文件路径（JSON）';
COMMENT ON COLUMN tasks.status IS '任务状态（PENDING, PROCESSING, COMPLETED, FAILED）';
COMMENT ON COLUMN tasks.start_time IS '任务开始时间';
COMMENT ON COLUMN tasks.end_time IS '任务结束时间';
COMMENT ON COLUMN tasks.result IS '处理结果（JSON）';
COMMENT ON COLUMN tasks.extract_fields IS '提取字段配置（JSON）';
COMMENT ON COLUMN tasks.error_message IS '错误信息';
COMMENT ON COLUMN tasks.created_at IS '创建时间';
COMMENT ON COLUMN tasks.updated_at IS '更新时间';
