# Smart AI 任务系统数据库设计方案

## 文档信息
- 版本：v3.4
- 创建时间：2026-04-20
- 更新时间：2026-04-22
- 目标系统：通用异步AI任务系统
- 数据库类型：SQLite 3

---

## 1. 核心概念

### 1.1 业务模型

```
委托人 ─── 1:N ─── 材料 ─── M:N ─── 任务 ─── N:1 ─── 供应商
```

### 1.2 术语定义

| 术语 | 英文 | 说明 |
|------|------|------|
| 委托人 | Delegator | 提交任务的用户，抽象多渠道 |
| 材料 | Material | 委托的材料（含语义理解+资源+参数） |
| 任务 | Task | 材料委托给供应商生产的AI产品 |
| 供应商 | Vendor | AI服务供应商（供应商+模型） |

### 1.3 核心关系

| 关系 | 说明 |
|------|------|
| 委托人 → 材料 | 1对多 |
| 材料 → 任务 | 1对多，一份材料可分发给多个任务 |
| 任务 → 供应商 | 多对一 |
| 材料 ↔ 供应商 | 多对多，通过任务连接 |

### 1.4 解耦设计

| 角色 | 职责 | 不关心 |
|------|------|--------|
| 委托人 | 提交材料、查看状态、获取结果 | 具体用哪个供应商 |
| 供应商 | 接收材料、处理、返回结果 | 谁提交的 |
| 系统 | 匹配调度、状态跟踪、结果分发 | - |

---

## 2. 材料定义

```
Material（材料）= 
├── 对话语义 (Semantic)
│   ├── 原始输入：用户怎么说的
│   ├── 意图理解：用户想要什么
│   └── 参数提取：从对话中解析出的参数
├── 资源 (Resources)
│   └── 图片/视频/音频/URL/文件
└── 参数 (Parameters)
    └── API配置参数
```

---

## 3. 支持的任务类型

| 任务类型 | task_type | 示例Vendor |
|----------|-----------|------------|
| 3D建模 | 3d_model | Meshy.AI、火山引擎、Tripo3D |
| 音频生成 | audio | TTS、语音合成 |
| 视频生成 | video | 视频生成、AI剪辑 |

---

## 4. 数据库表结构

### 4.1 delegators（委托人表）

**用途**：存储委托人多渠道用户信息

```sql
CREATE TABLE delegators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 委托人标识
    delegator_id TEXT NOT NULL UNIQUE,          -- 系统内部的委托人ID
    
    -- 渠道信息
    channel_type TEXT NOT NULL,                  -- 渠道类型：feishu / wecom / telegram / webchat
    channel_user_id TEXT NOT NULL,              -- 渠道原始用户ID
    
    -- 用户信息（冗余存储）
    user_name TEXT,                             -- 用户名称/昵称
    user_display_name TEXT,                     -- 显示名称
    
    -- 通知配置
    notify_enabled BOOLEAN DEFAULT 1,           -- 是否启用通知
    notify_channel TEXT,                        -- 通知渠道
    
    -- 统计信息
    total_tasks INTEGER DEFAULT 0,              -- 总提交任务数
    successful_tasks INTEGER DEFAULT 0,         -- 成功任务数
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- 索引
CREATE INDEX idx_delegators_channel ON delegators(channel_type, channel_user_id);
CREATE INDEX idx_delegators_delegator_id ON delegators(delegator_id);
```

---

### 4.2 materials（材料表）

**用途**：存储委托人的材料（含语义理解+资源+参数），与 resources 为 1对1 关系

```sql
CREATE TABLE materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 材料标识（与 task_id 1对1）
    task_id TEXT NOT NULL UNIQUE,             -- 系统内部的任务ID（与 tasks 表 1对1）
    
    -- 委托人（外键）
    delegator_id TEXT NOT NULL,                -- 委托人ID
    
    -- 材料状态
    status TEXT NOT NULL DEFAULT 'pending',    -- pending / completed
    
    -- 语义和参数文件路径（相对于 task 目录）
    semantic_path TEXT,                        -- 路径：materials/semantic.md
    api_params_path TEXT,                      -- 路径：materials/api_params.json
    
    -- 资源信息（合并到 materials，1对1）
    resource_type TEXT,                        -- image / text / video / audio / url
    source_type TEXT,                          -- channel_file / url / base64 / text
    
    -- 文件信息
    file_name TEXT,                           -- 文件名
    file_size INTEGER,                        -- 文件大小（字节）
    file_mime_type TEXT,                      -- MIME类型
    
    -- UUID（对应 TOS 文件名）
    resource_uuid TEXT,                        -- UUID，用于 TOS 文件名
    
    -- 存储路径
    tos_path TEXT,                            -- TOS完整路径：smart-ai-tasks/{task_id}/materials/{uuid}.ext
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    
    -- 外键约束
    FOREIGN KEY (delegator_id) REFERENCES delegators(delegator_id)
);

-- 索引
CREATE INDEX idx_materials_task_id ON materials(task_id);
CREATE INDEX idx_materials_delegator ON materials(delegator_id);
CREATE INDEX idx_materials_status ON materials(status);
CREATE INDEX idx_materials_created ON materials(created_at DESC);
```

**说明**：material_resources 表已与 materials 合并（1对1关系），不再单独使用。

---

### 4.3 material_resources（材料资源表）

**用途**：存储材料中的具体资源

```sql
CREATE TABLE material_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 关联材料
    material_id TEXT NOT NULL,                 -- 材料ID
    
    -- 资源类型
    resource_type TEXT NOT NULL,               -- image / text / video / audio / url
    
    -- 来源类型
    source_type TEXT NOT NULL,                -- channel_file / url / base64 / text
    
    -- 渠道信息
    channel_type TEXT,                        -- 渠道类型：feishu / wecom / telegram
    file_key TEXT,                           -- 渠道file_key
    
    -- 文件信息
    file_name TEXT,                          -- 文件名
    file_size INTEGER,                       -- 文件大小（字节）
    file_mime_type TEXT,                     -- MIME类型
    
    -- URL信息
    source_url TEXT,                         -- 原始URL
    
    -- 文本内容
    text_content TEXT,                       -- 文本内容
    
    -- 存储信息
    tos_path TEXT,                           -- TOS存储路径
    local_tmp_path TEXT,                     -- 本地临时路径
    
    -- 资源顺序
    resource_order INTEGER DEFAULT 1,         -- 资源顺序
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    
    -- 外键约束
    FOREIGN KEY (material_id) REFERENCES materials(material_id) ON DELETE CASCADE
);

-- 索引
CREATE INDEX idx_mr_material_id ON material_resources(material_id);
CREATE INDEX idx_mr_type ON material_resources(resource_type);
```

---

### 4.4 tasks（任务表）

**用途**：存储任务信息，连接材料和供应商

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 任务标识
    task_id TEXT NOT NULL UNIQUE,             -- 系统内部的任务ID
    
    -- 供应商（外键）
    vendor_id TEXT NOT NULL,                  -- 供应商ID
    
    -- 供应商返回的任务ID
    vendor_task_id TEXT,                      -- 供应商任务ID
    
    -- 任务状态
    status TEXT NOT NULL DEFAULT 'pending',    -- pending/submitting/queued/running/succeeded/failed/cancelled/error/timeout
    status_message TEXT,                      -- 状态描述
    
    -- 错误信息
    error_code TEXT,                          -- 错误码
    error_message TEXT,                       -- 错误信息
    
    -- API请求（完整）
    api_request TEXT,                         -- 提交给供应商的完整请求JSON
    
    -- API返回（完整）
    api_response TEXT,                        -- 供应商返回的完整响应JSON
    
    -- API参数（JSON，冗余存储便于快速查看）
    parameters TEXT,                          -- 提交给供应商的参数
    
    -- 结果信息（JSON）
    result_files TEXT,                       -- 结果文件列表
    
    -- TOS路径
    tos_path TEXT,                           -- 任务目录：smart-ai-tasks/{task_id}/
    
    -- 分享链接
    share_url TEXT,                           -- 分享链接
    share_expires_at INTEGER,                 -- 分享链接过期时间
    
    -- 计费信息
    token_usage TEXT,                         -- token消耗
    estimated_cost TEXT,                       -- 预估花费
    actual_cost TEXT,                          -- 实际花费
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    completed_at INTEGER,                      -- 完成时间
    
    -- 轮询相关
    poll_count INTEGER DEFAULT 0,              -- 轮询次数
    last_poll_at INTEGER,                      -- 最后轮询时间
    max_poll_count INTEGER DEFAULT 600,        -- 最大轮询次数
    
    -- 乐观锁
    version INTEGER DEFAULT 0,
    
    -- 外键约束
    FOREIGN KEY (material_id) REFERENCES materials(material_id),
    FOREIGN KEY (vendor_id) REFERENCES ai_vendors(vendor_id)
);

-- 索引
CREATE INDEX idx_tasks_task_id ON tasks(task_id);
CREATE INDEX idx_tasks_material ON tasks(material_id);
CREATE INDEX idx_tasks_vendor ON tasks(vendor_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);
```

**字段说明**：
- `api_request`：提交给供应商的完整请求，包含 headers、body 等
- `api_response`：供应商返回的完整响应，便于问题排查
- `tos_path`：任务在 TOS 上的根目录路径

---

### 4.5 ai_vendors（供应商表）

**用途**：管理AI服务供应商配置

```sql
CREATE TABLE ai_vendors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 供应商标识
    vendor_id TEXT NOT NULL UNIQUE,            -- 供应商唯一标识（包含模型版本）
    vendor_name TEXT NOT NULL,                 -- 供应商名称
    model_name TEXT NOT NULL,                  -- 模型名称
    model_version TEXT,                       -- 模型版本
    
    -- 任务类型
    task_type TEXT NOT NULL,                   -- 3d_model / audio / video
    
    -- 端点配置
    endpoint_submit TEXT NOT NULL,             -- 任务提交端点
    endpoint_query TEXT,                      -- 任务查询端点
    endpoint_cancel TEXT,                     -- 任务取消端点
    
    -- 认证配置
    auth_type TEXT DEFAULT 'bearer',          -- bearer / api_key / custom
    auth_config TEXT,                          -- 认证配置（JSON）
    
    -- 请求参数模板
    request_template TEXT,                     -- 请求参数模板（JSON）
    
    -- 支持的输入/输出
    supported_input_types TEXT,                -- 支持的输入类型
    supported_output_formats TEXT,             -- 支持的输出格式
    max_file_size INTEGER,                    -- 最大文件大小
    
    -- 计费信息
    price_per_call TEXT,                      -- 每次调用价格
    price_unit TEXT,                          -- 价格单位
    
    -- 超时配置
    timeout_minutes INTEGER DEFAULT 30,        -- 超时时间（分钟）
    max_poll_count INTEGER DEFAULT 600,        -- 最大轮询次数
    
    -- 状态
    is_active BOOLEAN DEFAULT 1,              -- 是否启用
    is_default BOOLEAN DEFAULT 0,              -- 是否为默认供应商
    priority INTEGER DEFAULT 0,                -- 推荐优先级
    
    -- 扩展字段
    extra_params TEXT,                        -- 额外参数（JSON）
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- 索引
CREATE INDEX idx_vendors_task_type ON ai_vendors(task_type);
CREATE INDEX idx_vendors_active ON ai_vendors(is_active);
CREATE INDEX idx_vendors_priority ON ai_vendors(priority DESC);
```

---

### 4.6 operations（操作日志表）

**用途**：记录所有关键操作

```sql
CREATE TABLE operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 关联任务
    task_id TEXT,                             -- 任务ID
    
    -- 操作类型
    operation_type TEXT NOT NULL,             -- 操作类型
    operation_detail TEXT,                    -- 操作详情（JSON）
    
    -- 操作结果
    status TEXT NOT NULL,                     -- success / failed / pending
    
    -- 错误信息
    error_message TEXT,                       -- 错误信息
    
    -- 性能指标
    duration_ms INTEGER,                     -- 操作耗时（毫秒）
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    
    -- 操作者
    operator TEXT,                            -- system / delegator_xxx / poller
    
    -- 外键约束
    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE SET NULL
);

-- 索引
CREATE INDEX idx_operations_task_id ON operations(task_id);
CREATE INDEX idx_operations_type ON operations(operation_type);
CREATE INDEX idx_operations_created ON operations(created_at DESC);
```

---

### 4.8 settings（系统配置表）

**用途**：存储系统级配置参数

```sql
CREATE TABLE settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    key TEXT NOT NULL UNIQUE,                 -- 配置键
    value TEXT NOT NULL,                      -- 配置值
    value_type TEXT DEFAULT 'string',         -- string / int / bool / json
    description TEXT,                         -- 配置说明
    category TEXT,                           -- 配置分类
    
    -- 时间戳
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

-- 索引
CREATE INDEX idx_settings_category ON settings(category);
```

---

## 5. ER图关系

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  delegators  │ 1    N│  materials   │ M    N│    tasks     │ N    1│  ai_vendors  │
│   委托人     │───────▶│    材料      │───────▶│    任务      │───────▶│    供应商     │
└──────────────┘       └──────┬───────┘       └──────┬───────┘       └──────────────┘
                             │                     │
                             │ N                   │ 1
                             ▼                     ▼
                    ┌──────────────┐       ┌──────────────┐
                    │material_     │
                    │resources     │       │ operations   │
                    │   资源       │       │ 操作日志     │
                    └──────────────┘       └──────────────┘

                    settings 独立
```

**关系说明**：
- 委托人 → 材料：1对多
- 材料 → 任务：1对多（一份材料分发给多个任务）
- 任务 → 供应商：多对一
- 材料 ↔ 供应商：多对多（通过任务连接）

---

## 6. 表结构汇总

| 表名 | 说明 | 关系 |
|------|------|------|
| delegators | 委托人表 | - |
| materials | 材料表 | N ← 1 委托人 |
| material_resources | 资源表 | N ← 1 材料 |
| tasks | 任务表 | N ← 1 材料, N ← 1 供应商 |
| ai_vendors | 供应商表 | - |
| operations | 操作日志表 | N ← 1 任务 |
| settings | 系统配置表 | 独立 |

---

## 7. tasks 表 status 字段详解

### 状态值定义

| 状态值 | 阶段 | 含义 |
|--------|------|------|
| pending | 创建 | 待提交 |
| submitting | 提交 | 提交中 |
| queued | 供应商 | 排队中 |
| running | 供应商 | 处理中 |
| succeeded | 完成 | 成功 |
| failed | 完成 | 失败 |
| cancelled | 完成 | 已取消 |
| error | 错误 | 出错 |
| timeout | 超时 | 轮询超时 |

### 状态流转

```
pending → submitting → queued → running → succeeded
                              │           │
                              │           └──> failed
                              │
                              └──> cancelled / error / timeout
```

---

## 8. 预设数据

### 8.1 供应商预设

```sql
INSERT INTO ai_vendors (vendor_id, vendor_name, model_name, model_version, task_type, endpoint_submit, endpoint_query, supported_input_types, supported_output_formats, price_per_call, timeout_minutes, priority) VALUES
('meshysty_v2', 'Meshy.AI', 'Meshy 3D', 'v2', '3d_model', 'https://api.meshy.ai/v2/image-to-3d', 'https://api.meshy.ai/v2/image-to-3d/{task_id}', '["image_url"]', '["glb", "fbx", "obj"]', '约$0.05', 30, 10),
('doubao_seed3d_v2', '火山引擎', '豆包 Seed3D', 'v2.0', '3d_model', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}', '["image_url", "text"]', '["glb", "stl", "obj"]', '待定', 30, 8),
('hyper3d_v2', '影眸科技', 'Hyper3D Gen2', 'v2', '3d_model', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}', '["image_url"]', '["glb", "obj", "usdz"]', '¥1.8/次', 30, 7),
('hitem3d_v2', '数美科技', 'Hitem3D', 'v2.0', '3d_model', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks', 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/{task_id}', '["image_url", "multi_images"]', '["glb", "stl"]', '¥5-13/次', 40, 6),
('tripo3d_v2', 'Tripo3D', 'Tripo3D', 'v2', '3d_model', 'https://api.tripo3d.ai/v2/openapi/task', 'https://api.tripo3d.ai/v2/openapi/task/{task_id}', '["image_url", "text", "multi_view"]', '["glb", "obj", "fbx"]', '待定', 30, 5);
```

### 8.2 系统配置预设

```sql
-- 轮询配置
INSERT INTO settings (key, value, value_type, description, category) VALUES
('polling_interval_seconds', '180', 'int', '轮询间隔（秒）', 'polling'),
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

-- 分享链接配置
INSERT INTO settings (key, value, value_type, description, category) VALUES
('share_url_expire_hours', '24', 'int', '分享链接有效期（小时）', 'share');
```

---

## 9. 变更日志

### v3.4 (2026-04-22)
- materials 表：material_id 改为 task_id（1对1）
- tasks 表：移除 material_id 外键（1对1 关系）

### v3.3 (2026-04-22)
- materials 表：增加 semantic_path、api_params_path、resource_uuid、tos_path 等字段
- material_resources 表：已与 materials 表合并（1对1关系），不再单独使用
- tasks 表：增加 api_request（完整请求）、api_response（完整返回）、tos_path（TOS路径）

### v3.2 (2026-04-21)
- materials 表增加 status 字段：pending / completed
- Skill 确认后一次性写入 materials（status=pending）
- 后台进程轮询 pending materials 创建 tasks，标记 completed

### v3.1 (2026-04-21)
- 删除 task_results 表
- tasks 表增加 result_files JSON 字段，支持多个结果文件

### v3.0 (2026-04-21)
- 重新梳理ER关系：委托人 → 材料(1:N) → 任务(M:N) → 供应商(N:1)
- 材料表新增 semantic 字段：对话语义理解
- 材料 → 任务：1对多（一份材料分发给多个任务）
- 任务 → 供应商：多对一
- 材料 ↔ 供应商：通过任务实现多对多

### v2.1 (2026-04-21)
- 引入 materials/material_resources 表

### v2.0 (2026-04-21)
- 新增 delegators 表
- apis → ai_vendors

### v1.0 (2026-04-20)
- 初始版本

---

## 10. 文件路径

- 数据库文件：`/root/.openclaw/workspace/smart-ai-system/smart-ai.db`
- 文档版本：v3.4
- 最后更新：2026-04-22