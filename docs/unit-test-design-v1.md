# AI-3D 建模系统 - 单元测试用例设计

## 文档信息
- 版本：v1.0.0
- 创建时间：2026-04-23
- 基于设计：ai-3d-modeling-system-design-v3.md

---

## 1. 测试策略

### 1.1 测试分层

```
┌─────────────────────────────────────────┐
│           单元测试 (Unit Tests)          │
│   测试独立模块的功能，不依赖外部服务       │
└─────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────┐
│         集成测试 (Integration Tests)     │
│   测试模块间交互，使用真实数据库           │
└─────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────┐
│           端到端测试 (E2E Tests)        │
│   模拟真实用户流程                        │
└─────────────────────────────────────────┘
```

### 1.2 测试目录结构

```
tests/
├── unit/
│   ├── test_adapters.py
│   ├── test_db.py
│   ├── test_storage.py
│   ├── test_poller.py
│   └── test_utils.py
├── integration/
│   ├── test_skill.py
│   └── test_poller_integration.py
└── conftest.py          # pytest 配置
```

---

## 2. adapters 模块测试

### 2.1 TemplateRequestBuilder 测试

#### TC-ADAPTER-001: 构建简单图片请求

```python
def test_build_simple_image_request():
    """
    测试：使用单张图片构建请求
    输入：
        vendor_config = {
            "model": "doubao-seed3d",
            "request_template": {"model": "${model}", "content": ${content}},
            "content_template": [
                {"type": "image_url", "image_url": {"url": "${image_url_0}"}}
            ]
        }
        material = {
            "image_urls": ["https://example.com/image.jpg"],
            "text_content": ""
        }
    预期：
        request = {
            "model": "doubao-seed3d",
            "content": [{"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}]
        }
    """
    pass
```

#### TC-ADAPTER-002: 构建图文混合请求

```python
def test_build_text_and_image_request():
    """
    测试：使用图片和文字构建请求
    输入：
        vendor_config = {
            "model": "YingMou",
            "request_template": {"model": "${model}", "content": ${content}},
            "content_template": [
                {"type": "image_url", "image_url": {"url": "${image_url_0}"}},
                {"type": "text", "text": "${text_content}"}
            ]
        }
        material = {
            "image_urls": ["https://example.com/image.jpg"],
            "text_content": "a cute cat"
        }
    预期：
        content 包含 image_url 和 text 两个元素
    """
    pass
```

#### TC-ADAPTER-003: 多图请求构建

```python
def test_build_multi_image_request():
    """
    测试：使用多张图片构建请求
    输入：
        material = {
            "image_urls": [
                "https://example.com/1.jpg",
                "https://example.com/2.jpg"
            ]
        }
    预期：
        content 包含两个 image_url 元素
    """
    pass
```

#### TC-ADAPTER-004: 空材料处理

```python
def test_build_with_empty_material():
    """
    测试：材料为空时的处理
    输入：
        material = {"image_urls": [], "text_content": ""}
    预期：
        content 为空数组
    """
    pass
```

### 2.2 TemplateResponseParser 测试

#### TC-PARSER-001: 解析成功响应

```python
def test_parse_success_response():
    """
    测试：解析成功的任务响应
    输入：
        vendor_config = {
            "response_parser": {
                "task_id": "$.id",
                "status": "$.status",
                "file_url": "$.content.file_url"
            },
            "status_map": {
                "succeeded": "succeeded",
                "failed": "failed"
            }
        }
        response = {
            "id": "task_123",
            "status": "succeeded",
            "content": {"file_url": "https://example.com/model.glb"}
        }
    预期：
        result = {
            "task_id": "task_123",
            "status": "succeeded",
            "file_url": "https://example.com/model.glb"
        }
    """
    pass
```

#### TC-PARSER-002: 解析失败响应

```python
def test_parse_failure_response():
    """
    测试：解析失败的任务响应
    输入：response.status = "failed"
    预期：result.status = "failed"
    """
    pass
```

#### TC-PARSER-003: 状态映射

```python
def test_status_mapping():
    """
    测试：供应商状态到系统状态的映射
    输入：
        status_map = {"pending": "queued", "completed": "succeeded"}
        response.status = "completed"
    预期：result.status = "succeeded"
    """
    pass
```

#### TC-PARSER-004: 嵌套JSONPath提取

```python
def test_nested_jsonpath_extraction():
    """
    测试：提取嵌套在多层JSON中的字段
    输入：path = "$.content.file_url"
    预期：正确提取深层嵌套的值
    """
    pass
```

### 2.3 AdapterFactory 测试

#### TC-FACTORY-001: 创建适配器实例

```python
def test_create_adapter_instance():
    """
    测试：根据配置创建正确的适配器实例
    输入：vendor_config.adapter = "ark_generic"
    预期：返回 BaseAdapter 实例
    """
    pass
```

#### TC-FACTORY-002: 获取活跃供应商

```python
def test_get_active_vendors():
    """
    测试：从数据库获取所有活跃供应商配置
    预期：返回 is_active=true 的供应商列表
    """
    pass
```

#### TC-FACTORY-003: 未知适配器处理

```python
def test_unknown_adapter_fallback():
    """
    测试：未知适配器名称时使用默认适配器
    输入：adapter = "unknown_adapter"
    预期：返回 BaseAdapter 实例（不抛异常）
    """
    pass
```

---

## 3. db 模块测试

### 3.1 Database 测试

#### TC-DB-001: 初始化数据库

```python
def test_database_initialization(tmp_path):
    """
    测试：初始化数据库并创建所有表
    预期：
        - sessions 表存在
        - materials 表存在
        - vendor_tasks 表存在
        - results 表存在
        - ops_log 表存在
        - settings 表存在
    """
    pass
```

#### TC-DB-002: 数据库连接复用

```python
def test_database_connection_reuse():
    """
    测试：多次调用 get_connection() 返回同一连接
    """
    pass
```

### 3.2 SessionManager 测试

#### TC-SESSION-001: 创建会话

```python
def test_create_session():
    """
    测试：创建新会话
    输入：
        session_uuid = "sess_test_001"
        channel_type = "feishu"
        channel_user_id = "ou_123"
    预期：
        - 返回包含 session_uuid 的字典
        - status = "active"
        - phase = "pending"
    """
    pass
```

#### TC-SESSION-002: 获取会话

```python
def test_get_session():
    """
    测试：通过 UUID 获取会话
    预期：返回正确的会话记录
    """
    pass
```

#### TC-SESSION-003: 更新会话阶段

```python
def test_update_session_phase():
    """
    测试：更新会话阶段
    输入：phase = "materials_ready"
    预期：updated_at 时间戳更新
    """
    pass
```

#### TC-SESSION-004: 获取活跃会话列表

```python
def test_get_active_sessions():
    """
    测试：获取所有活跃会话
    预期：返回 status="active" 的会话列表
    """
    pass
```

### 3.3 MaterialManager 测试

#### TC-MATERIAL-001: 创建材料记录

```python
def test_create_material():
    """
    测试：创建材料记录
    输入：
        material_uuid = "mat_test_001"
        session_uuid = "sess_test_001"
        material_type = "image"
        source_type = "feishu"
        image_urls = '["url1", "url2"]'
    预期：
        - material_uuid 正确存储
        - image_urls 正确解析
    """
    pass
```

#### TC-MATERIAL-002: 按会话获取材料

```python
def test_get_materials_by_session():
    """
    测试：获取某个会话的所有材料
    预期：返回该会话的材料列表
    """
    pass
```

### 3.4 VendorTaskManager 测试

#### TC-TASK-001: 创建供应商任务

```python
def test_create_vendor_task():
    """
    测试：创建供应商任务记录
    输入：
        vendor_task_uuid = "task_test_001"
        session_uuid = "sess_test_001"
        material_uuid = "mat_test_001"
        vendor_id = "vendor_ark_seed3d"
        vendor_name = "豆包Seed3D"
        model_name = "doubao-seed3d"
    预期：
        - status = "pending"
        - poll_count = 0
    """
    pass
```

#### TC-TASK-002: 获取运行中任务

```python
def test_get_running_tasks():
    """
    测试：获取所有运行中的任务
    预期：返回 status IN ('queued', 'running') 的任务
    """
    pass
```

#### TC-TASK-003: 更新任务状态

```python
def test_update_task_status():
    """
    测试：更新任务状态
    输入：
        vendor_task_uuid = "task_test_001"
        status = "running"
    预期：
        - status 更新为 "running"
        - updated_at 时间戳更新
    """
    pass
```

#### TC-TASK-004: 设置供应商任务ID

```python
def test_set_vendor_task_id():
    """
    测试：设置供应商返回的任务ID
    输入：vendor_task_id = "ark_12345"
    预期：vendor_task_id 字段更新
    """
    pass
```

#### TC-TASK-005: 增加轮询计数

```python
def test_increment_poll_count():
    """
    测试：轮询后增加计数
    预期：poll_count += 1
    """
    pass
```

#### TC-TASK-006: 会话所有任务是否完成

```python
def test_check_all_tasks_done():
    """
    测试：检查会话的所有供应商任务是否完成
    场景1：3个任务都 succeeded -> True
    场景2：2个 succeeded, 1个 running -> False
    场景3：1个 failed, 2个 succeeded -> True
    """
    pass
```

---

## 4. storage 模块测试

### 4.1 StorageManager 测试

#### TC-STORAGE-001: 构建TOS路径

```python
def test_build_tos_path():
    """
    测试：构建正确的TOS存储路径
    输入：
        session_uuid = "sess_123"
        sub_path = "materials/file.jpg"
    预期：返回 "ai-3d-system/sessions/sess_123/materials/file.jpg"
    """
    pass
```

#### TC-STORAGE-002: 生成下载链接

```python
def test_generate_share_url():
    """
    测试：生成带有过期时间的下载链接
    输入：
        tos_path = "ai-3d-system/.../model.glb"
        expire_seconds = 86400
    预期：返回包含过期时间的URL
    """
    pass
```

#### TC-STORAGE-003: 路径安全检查

```python
def test_path_security():
    """
    测试：防止路径遍历攻击
    输入：sub_path = "../../../etc/passwd"
    预期：抛出异常或拒绝访问
    """
    pass
```

---

## 5. poller 模块测试

### 5.1 Poller 测试

#### TC-POLLER-001: 批量获取运行中任务

```python
def test_batch_get_running_tasks():
    """
    测试：一次性获取所有运行中的任务
    预期：返回所有 queued/running 状态的任务
    """
    pass
```

#### TC-POLLER-002: 状态检查

```python
def test_check_task_status():
    """
    测试：调用供应商API检查任务状态
    预期：正确解析并返回状态
    """
    pass
```

#### TC-POLLER-003: 成功处理

```python
def test_handle_success():
    """
    测试：任务成功后的处理流程
    1. 下载文件
    2. 上传到TOS
    3. 生成下载链接
    4. 更新数据库
    """
    pass
```

#### TC-POLLER-004: 失败处理

```python
def test_handle_failure():
    """
    测试：任务失败后的处理
    预期：
        - 更新 status = "failed"
        - 记录错误信息
        - 不上传文件
    """
    pass
```

#### TC-POLLER-005: 轮询间隔

```python
def test_poll_interval():
    """
    测试：轮询间隔正确
    预期：每60秒执行一次轮询
    """
    pass
```

---

## 6. utils 模块测试

### 6.1 工具函数测试

#### TC-UTIL-001: UUID生成

```python
def test_generate_uuid():
    """
    测试：生成符合格式的UUID
    预期：格式为 xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
    """
    pass
```

#### TC-UTIL-002: 时间戳获取

```python
def test_get_timestamp():
    """
    测试：获取当前Unix时间戳
    预期：返回整数秒级时间戳
    """
    pass
```

#### TC-UTIL-003: 时长格式化

```python
def test_format_duration():
    """
    测试：秒数转换为可读时长
    输入：seconds = 125
    预期：返回 "2分5秒"
    """
    pass
```

#### TC-UTIL-004: 内容类型解析

```python
def test_parse_content_type():
    """
    测试：从URL解析文件类型
    输入：url = "https://example.com/model.glb"
    预期：返回 "glb"
    """
    pass
```

---

## 7. 边界条件测试

### 7.1 空值处理

```
TC-EDGE-001: material.image_urls = None
TC-EDGE-002: material.text_content = None
TC-EDGE-003: response 缺少可选字段
TC-EDGE-004: vendor_config 缺少可选字段
```

### 7.2 异常数据

```
TC-EDGE-005: response 不是合法 JSON
TC-EDGE-006: response.status 超出预期范围
TC-EDGE-007: 文件URL已过期
TC-EDGE-008: 网络请求超时
```

### 7.3 并发测试

```
TC-EDGE-009: 多线程同时轮询同一任务
TC-EDGE-010: 多线程同时更新同一记录
```

---

## 8. 测试数据准备

### 8.1 Mock 供应商配置

```python
MOCK_VENDOR_CONFIG = {
    "name": "测试供应商",
    "model": "test-model",
    "adapter": "ark_generic",
    "endpoint": "https://api.test.com/submit",
    "query_endpoint": "https://api.test.com/query/${vendor_task_id}",
    "method": "POST",
    "auth_type": "bearer",
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
        "file_url": "$.file_url"
    },
    "status_map": {
        "queued": "queued",
        "running": "running",
        "succeeded": "succeeded",
        "failed": "failed"
    }
}
```

### 8.2 Mock 响应数据

```python
MOCK_SUCCESS_RESPONSE = {
    "id": "task_12345",
    "status": "succeeded",
    "file_url": "https://example.com/model.glb"
}

MOCK_RUNNING_RESPONSE = {
    "id": "task_12345",
    "status": "running",
    "progress": 50
}

MOCK_FAILURE_RESPONSE = {
    "id": "task_12345",
    "status": "failed",
    "error": {"code": "IMAGE_TOO_SMALL", "message": "图片分辨率过低"}
}
```

---

## 9. notifier 模块测试

### 9.1 ResultSummarizer 测试

#### TC-SUM-001: 汇总成功结果

```python
def test_summarize_success_results():
    """
    测试：汇总所有成功的供应商结果
    场景：
        - 3个任务，2个成功，1个失败
    预期：
        summary = {
            "total_vendors": 3,
            "succeeded": 2,
            "failed": 1
        }
    """
    pass
```

#### TC-SUM-002: 检查所有任务完成

```python
def test_check_all_done():
    """
    测试：检查会话是否所有供应商任务都完成
    场景1：3个任务都 succeeded -> True
    场景2：2个 succeeded, 1个 running -> False
    场景3：1个 failed, 2个 succeeded -> True
    """
    pass
```

#### TC-SUM-003: 计算总耗时

```python
def test_calculate_total_duration():
    """
    测试：计算从提交到所有任务完成的总耗时
    预期：返回秒数
    """
    pass
```

#### TC-SUM-004: 构建材料预览信息

```python
def test_build_materials_preview():
    """
    测试：构建材料的预览信息
    预期：包含类型、数量、预览URL
    """
    pass
```

### 9.2 FeishuNotifier 测试

#### TC-NOTIFY-001: 构建飞书卡片

```python
def test_build_feishu_card():
    """
    测试：构建飞书消息卡片
    预期：卡片包含标题、摘要、结果列表
    """
    pass
```

#### TC-NOTIFY-002: 发送汇总通知

```python
def test_send_summary_notification():
    """
    测试：发送汇总通知到飞书
    预期：
        - 调用 gateway webhook
        - 传递正确的 session_uuid 和 summary
    """
    pass
```

#### TC-NOTIFY-003: 通知内容格式化

```python
def test_format_duration_in_card():
    """
    测试：在通知卡片中格式化时长
    输入：125秒
    预期：显示 "2分5秒"
    """
    pass
```

#### TC-NOTIFY-004: 失败结果展示

```python
def test_show_failure_in_card():
    """
    测试：在通知卡片中展示失败信息
    预期：显示错误码和错误消息
    """
    pass
```

#### TC-NOTIFY-005: 成功结果展示

```python
def test_show_success_in_card():
    """
    测试：在通知卡片中展示成功结果
    预期：显示供应商名称、文件格式、下载链接
    """
    pass
```

---

## 10. skill 模块测试

### 10.1 意图解析测试

#### TC-SKILL-INTENT-001: 识别3D建模请求

```python
def test_parse_3d_modeling_intent():
    """
    测试：解析用户消息，识别3D建模意图
    输入："帮我生成一个卡通人物的3D模型"
    预期：返回 intent = "3d_modeling"
    """
    pass
```

#### TC-SKILL-INTENT-002: 识别取消意图

```python
def test_parse_cancel_intent():
    """
    测试：解析取消意图
    输入："取消刚才的请求"
    预期：返回 intent = "cancel"
    """
    pass
```

#### TC-SKILL-INTENT-003: 非3D请求

```python
def test_parse_non_3d_intent():
    """
    测试：解析非3D建模请求
    输入："今天天气怎么样"
    预期：返回 intent = "other" 或 None
    """
    pass
```

### 10.2 材料提取测试

#### TC-SKILL-EXTRACT-001: 提取图片

```python
def test_extract_image_from_message():
    """
    测试：从消息中提取图片URL
    输入：包含图片的消息
    预期：返回 image_urls 列表
    """
    pass
```

#### TC-SKILL-EXTRACT-002: 提取文字描述

```python
def test_extract_text_description():
    """
    测试：从消息中提取文字描述
    输入："生成一个穿着西装的绅士"
    预期：返回 text_content = "生成一个穿着西装的绅士"
    """
    pass
```

#### TC-SKILL-EXTRACT-003: 混合提取

```python
def test_extract_mixed_content():
    """
    测试：同时提取图片和文字
    预期：image_urls 和 text_content 都不为空
    """
    pass
```

### 10.3 任务创建测试

#### TC-SKILL-CREATE-001: 创建会话

```python
def test_create_session():
    """
    测试：创建新的用户会话
    预期：
        - session_uuid 生成
        - 记录 channel_type, channel_user_id
        - status = "active", phase = "pending"
    """
    pass
```

#### TC-SKILL-CREATE-002: 创建材料记录

```python
def test_create_material_record():
    """
    测试：创建材料记录
    预期：
        - material_uuid 生成
        - image_urls 和 text_content 正确存储
    """
    pass
```

#### TC-SKILL-CREATE-003: 批量创建供应商任务

```python
def test_create_vendor_tasks_batch():
    """
    测试：同时向多个供应商创建任务
    预期：
        - 为每个活跃供应商创建一个任务
        - vendor_task_uuid 唯一
        - status = "pending"
    """
    pass
```

#### TC-SKILL-CREATE-004: 跳过不活跃供应商

```python
def test_skip_inactive_vendors():
    """
    测试：只向活跃供应商创建任务
    预期：is_active=false 的供应商不创建任务
    """
    pass
```

### 10.4 响应测试

#### TC-SKILL-RESP-001: 返回处理中消息

```python
def test_response_processing():
    """
    测试：用户提交后返回处理中消息
    预期：包含"正在处理中"等提示
    """
    pass
```

#### TC-SKILL-RESP-002: 返回错误消息

```python
def test_response_error():
    """
    测试：处理失败时返回错误消息
    预期：友好提示错误原因
    """
    pass
```

---

## 11. 端到端测试

### 11.1 完整流程测试

#### TC-E2E-001: 完整成功流程

```python
async def test_complete_success_flow():
    """
    测试：完整的成功流程
    1. 用户发送消息
    2. 系统解析意图和材料
    3. 创建会话、材料、任务
    4. 提交到供应商
    5. 轮询获取结果
    6. 下载并上传TOS
    7. 发送汇总通知
    
    预期：用户收到成功通知，包含下载链接
    """
    pass
```

#### TC-E2E-002: 部分供应商失败

```python
async def test_partial_failure_flow():
    """
    测试：部分供应商失败的流程
    场景：3个供应商，1个失败，2个成功
    
    预期：通知中显示成功和失败的结果
    """
    pass
```

#### TC-E2E-003: 全部供应商失败

```python
async def test_all_failure_flow():
    """
    测试：全部供应商失败的流程
    
    预期：通知中说明所有任务失败
    """
    pass
```

#### TC-E2E-004: 超时处理

```python
async def test_timeout_handling():
    """
    测试：任务超时处理
    场景：供应商任务超过 timeout_minutes 未完成
    
    预期：
        - status 更新为 "timeout"
        - 发送超时通知
    """
    pass
```

### 11.2 异常流程测试

#### TC-E2E-005: 图片下载失败

```python
async def test_image_download_failure():
    """
    测试：图片下载失败处理
    
    预期：
        - 记录错误日志
        - 任务状态更新为 failed
        - 通知用户
    """
    pass
```

#### TC-E2E-006: TOS上传失败

```python
async def test_tos_upload_failure():
    """
    测试：TOS上传失败处理
    
    预期：
        - 重试机制
        - 记录错误日志
        - 通知用户
    """
    pass
```

#### TC-E2E-007: 飞书通知发送失败

```python
async def test_feishu_notify_failure():
    """
    测试：飞书通知发送失败处理
    
    预期：
        - 重试机制
        - 不影响任务状态
    """
    pass
```

---

## 12. 测试数据准备

### 12.1 Mock 数据总结

| 数据类型 | 用途 |
|----------|------|
| MOCK_VENDOR_CONFIG | 供应商配置 |
| MOCK_SUCCESS_RESPONSE | 成功响应 |
| MOCK_RUNNING_RESPONSE | 运行中响应 |
| MOCK_FAILURE_RESPONSE | 失败响应 |
| MOCK_SESSION | 会话数据 |
| MOCK_MATERIAL | 材料数据 |
| MOCK_SUMMARY | 汇总报告 |

### 12.2 Mock 汇总数据

```python
MOCK_SUMMARY = {
    "event": "all_vendors_completed",
    "session_uuid": "sess_test_001",
    "summary": {
        "total_vendors": 3,
        "succeeded": 2,
        "failed": 1,
        "total_time_seconds": 245
    },
    "results": [
        {
            "vendor_name": "豆包Seed3D",
            "vendor_id": "vendor_ark_seed3d",
            "status": "succeeded",
            "file_format": "glb",
            "share_url": "https://tos.example.com/...",
            "download_expires": "2026-04-24 12:00:00"
        },
        {
            "vendor_name": "影眸 Hyper3D",
            "vendor_id": "vendor_ark_yingmou",
            "status": "succeeded",
            "file_format": "glb",
            "share_url": "https://tos.example.com/...",
            "download_expires": "2026-04-24 12:00:00"
        },
        {
            "vendor_name": "数美 Hitem3D",
            "vendor_id": "vendor_ark_shumei",
            "status": "failed",
            "error_code": "IMAGE_TOO_SMALL",
            "error_message": "图片分辨率过低"
        }
    ],
    "materials": {
        "type": "image",
        "count": 1,
        "preview_url": "https://example.com/input.jpg"
    }
}
```
