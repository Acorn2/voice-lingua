-- 数据库迁移脚本：更新 tasks 表的 status 字段长度
-- 执行前请备份数据库

BEGIN;

-- 更新 status 字段长度从 VARCHAR(20) 到 VARCHAR(30)
ALTER TABLE tasks ALTER COLUMN status TYPE VARCHAR(30);

-- 验证更改
SELECT column_name, data_type, character_maximum_length 
FROM information_schema.columns 
WHERE table_name = 'tasks' AND column_name = 'status';

COMMIT;