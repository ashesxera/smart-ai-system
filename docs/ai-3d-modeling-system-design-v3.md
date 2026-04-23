# AI-3D 建模系统设计方案

## 文档信息
- 版本：v3.0
- 创建时间：2026-04-23
- 更新说明：v3.0 - 引入模板驱动架构，支持无需代码修改即可扩展新供应商API

---

## 1. 系统概述

### 1.1 核心能力

用户通过飞书群聊或私聊提交图片/文字描述，系统自动：
1. 解析用户意图和材料
2. 同时向多个 3D 供应商 API 提交任务
3. 批量轮询任务状态（保证完整性，不追求实时性）
4. 自动下载结果并保存到 TOS 网盘
5. 生成下载链接并发送汇总报告给用户

### 1.2 支持的供应商

| 供应商 | 模型 | 输入类型 | 输出格式 |
|--------|------|----------|----------|
| Seed3D | doubao-seed3d | 图片/文字 | glb |
| 影眸 | YingMou | 1-5张图/文字 | glb, obj, usdz, fbx, stl |
| 数美 | Shumei | 1-4张图/文字 | obj, glb, stl, fbx, usdz |

### 1.3 核心设计原则

**一个用户请求 = 一个 session + 一个 materials + 多个 vendor_tasks**

**通知策略：等所有供应商完成后，发送汇总报告给用户**

**扩展性原则：所有供应商配置在数据库，通过模板驱动，新供应商无需修改代码**

---

## 2. 模板驱动架构

### 2.1 设计目标

新供应商接入流程：
1. 在 settings 表插入供应商配置（包含请求模板 + 响应解析器）
2. 在 settings 表插入材料解析规则
3. 无需修改任何 Python 代码

### 2.2 模板类型

| 模板类型 | 用途 | 示例 |
|----------|------|------|
| request_template | 构建API请求体 | {"model": "${model}", "content": ${content}} |
| content_template | 构建content数组 | [{"type": "image_url", "image_url": {"url": "${image_url_0}"}}] |
| response_parser | 解析API响应 | {"task_id": "$.id", "status": "$.status"} |
| status_map | 状态值映射 | {"pending": "queued", "completed": "succeeded"} |

### 2.3 变量替换

模板中使用 ${变量名} 进行动态替换：

| 变量 | 来源 | 说明 |
|------|------|------|
| ${model} | vendor_config.model | 模型名称 |
| ${image_url_0} | material.image_urls[0] | 第0张图片URL |
| ${text_content} | material.text_content | 文字描述 |
| ${vendor_task_id} | vendor_task.vendor_task_id | 供应商任务ID |

---

## 3. 数据库设计 (v3.0)

### 表结构

| 表名 | 说明 |
|------|------|
| sessions | 用户会话表 |
| materials | 材料表 |
| vendor_tasks | 供应商任务表 |
| results | 结果表 |
| ops_log | 操作日志表 |

### sessions 表

```sql
CREATE TABLE sessions (
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
```

### materials 表

```sql
CREATE TABLE materials (
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
```

### vendor_tasks 表

```sql
CREATE TABLE vendor_tasks (
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
```

### results 表

```sql
CREATE TABLE results (
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
```

### ops_log 表

```sql
CREATE TABLE ops_log (
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
```

### settings 表

```sql
CREATE TABLE settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT NOT NULL,
    value_type TEXT DEFAULT 'string',
    description TEXT,
    category TEXT,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);
```

---

## 4. 供应商配置模板

### 完整配置字段

```json
{
  "name": "供应商显示名称",
  "model": "API模型标识符",
  "adapter": "适配器名称",
  "endpoint": "提交任务API端点",
  "query_endpoint": "查询任务状态API端点",
  "method": "POST",
  "auth_type": "bearer",
  "timeout_minutes": 30,
  "priority": 10,
  "is_active": true,
  "supported_formats": ["glb", "obj"],
  "max_images": 1,
  "max_image_size_mb": 10,
  "request_template": {},
  "content_template": [],
  "response_parser": {},
  "status_map": {}
}
```

### 火山引擎 Seed3D 配置

```json
{
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
}
```

---

## 5. 模板处理器

### 请求构建器

```python
class TemplateRequestBuilder:
    def build(self, vendor_config: dict, material: dict) -> dict:
        content = self._build_content(vendor_config, material)
        variables = {
            'model': vendor_config['model'],
            'content': json.dumps(content),
            'text_content': material.get('text_content', ''),
            **{f'image_url_{i}': url 
               for i, url in enumerate(material.get('image_urls', []))},
        }
        request_template = vendor_config.get('request_template', {})
        return self._substitute(request_template, variables)
    
    def _substitute(self, obj, variables):
        if isinstance(obj, str):
            for key, value in variables.items():
                obj = obj.replace(f'${{{key}}}', str(value))
            return obj
        elif isinstance(obj, dict):
            return {k: self._substitute(v, variables) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute(item, variables) for item in obj]
        return obj
```

### 响应解析器

```python
class TemplateResponseParser:
    def parse(self, vendor_config: dict, response: dict) -> dict:
        parser_config = vendor_config['response_parser']
        result = {}
        for field, path in parser_config.items():
            result[field] = self._extract(response, path)
        raw_status = result.get('status')
        status_map = vendor_config.get('status_map', {})
        result['status'] = status_map.get(raw_status, raw_status)
        return result
    
    def _extract(self, data: dict, path: str) -> Any:
        if path.startswith('$.'):
            keys = path[2:].split('.')
            for key in keys:
                data = data[key]
            return data
        return data.get(path)
```

### 适配器工厂

```python
class AdapterFactory:
    _adapters = {}
    
    @classmethod
    def register(cls, name, adapter_class):
        cls._adapters[name] = adapter_class
    
    @classmethod
    def create(cls, vendor_config: dict) -> BaseAdapter:
        adapter_name = vendor_config.get('adapter', 'generic')
        adapter_class = cls._adapters.get(adapter_name, BaseAdapter)
        return adapter_class(vendor_config)
    
    @classmethod
    def get_active_vendors(cls) -> list:
        vendors = db.query(
            "SELECT * FROM settings WHERE category='vendor' AND is_active=1"
        )
        return [json.loads(v['value']) for v in vendors]
```

---

## 6. 扩展新供应商流程

### 接入步骤

```
1. 获取新供应商 API 文档
2. 确定 endpoint、method、auth_type
3. 确定请求体结构（哪些字段需要动态替换）
4. 确定响应结构（如何提取 task_id、status、file_url）
5. 确定状态映射（供应商状态 -> 系统状态）
6. 插入 settings 表
7. 完成（无需修改任何 Python 代码）
```

### 检查清单

添加新供应商前，确认：
- [ ] endpoint 和 query_endpoint
- [ ] auth_type (bearer / api_key / basic)
- [ ] 请求体模板（哪些字段需要 ${变量}）
- [ ] content 数组如何构建
- [ ] 响应解析器（task_id、status、file_url 路径）
- [ ] 状态映射（供应商状态值 -> 系统状态值）
- [ ] max_images、max_image_size_mb 限制

### 示例：接入 Meshy AI

假设 Meshy API 结构如下：
```json
POST https://api.meshy.ai/v2/image-to-3d
Body: {"model_id": "meshy-v2", "image_url": "${image_url_0}"}
Response: {"id": "xxx", "status": "pending", "model_url": null}
```

只需插入配置：
```sql
INSERT INTO settings (key, value, value_type, description, category) VALUES
('vendor_meshy', '{
  "name": "Meshy AI",
  "model": "meshy-v2",
  "adapter": "generic",
  "endpoint": "https://api.meshy.ai/v2/image-to-3d",
  "query_endpoint": "https://api.meshy.ai/v2/image-to-3d/${vendor_task_id}",
  "method": "POST",
  "auth_type": "bearer",
  "timeout_minutes": 20,
  "priority": 5,
  "is_active": true,
  "supported_formats": ["glb", "fbx", "obj"],
  "max_images": 1,
  "max_image_size_mb": 5,
  "request_template": {
    "model_id": "${model}",
    "image_url": "${image_url_0}"
  },
  "content_template": [],
  "response_parser": {
    "task_id": "$.id",
    "status": "$.status",
    "file_url": "$.model_url"
  },
  "status_map": {
    "pending": "queued",
    "in_progress": "running",
    "completed": "succeeded",
    "failed": "failed"
  }
}', 'json', 'Meshy AI', 'vendor');
```

---

## 7. 简化轮询设计

### 设计原则

**结果完整性 > 实时性**
- 简单批量轮询，60秒间隔
- 无需独立轮询 + next_poll_at

### 轮询逻辑

```python
async def poll():
    while True:
        tasks = db.get_all_running_tasks()
        
        for task in tasks:
            vendor_config = get_vendor_config(task['vendor_id'])
            adapter = AdapterFactory.create(vendor_config)
            
            query_endpoint = vendor_config['query_endpoint'].replace(
                '${vendor_task_id}', task['vendor_task_id']
            )
            
            response = await adapter.query(query_endpoint)
            parsed = adapter.parse_response(response)
            
            db.update_status(task['vendor_task_uuid'], parsed['status'])
            
            if parsed['status'] == 'succeeded':
                await handle_success(task, parsed['file_url'])
        
        for session_uuid in get_active_sessions():
            if check_all_vendors_done(session_uuid):
                await send_summary(session_uuid)
        
        await asyncio.sleep(60)
```

---

## 8. 多供应商结果汇总

### 汇总触发条件

当 session 下所有 vendor_task 状态为以下之一时触发：
- succeeded / failed / cancelled / timeout

### 汇总报告格式

```json
{
  "event": "all_vendors_completed",
  "session_uuid": "sess-xxx",
  "summary": {
    "total_vendors": 3,
    "succeeded": 2,
    "failed": 1
  },
  "results": [
    {"vendor_name": "豆包Seed3D", "status": "succeeded", "share_url": "..."},
    {"vendor_name": "影眸 Hyper3D", "status": "succeeded", "share_url": "..."},
    {"vendor_name": "数美 Hitem3D", "status": "failed", "error_message": "..."}
  ]
}
```

---

## 9. TOS 存储设计

### 目录结构

```
tos://4-ark-claw/ai-3d-system/sessions/{session_uuid}/
  materials/{uuid}.{ext}
  results/{vendor_id}.glb
```

### tosutil 命令

```bash
# 上传
tosutil cp local_file.tmp tos://4-ark-claw/ai-3d-system/sessions/{uuid}/materials/

# 生成下载链接 (24小时)
tosutil sign tos://4-ark-claw/ai-3d-system/sessions/{uuid}/results/model.glb --expire 86400
```
