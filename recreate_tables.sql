-- 重新创建表结构（仅适用于开发环境，会丢失所有数据）
-- 执行前请确认这是开发环境且数据可以丢失

BEGIN;

-- 删除相关表（注意顺序，先删除有外键依赖的表）
DROP TABLE IF EXISTS task_logs CASCADE;
DROP TABLE IF EXISTS text_mappings CASCADE;
DROP TABLE IF EXISTS translation_results CASCADE;
DROP TABLE IF EXISTS tasks CASCADE;

-- 重新创建 tasks 表（使用正确的字段长度）
CREATE TABLE tasks (
    task_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_type VARCHAR(20) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'transcription_pending',
    languages JSON NOT NULL,
    audio_file_path TEXT,
    text_content TEXT,
    reference_text TEXT,
    accuracy DECIMAL(5,4),
    error_message TEXT,
    result_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- 重新创建其他表
CREATE TABLE translation_results (
    id SERIAL PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    target_language VARCHAR(10) NOT NULL,
    source_type VARCHAR(10) NOT NULL,
    source_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    confidence DECIMAL(5,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE text_mappings (
    text_id VARCHAR(50) PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    language VARCHAR(10) NOT NULL,
    source_type VARCHAR(10) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE task_logs (
    id SERIAL PRIMARY KEY,
    task_id UUID NOT NULL REFERENCES tasks(task_id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    message TEXT,
    details JSON,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_translation_results_task_id ON translation_results(task_id);
CREATE INDEX idx_text_mappings_task_id ON text_mappings(task_id);
CREATE INDEX idx_task_logs_task_id ON task_logs(task_id);

COMMIT;