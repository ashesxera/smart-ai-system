-- AI-3D 建模系统数据库 Schema v1.0
-- 创建时间: 2026-04-23

-- ============================================================
-- 1. sessions 表 - 用户会话表
-- ============================================================
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_uuid TEXT NOT NULL UNIQUE,
    channel_type TEXT NOT NULL DEFAULT 'feishu',
    channel_user_id TEXT NOT NULL,
    channel_user_name TEXT,
    group_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    phase TEXT NOT NULL DEFAULT 'collecting',
    material_summary TEXT,
    user_input TEXT,
    source_message_id TEXT,
    source_session_key TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    completed_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_sessions_uuid ON sessions(session_uuid);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(channel_type, channel_user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_group ON sessions(group_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status, phase);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);

-- ============================================================
-- 2. materials 表 - 材料表
-- ============================================================
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    material_uuid TEXT NOT NULL UNIQUE,
    session_uuid TEXT NOT NULL,
    material_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    text_content TEXT,
    image_urls TEXT,
    file_name TEXT,
    file_size INTEGER,
    file_mime_type TEXT,
    local_path TEXT,
    tos_path TEXT,
    generation_params TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (session_uuid) REFERENCES sessions(session_uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_materials_uuid ON materials(material_uuid);
CREATE INDEX IF NOT EXISTS idx_materials_session ON materials(session_uuid);
CREATE INDEX IF NOT EXISTS idx_materials_type ON materials(material_type);
CREATE INDEX IF NOT EXISTS idx_materials_status ON materials(status);

-- ============================================================
-- 3. vendor_tasks 表 - 供应商任务表
-- ============================================================
CREATE TABLE IF NOT EXISTS vendor_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vendor_task_uuid TEXT NOT NULL UNIQUE,
    session_uuid TEXT NOT NULL,
    material_uuid TEXT NOT NULL,
    vendor_id TEXT NOT NULL,
    vendor_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    vendor_task_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    status_message TEXT,
    api_endpoint TEXT,
    api_request_body TEXT,
    api_response TEXT,
    error_code TEXT,
    error_message TEXT,
    result_file_url TEXT,
    result_file_size INTEGER,
    local_result_path TEXT,
    tos_result_path TEXT,
    share_url TEXT,
    share_expires_at INTEGER,
    poll_count INTEGER DEFAULT 0,
    last_poll_at INTEGER,
    next_poll_at INTEGER,
    max_poll_count INTEGER DEFAULT 600,
    poll_interval_seconds INTEGER DEFAULT 30,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    submitted_at INTEGER,
    completed_at INTEGER,
    version INTEGER DEFAULT 0,
    FOREIGN KEY (session_uuid) REFERENCES sessions(session_uuid) ON DELETE CASCADE,
    FOREIGN KEY (material_uuid) REFERENCES materials(material_uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vendor_tasks_uuid ON vendor_tasks(vendor_task_uuid);
CREATE INDEX IF NOT EXISTS idx_vendor_tasks_session ON vendor_tasks(session_uuid);
CREATE INDEX IF NOT EXISTS idx_vendor_tasks_material ON vendor_tasks(material_uuid);
CREATE INDEX IF NOT EXISTS idx_vendor_tasks_vendor ON vendor_tasks(vendor_id);
CREATE INDEX IF NOT EXISTS idx_vendor_tasks_status ON vendor_tasks(status);
CREATE INDEX IF NOT EXISTS idx_vendor_tasks_next_poll ON vendor_tasks(next_poll_at);
CREATE INDEX IF NOT EXISTS idx_vendor_tasks_pending ON vendor_tasks(status, next_poll_at);

-- ============================================================
-- 4. results 表 - 结果表
-- ============================================================
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_uuid TEXT NOT NULL UNIQUE,
    vendor_task_uuid TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    file_format TEXT,
    tos_bucket TEXT NOT NULL DEFAULT '4-ark-claw',
    tos_path TEXT NOT NULL,
    share_url TEXT,
    share_expires_at INTEGER,
    polygon_count INTEGER,
    texture_resolution TEXT,
    has_alpha BOOLEAN DEFAULT 0,
    is_selected BOOLEAN DEFAULT 0,
    selected_at INTEGER,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (vendor_task_uuid) REFERENCES vendor_tasks(vendor_task_uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_results_uuid ON results(result_uuid);
CREATE INDEX IF NOT EXISTS idx_results_task ON results(vendor_task_uuid);
CREATE INDEX IF NOT EXISTS idx_results_selected ON results(is_selected);

-- ============================================================
-- 5. ops_log 表 - 操作日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS ops_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_uuid TEXT,
    vendor_task_uuid TEXT,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    detail TEXT,
    status TEXT NOT NULL DEFAULT 'success',
    duration_ms INTEGER,
    error_message TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_ops_log_session ON ops_log(session_uuid);
CREATE INDEX IF NOT EXISTS idx_ops_log_task ON ops_log(vendor_task_uuid);
CREATE INDEX IF NOT EXISTS idx_ops_log_action ON ops_log(action);
CREATE INDEX IF NOT EXISTS idx_ops_log_created ON ops_log(created_at DESC);

-- ============================================================
-- 6. settings 表 - 系统配置表
-- ============================================================
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    value_type TEXT DEFAULT 'string',
    description TEXT,
    category TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_settings_category ON settings(category);

-- ============================================================
-- 预设数据
-- ============================================================

-- 供应商配置
INSERT OR REPLACE INTO settings (key, value, value_type, description, category) VALUES
('vendor_ark_seed3d', '{"name":"豆包Seed3D","model":"doubao-seed3d","endpoint":"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks","query_endpoint":"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}","timeout_minutes":30,"max_poll_count":60,"poll_interval_seconds":20,"priority":10,"is_active":true,"supported_formats":["glb"],"max_images":1,"max_image_size_mb":10}', 'json', '火山引擎 Seed3D 供应商配置', 'vendor');

INSERT OR REPLACE INTO settings (key, value, value_type, description, category) VALUES
('vendor_ark_yingmou', '{"name":"影眸 Hyper3D","model":"YingMou","endpoint":"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks","query_endpoint":"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}","timeout_minutes":30,"max_poll_count":60,"poll_interval_seconds":20,"priority":8,"is_active":true,"supported_formats":["glb","obj","usdz","fbx","stl"],"max_images":5,"max_image_size_mb":30}', 'json', '影眸科技供应商配置', 'vendor');

INSERT OR REPLACE INTO settings (key, value, value_type, description, category) VALUES
('vendor_ark_shumei', '{"name":"数美 Hitem3D","model":"Shumei","endpoint":"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks","query_endpoint":"https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}","timeout_minutes":40,"max_poll_count":80,"poll_interval_seconds":30,"priority":6,"is_active":true,"supported_formats":["obj","glb","stl","fbx","usdz"],"max_images":4,"max_image_size_mb":10}', 'json', '数美科技供应商配置', 'vendor');

-- 轮询配置
INSERT OR REPLACE INTO settings (key, value, value_type, description, category) VALUES
('polling_interval_default', '20', 'int', '默认轮询间隔(秒)', 'polling'),
('polling_batch_size', '50', 'int', '每批轮询任务数', 'polling'),
('polling_max_retries', '3', 'int', 'API调用最大重试次数', 'polling');

-- TOS配置
INSERT OR REPLACE INTO settings (key, value, value_type, description, category) VALUES
('tos_bucket_name', '4-ark-claw', 'string', 'TOS存储桶名称', 'tos'),
('tos_base_path', 'ai-3d-system', 'string', 'TOS基础路径', 'tos'),
('tos_presign_expire_hours', '24', 'int', '分享链接有效期(小时)', 'tos');

-- 通知配置
INSERT OR REPLACE INTO settings (key, value, value_type, description, category) VALUES
('notification_enabled', 'true', 'bool', '是否启用通知', 'notification'),
('notification_retry_times', '3', 'int', '通知失败重试次数', 'notification'),
('gateway_webhook_url', 'http://127.0.0.1:18789/webhook/notify', 'string', 'Gateway Webhook通知地址', 'notification');

-- API配置
INSERT OR REPLACE INTO settings (key, value, value_type, description, category) VALUES
('ark_api_key', '', 'string', '火山引擎 API Key', 'api'),
('ark_base_url', 'https://ark.cn-beijing.volces.com/api/v3', 'string', 'API Base URL', 'api');
