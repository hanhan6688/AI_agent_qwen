-- 数据库更新脚本 - 添加 pdf_count 字段
-- 执行此脚本前，请确保已备份数据库

-- 检查并添加 pdf_count 字段到 tasks 表
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'tasks' AND column_name = 'pdf_count'
    ) THEN
        ALTER TABLE tasks ADD COLUMN pdf_count INTEGER DEFAULT 0;
        RAISE NOTICE 'pdf_count 字段已成功添加';
    ELSE
        RAISE NOTICE 'pdf_count 字段已存在';
    END IF;
END $$;

-- 更新现有记录的 pdf_count 值为 1（假设每个任务对应一个PDF文件）
UPDATE tasks SET pdf_count = 1 WHERE pdf_count IS NULL;

-- 验证更新结果
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'tasks' AND column_name = 'pdf_count';

-- 查看前 10 条记录的 pdf_count 值
SELECT task_id, file_name, pdf_count FROM tasks LIMIT 10;
