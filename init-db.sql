-- 初始化数据库脚本

-- 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT true
    );

-- 创建任务表
CREATE TABLE IF NOT EXISTS tasks (
    task_id VARCHAR(100) PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    pdf_count INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result_path VARCHAR(500)
    );

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);

-- 创建提取结果表
CREATE TABLE IF NOT EXISTS extract_results (
    id BIGSERIAL PRIMARY KEY,
    task_id VARCHAR(100) REFERENCES tasks(task_id) ON DELETE CASCADE,
    result_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

CREATE INDEX IF NOT EXISTS idx_extract_results_task_id ON extract_results(task_id);

-- 插入默认管理员用户（密码: admin123，BCrypt加密后的值）
INSERT INTO users (username, password, email) VALUES
('admin', '$2a$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'admin@docextract.com')
ON CONFLICT (username) DO NOTHING;