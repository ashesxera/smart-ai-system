# AI-3D 建模系统 - 数据库初始化脚本

## 文档信息
- 版本：v1.0.0
- 创建时间：2026-04-23
- 说明：初始化数据库表结构和供应商配置

---

## 1. 建表语句

```sql
-- ============================================
-- AI-3D 建模系统 数据库 Schema
-- ============================================

-- 会话表
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_uuid TEXT NOT NULL UNIQUE,
    channel_type TEXT NOT NULL DEFAULT 'feishu',
    channel_user_id TEXT NOT NULL,
    channel_user_name TEXT,
    group_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    phase TEXT NOT NULL DEFAULT 'pending',
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
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status, phase);

-- 材料表
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

-- 供应商任务表
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
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    submitted_at INTEGER,
    completed_at INTEGER,
    FOREIGN KEY (session_uuid) REFERENCES sessions(session_uuid) ON DELETE CASCADE,
    FOREIGN KEY (material_uuid) REFERENCES materials(material_uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_vendor_tasks_uuid ON vendor_tasks(vendor_task_uuid);
CREATE INDEX IF NOT EXISTS idx_vendor_tasks_session ON vendor_tasks(session_uuid);
CREATE INDEX IF NOT EXISTS idx_vendor_tasks_status ON vendor_tasks(status);

-- 结果表
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
    has_alpha INTEGER DEFAULT 0,
    is_selected INTEGER DEFAULT 0,
    selected_at INTEGER,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    FOREIGN KEY (vendor_task_uuid) REFERENCES vendor_tasks(vendor_task_uuid) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_results_uuid ON results(result_uuid);
CREATE INDEX IF NOT EXISTS idx_results_task ON results(vendor_task_uuid);

-- 操作日志表
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

-- 设置表（供应商配置等）
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
```

---

## 2. 供应商配置初始化

### 2.1 火山引擎 Seed3D

```sql
INSERT INTO settings (key, value, value_type, description, category) VALUES
('vendor_ark_seed3d', '{
  "id": "vendor_ark_seed3d",
  "name": "豆包Seed3D",
  "model": "doubao-seed3d",
  "adapter": "ark_generic",
  "endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
  "query_endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/${vendor_task_id}",
  "method": "POST",
  "auth_type": "bearer",
  "timeout_minutes": 30,
  "priority": 10,
  "is_active": true,
  "supported_formats": ["glb"],
  "max_images": 1,
  "max_image_size_mb": 10,
  "request_template": {
    "model": "${model}",
    "content": ${content}
  },
  "content_template": [
    {"type": "image_url", "image_url": {"url": "${image_url_0}"}}
  ],
  "response_parser": {
    "task_id": "$.id",
    "status": "$.status",
    "file_url": "$.content.file_url"
  },
  "status_map": {
    "queued": "queued",
    "running": "running",
    "succeeded": "succeeded",
    "failed": "failed"
  }
}', 'json', '火山引擎 Seed3D - 多视角3D生成模型', 'vendor');
```

### 2.2 影眸科技 Hyper3D

```sql
INSERT INTO settings (key, value, value_type, description, category) VALUES
('vendor_ark_yingmou', '{
  "id": "vendor_ark_yingmou",
  "name": "影眸 Hyper3D",
  "model": "YingMou",
  "adapter": "ark_generic",
  "endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
  "query_endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/${vendor_task_id}",
  "method": "POST",
  "auth_type": "bearer",
  "timeout_minutes": 30,
  "priority": 8,
  "is_active": true,
  "supported_formats": ["glb", "obj", "usdz", "fbx", "stl"],
  "max_images": 5,
  "max_image_size_mb": 30,
  "request_template": {
    "model": "${model}",
    "content": ${content}
  },
  "content_template": [
    {"type": "image_url", "image_url": {"url": "${image_url_0}"}}
  ],
  "response_parser": {
    "task_id": "$.id",
    "status": "$.status",
    "file_url": "$.content.file_url"
  },
  "status_map": {
    "queued": "queued",
    "running": "running",
    "succeeded": "succeeded",
    "failed": "failed"
  }
}', 'json', '影眸科技 Hyper3D - 高精度人像3D模型', 'vendor');
```

### 2.3 数美科技 Hitem3D

```sql
INSERT INTO settings (key, value, value_type, description, category) VALUES
('vendor_ark_shumei', '{
  "id": "vendor_ark_shumei",
  "name": "数美 Hitem3D",
  "model": "Shumei",
  "adapter": "ark_generic",
  "endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
  "query_endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/${vendor_task_id}",
  "method": "POST",
  "auth_type": "bearer",
  "timeout_minutes": 40,
  "priority": 6,
  "is_active": true,
  "supported_formats": ["obj", "glb", "stl", "fbx", "usdz"],
  "max_images": 4,
  "max_image_size_mb": 10,
  "request_template": {
    "model": "${model}",
    "content": ${content}
  },
  "content_template": [
    {"type": "image_url", "image_url": {"url": "${image_url_0}"}}
  ],
  "response_parser": {
    "task_id": "$.id",
    "status": "$.status",
    "file_url": "$.content.file_url"
  },
  "status_map": {
    "queued": "queued",
    "running": "running",
    "succeeded": "succeeded",
    "failed": "failed"
  }
}', 'json', '数美科技 Hitem3D - 通用3D生成模型', 'vendor');
```

---

## 3. 系统配置初始化

```sql
-- 系统配置
INSERT INTO settings (key, value, value_type, description, category) VALUES
('system.tos_bucket', '4-ark-claw', 'string', 'TOS存储桶名称', 'system');

INSERT INTO settings (key, value, value_type, description, category) VALUES
('system.tos_base_path', 'ai-3d-system', 'string', 'TOS基础路径', 'system');

INSERT INTO settings (key, value, value_type, description, category) VALUES
('system.polling_interval', '60', 'integer', '轮询间隔秒数', 'system');

INSERT INTO settings (key, value, value_type, description, category) VALUES
('system.share_url_expire', '86400', 'integer', '分享链接过期秒数(24小时)', 'system');

INSERT INTO settings (key, value, value_type, description, category) VALUES
('system.max_retries', '3', 'integer', '最大重试次数', 'system');

INSERT INTO settings (key, value, value_type, description, category) VALUES
('system.api_timeout', '30', 'integer', 'API超时秒数', 'system');
```

---

## 4. Python 初始化脚本

```python
"""
数据库初始化脚本

用法：
    python -m ai_3d_modeling.db.init
"""

import sys
import os

# 添加 src 目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai_3d_modeling.db import Database


def initialize_database(db_path: str = 'ai-3d-modeling.db'):
    """初始化数据库"""
    print(f"Initializing database: {db_path}")
    
    db = Database(db_path)
    db.initialize()
    
    print("Database initialized successfully!")


if __name__ == '__main__':
    initialize_database()
```

---

## 5. 验证查询

```sql
-- 验证表已创建
SELECT name FROM sqlite_master WHERE type='table';

-- 验证供应商配置
SELECT key, description FROM settings WHERE category = 'vendor';

-- 验证系统配置
SELECT key, value FROM settings WHERE category = 'system';
```
