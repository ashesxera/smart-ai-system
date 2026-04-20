# Smart AI 任务系统数据库设计方案

## 文档信息
- 版本：v1.1
- 创建时间：2026-04-20
- 更新时间：2026-04-20 17:53
- 目标系统：通用异步AI任务系统
- 数据库类型：SQLite 3

---

## 1. 设计背景

本数据库设计服务于**通用异步AI任务系统**，支持通过飞书对话提交各类异步AI生成任务（3D建模、音频生成、视频生成等）。

### 设计目标

| 目标 | 说明 |
|------|------|
| 通用性 | 支持多种AI任务类型（3D/音频/视频） |
| 可扩展性 | 新增任务类型只需配置，无需改表结构 |
| 可追溯性 | 完整记录素材、成品、操作过程 |
| 可靠性 | 并发安全、完整日志、支持重试 |

---

## 2. 支持的任务类型

| 任务类型 | task_type | 示例API |
|----------|-----------|---------|
| 3D建模 | 3d_model | Meshy.AI、火山引擎（豆包/影眸/数美）、Tripo3D |
| 音频生成 | audio | TTS、语音合成 |
| 视频生成 | video | 视频生成、AI剪辑 |

---

## 3. 数据库表结构

### 3.1 tasks（任务主表）

**用途**：存储所有AI任务的核心信息

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 任务标识
    task_id TEXT NOT NULL UNIQUE,              -- 系统生成的任务ID
    
    -- 任务类型（区分不同AI任务）
    task_type TEXT NOT NULL,                   -- 3d_model / audio / video
    
    -- API信息（多对一关系：一个task属于一个API）
    provider TEXT NOT NULL,                    -- API提供商标识
    api_task_id TEXT,                          -- API返回的原始任务ID
    api_id TEXT NOT NULL,                      -- 关联的API配置ID
    
    -- 提交者信息
    submitter_id TEXT NOT NULL,                 -- 飞书用户ID
    submitter_name TEXT,                       -- 提交者姓名
    submitter_user_name TEXT,                  -- 飞书昵称（冗余存储，便于显示）
    notify_chat_id TEXT NOT NULL,               -- 飞书群聊ID（用于通知）
    
    -- 任务状态
    status TEXT NOT NULL DEFAULT 'pending',     -- pending/queued/running/succeeded/failed/cancelled/error/timeout
    status_message TEXT,                        -- 状态描述/错误信息
    
    -- 错误信息
    error_code TEXT,                            -- 错误码
    error_message TEXT,                         -- 错误信息
    
    -- API请求/响应（调试用）
    api_request_body TEXT,                      -- 完整API请求JSON
    api_response TEXT,                          -- API响应JSON
    
    -- 最终成品分享链接（冗余存储，便于快速获取）
    output_share_url TEXT,                     -- 成品分享链接
    
    -- 计费信息
    token_usage TEXT,                          -- token消耗（JSON）
    estimated_cost TEXT,                       -- 预估花费
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    completed_at INTEGER,                      -- 完成/失败时间
    
    -- 轮询相关（通用轮询配置）
    poll_count INTEGER DEFAULT 0,               -- 轮询次数
    last_poll_at INTEGER,                       -- 最后轮询时间
    max_poll_count INTEGER DEFAULT 600,         -- 最大轮询次数
    
    -- 并发控制
    version INTEGER DEFAULT 0,                 -- 乐观锁版本号
    
    -- 元数据（扩展字段）
    metadata TEXT                               -- JSON格式的扩展数据
);

-- 索引
CREATE INDEX idx_tasks_task_id ON tasks(task_id);
CREATE INDEX idx_tasks_api_task_id ON tasks(api_task_id);
CREATE INDEX idx_tasks_type ON tasks(task_type);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_submitter ON tasks(submitter_id);
CREATE INDEX idx_tasks_provider ON tasks(provider);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);
CREATE INDEX idx_tasks_type_status ON tasks(task_type, status);
CREATE INDEX idx_tasks_status_created ON tasks(status, created_at DESC);
```

**字段说明**：
- `task_id`：系统生成的任务唯一标识（UUID格式）
- `task_type`：任务类型（3d_model/audio/video），用于区分不同AI任务
- `api_task_id`：API返回的原始任务ID，用于查询状态
- `output_format`：输出格式（glb/stl/obj/mp3/mp4/wav等）
- `metadata`：JSON格式，存储任务特定的扩展参数

---

### 3.2 resources（资源表）

**用途**：存储任务提交的资源信息（素材/输入/输出），支持多种资源类型

```sql
CREATE TABLE resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,                      -- 关联的任务ID
    
    -- 资源类型（输入/输出）
    resource_type TEXT NOT NULL,                 -- input / output
    
    -- 资源内容类型
    content_type TEXT NOT NULL,                  -- image / text / audio / video / model / other
    
    -- 来源类型
    source_type TEXT NOT NULL,                   -- feishu_file / url / base64 / text / api_response
    
    -- 飞书文件信息（输入为飞书文件时）
    file_key TEXT,                               -- 飞书file_key
    file_name TEXT,                              -- 原始文件名
    file_size INTEGER,                           -- 文件大小（字节）
    file_mime_type TEXT,                         -- MIME类型
    
    -- URL信息
    source_url TEXT,                             -- 公开URL
    
    -- 文本内容（文生3D/文生音频时）
    text_content TEXT,                            -- 文本提示词
    
    -- 多视图/多片段标记
    multi_content_bit TEXT,                       -- 位图标记
    content_list TEXT,                           -- 内容列表（JSON数组）
    
    -- 存储信息
    tos_path TEXT NOT NULL,                      -- TOS存储路径
    local_tmp_path TEXT,                         -- 本地临时路径
    
    -- 输出成品信息（output类型使用）
    output_format TEXT,                          -- 输出格式：glb/stl/mp3/mp4等
    output_size INTEGER,                         -- 成品文件大小
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    
    -- 外键约束
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

-- 索引
CREATE INDEX idx_resources_task_id ON resources(task_id);
CREATE INDEX idx_resources_type ON resources(resource_type);
CREATE INDEX idx_resources_content_type ON resources(content_type);
CREATE INDEX idx_resources_source_type ON resources(source_type);
```

**字段说明**：
- `resource_type`：资源类型
  - `input`：输入素材
  - `output`：输出成品
- `content_type`：内容类型
  - `image`：图片（单图/多图）
  - `text`：文本描述
  - `audio`：音频文件
  - `video`：视频文件
  - `model`：3D模型文件
  - `other`：其他
- `source_type`：图片来源
  - `feishu_file`：飞书文件
  - `url`：公开URL
  - `base64`：Base64编码
  - `text`：纯文本
  - `api_response`：API返回

---

### 3.3 operations（操作日志表）

**用途**：记录所有关键操作和通知，用于审计、问题排查

```sql
CREATE TABLE operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT,                                -- 关联的任务ID（可选）
    
    -- 操作类型
    operation_type TEXT NOT NULL,                -- 操作类型
    operation_detail TEXT,                        -- 操作详情（JSON或文本）
    
    -- 操作结果
    status TEXT NOT NULL,                         -- success / failed / pending
    
    -- 错误信息
    error_message TEXT,                          -- 错误信息
    
    -- 性能指标
    duration_ms INTEGER,                         -- 操作耗时（毫秒）
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    
    -- 操作者
    operator TEXT,                               -- system / user_xxx / poller
    
    -- 外键约束
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE SET NULL
);

-- 索引
CREATE INDEX idx_operations_task_id ON operations(task_id);
CREATE INDEX idx_operations_type ON operations(operation_type);
CREATE INDEX idx_operations_created ON operations(created_at DESC);
CREATE INDEX idx_operations_task_created ON operations(task_id, created_at DESC);
```

**操作类型枚举**：

| 类型 | 说明 | 归属 |
|------|------|------|
| task_created | 任务创建 | 通用 |
| parameter_parsed | 参数解析完成 | 通用 |
| api_submit | 提交到API | 通用 |
| api_poll | API轮询状态 | 通用 |
| tos_upload_input | 上传输入素材 | 通用 |
| tos_upload_output | 上传输出成品 | 通用 |
| result_download | 下载结果文件 | 通用 |
| notification_sent | 发送通知 | 通用 |
| notification_failed | 通知发送失败 | 通用 |
| task_completed | 任务完成 | 通用 |
| task_failed | 任务失败 | 通用 |
| task_timeout | 任务超时 | 通用 |
| cleanup_tmp | 清理临时文件 | 通用 |

**说明**：通知记录也写入此表（如 notification_sent），不再单独建表。

---

### 3.4 settings（系统配置表）

**用途**：存储系统级配置参数

```sql
CREATE TABLE settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,                    -- 配置键
    value TEXT NOT NULL,                          -- 配置值
    value_type TEXT DEFAULT 'string',            -- string / int / bool / json
    description TEXT,                            -- 配置说明
    category TEXT,                               -- 配置分类
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- 索引
CREATE INDEX idx_settings_category ON settings(category);
```

**预设配置数据**：

```sql
-- 轮询配置
INSERT INTO settings (key, value, value_type, description, category) VALUES
('polling_interval_seconds', '30', 'int', '轮询间隔（秒）', 'polling'),
('max_poll_count', '600', 'int', '最大轮询次数', 'polling');

-- TOS配置
INSERT INTO settings (key, value, value_type, description, category) VALUES
('tos_bucket_name', '4-ark-claw', 'string', 'TOS存储桶名称', 'tos'),
('tos_input_prefix', 'smart-ai-input', 'string', 'TOS输入路径前缀', 'tos'),
('tos_output_prefix', 'smart-ai-output', 'string', 'TOS输出路径前缀', 'tos'),
('tmp_cleanup_hours', '1', 'int', '临时文件清理时间（小时）', 'tos');

-- 通知配置
INSERT INTO settings (key, value, value_type, description, category) VALUES
('notification_retry_times', '3', 'int', '通知失败重试次数', 'notification'),
('notification_on_success', 'true', 'bool', '成功时是否通知', 'notification'),
('notification_on_failure', 'true', 'bool', '失败时是否通知', 'notification');

-- API通用配置
INSERT INTO settings (key, value, value_type, description, category) VALUES
('api_timeout_seconds', '60', 'int', 'API调用超时时间（秒）', 'api');
```

---

### 3.5 resources_tasks（资源-任务关联表）

**用途**：实现resources与tasks的多对多关系，一套素材可提交给多个API产生多个task

```sql
CREATE TABLE resources_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL,                -- 关联的资源ID
    task_id TEXT NOT NULL,                     -- 关联的任务ID
    
    -- 关联顺序
    bind_order INTEGER DEFAULT 1,               -- 绑定顺序
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    
    -- 外键约束
    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    
    -- 唯一约束：防止重复关联
    UNIQUE(resource_id, task_id)
);

-- 索引
CREATE INDEX idx_rt_resource_id ON resources_tasks(resource_id);
CREATE INDEX idx_rt_task_id ON resources_tasks(task_id);
```

**使用场景**：
- 一套素材提交给多个API（如同时提交给Meshy和Tripo3D）
- 一个task可以关联多个resource（多视图素材）

**使用场景**：
- 单API任务：只关联一个API
- 组合API任务：先调用API1生成中间结果，再调用API2优化

---

### 3.6 apis（API配置表）

**用途**：管理支持的AI API配置（原models表改名并通用化）

```sql
CREATE TABLE apis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- API标识
    api_id TEXT NOT NULL UNIQUE,                 -- API唯一标识
    provider TEXT NOT NULL,                       -- 提供商名称
    
    -- 任务类型（新增）
    task_type TEXT NOT NULL,                     -- 3d_model / audio / video
    
    -- API信息
    api_name TEXT NOT NULL,                      -- API显示名称
    api_version TEXT,                           -- API版本
    
    -- 端点配置
    endpoint_submit TEXT NOT NULL,               -- 任务提交端点
    endpoint_query TEXT,                         -- 任务查询端点
    endpoint_cancel TEXT,                        -- 任务取消端点
    
    -- 认证配置
    auth_type TEXT DEFAULT 'bearer',             -- bearer / api_key / custom
    auth_config TEXT,                           -- 认证配置（JSON，敏感信息加密存储）
    
    -- 请求参数模板（JSON）
    request_template TEXT,                       -- 请求参数模板
    
    -- 支持的输入/输出
    supported_input_types TEXT,                   -- 支持的输入类型（JSON数组）
    supported_output_formats TEXT,               -- 支持的输出格式（JSON数组）
    max_file_size INTEGER,                       -- 最大文件大小
    
    -- 计费信息
    price_per_call TEXT,                         -- 每次调用价格
    price_unit TEXT,                            -- 价格单位
    
    -- 超时配置
    timeout_minutes INTEGER DEFAULT 30,           -- 超时时间（分钟）
    max_poll_count INTEGER DEFAULT 600,          -- 最大轮询次数
    
    -- 状态
    is_active BOOLEAN DEFAULT 1,                 -- 是否启用
    is_default BOOLEAN DEFAULT 0,                -- 是否为该任务类型的默认API
    priority INTEGER DEFAULT 0,                 -- 推荐优先级（数值越大越优先）
    
    -- 扩展字段
    extra_params TEXT,                          -- 额外参数（JSON）
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- 索引
CREATE INDEX idx_apis_provider ON apis(provider);
CREATE INDEX idx_apis_task_type ON apis(task_type);
CREATE INDEX idx_apis_active ON apis(is_active);
CREATE INDEX idx_apis_priority ON apis(priority DESC);
```

**预设API数据**：

```sql
-- 3D建模API
INSERT INTO apis (api_id, provider, task_type, api_name, api_version, endpoint_submit, endpoint_query, supported_input_types, supported_output_formats, price_per_call, timeout_minutes, priority) VALUES
('meshysty', 'Meshy.AI', '3d_model', 'Meshy 3D', 'v2', 'https://api.meshy.ai/v2/image-to-3d', 'https://api.meshy.ai/v2/image-to-3d/{task_id}', '["image_url"]', '["glb", "fbx", "obj"]', '约$0.05', 30, 10),
('doubao-seed3d', '火山引擎', '3d_model', '豆包 Seed3D', 'v2.0', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}', '["image_url", "text"]', '["glb", "stl", "obj"]', '待定', 30, 8),
('hyper3d', '影眸科技', '3d_model', 'Hyper3D Gen2', 'v2', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}', '["image_url"]', '["glb", "obj", "usdz"]', '¥1.8/次', 30, 7),
('hitem3d', '数美科技', '3d_model', 'Hitem3D', 'v2.0', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}', '["image_url", "multi_images"]', '["glb", "stl"]', '¥5-13/次', 40, 6),
('tripo3d', 'Tripo3D', '3d_model', 'Tripo3D', 'v2', 'https://api.tripo3d.ai/v2/openapi/task', 'https://api.tripo3d.ai/v2/openapi/task/{task_id}', '["image_url", "text", "multi_view"]', '["glb", "obj", "fbx"]', '待定', 30, 5);

-- 音频API（预留）
INSERT INTO apis (api_id, provider, task_type, api_name, api_version, endpoint_submit, endpoint_query, supported_input_types, supported_output_formats, timeout_minutes, priority) VALUES
('demo-tts', '待定', 'audio', 'TTS语音合成', 'v1', 'https://api.example.com/tts', 'https://api.example.com/tts/{task_id}', '["text"]', '["mp3", "wav"]', 10, 5);

-- 视频API（预留）
INSERT INTO apis (api_id, provider, task_type, api_name, api_version, endpoint_submit, endpoint_query, supported_input_types, supported_output_formats, timeout_minutes, priority) VALUES
('demo-video', '待定', 'video', '视频生成', 'v1', 'https://api.example.com/video', 'https://api.example.com/video/{task_id}', '["image", "text"]', '["mp4"]', 60, 5);
```

**字段说明**：
- `task_type`：明确区分API所属任务类型
- `auth_config`：认证配置（JSON），存储API Key等敏感信息
- `request_template`：请求参数模板，便于统一构建请求

---

## 4. ER图关系

```
                    resources (N) ──────< (N) resources_tasks >────── (N) tasks (1)
                           │                                            │
                           │                                            │
                           (N)                                         (N)
                    operations <─────────────────────────────────────┤
                           ^
                           │
                           │
                    apis (1) <────────────────────────────────────────┘

settings (独立表，全局配置)
```

**关系说明**：
- **tasks ↔ apis**：**多对一** (N) → (1) <br>多个task使用同一个API
- **resources ↔ tasks**：**多对多** (N) ↔ (N) <br>一套素材可提交多个API产生多个task
- **tasks ↔ operations**：**一对多** (1) → (N) <br>一个任务多个操作日志
- **settings**：独立表，全局配置

**多对多关系实现**：通过resources_tasks中间表实现

---

## 5. tasks表status字段详解

### 状态值定义

| 状态值 | 来源 | 含义 | 触发时机 |
|--------|------|------|---------|
| pending | 本地 | 待提交 | 任务创建，尚未提交到API |
| queued | API返回 | 排队中 | 任务提交后API初始状态 |
| running | API返回 | 任务运行中 | API从queued变为running |
| succeeded | API返回 | 任务成功 | API返回succeeded，结果已下载 |
| failed | API返回 | 任务失败 | API返回failed |
| cancelled | API返回 | 取消任务 | 任务被取消（部分API支持） |
| error | 本地判定 | API错误 | 查询接口返回error对象 |
| timeout | 本地判定 | 轮询超时 | poll_count >= max_poll_count且仍为queued/running |

### 状态流转图

```
本地路径：
pending ──> queued ──> running ──> succeeded
                     └──> failed
              └──> cancelled

错误路径：
queued/running ──(poll_count超限)──> timeout
查询返回error ──> error
```

---

## 6. 表设计对比

### 6.1 当前表结构（共6张）

| 表 | 说明 | 关系 |
|---|------|------|
| tasks | 任务主表 | 多对一 → apis |
| resources | 资源表 | 多对多 ↔ tasks（中间表） |
| operations | 操作日志表 | 一对多 ← tasks |
| settings | 系统配置表 | 独立 |
| apis | API配置表 | 多对一 ← tasks |
| resources_tasks | 资源-任务关联表 | 中间表 |

### 6.2 关系说明

| 关系 | 类型 | 说明 |
|------|------|------|
| tasks → apis | 多对一 (N)→(1) | 多个task使用同一个API |
| resources ↔ tasks | 多对多 (N)↔(N) | 一套素材提交多个API产生多个task |
| tasks → operations | 一对多 (1)→(N) | 一个任务多个操作日志 |

### 6.3 字段调整

| 字段 | 位置 |
|------|------|
| provider, api_id, api_task_id | tasks |
| api_request_body, api_response | tasks |
| input/output路径 | resources (按type区分) |
| output_format, output_size | resources (type=output) |

---

## 7. 变更日志

### v1.1 (2026-04-20)
- tasks表：添加 `submitter_user_name` 字段（飞书昵称冗余存储）
- apis表：添加 `is_default` 字段（标记任务类型的默认API）
- ER关系修正：tasks ↔ apis 为多对一，resources ↔ tasks 为多对多

### v1.0 (2026-04-20)
- 初始版本

---

## 8. 文件路径

- 数据库文件：`/root/.openclaw/workspace/smart-ai-system/smart-ai.db`
- 文档版本：v1.1
- 最后更新：2026-04-20