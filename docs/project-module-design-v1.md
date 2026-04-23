# AI-3D 建模系统 - 项目模块文档

## 文档信息
- 版本：v1.1.0
- 创建时间：2026-04-23
- 更新说明：v1.1 - 补充 notifier 和 skill 模块详细设计
- 基于设计：ai-3d-modeling-system-design-v3.md

---

## 1. 项目概述

### 1.1 项目结构

```
ai_3d_modeling/
├── adapters/          # API 适配器模块（模板驱动）
├── poller/            # 轮询守护进程
├── storage/           # TOS 存储模块
├── notifier/          # 通知模块
├── skill/             # 飞书 Skill 模块
├── db/                # 数据库模块
├── utils/             # 工具模块
└── main.py            # 入口文件
```

### 1.2 模块依赖关系

```
Skill -> DB -> Adapters <-> Poller
              |              |
              v              v
           Storage     <- Notifier
```

---

## 2. adapters 模块

### 2.1 模块说明

**职责**：模板驱动的 API 适配器，负责构建请求、解析响应

**核心类**：
- `TemplateRequestBuilder` - 请求构建器
- `TemplateResponseParser` - 响应解析器
- `BaseAdapter` - 适配器基类
- `AdapterFactory` - 适配器工厂

### 2.2 类图

```
AdapterFactory
├── register(name, adapter_class)
├── create(vendor_config) -> BaseAdapter
└── get_active_vendors() -> list

BaseAdapter
├── config: dict
├── request_builder: TemplateRequestBuilder
├── response_parser: TemplateResponseParser
├── build_request(material) -> dict
├── parse_response(response) -> dict
└── get_auth_headers() -> dict

TemplateRequestBuilder
├── build(vendor_config, material) -> dict
├── _build_content(vendor_config, material) -> list
└── _substitute(obj, variables) -> any

TemplateResponseParser
├── parse(vendor_config, response) -> dict
└── _extract(data, path) -> any
```

---

## 3. db 模块

### 3.1 模块说明

**职责**：SQLite 数据库操作封装

**核心类**：
- `Database` - 数据库连接和操作类
- `SessionManager` - 会话管理
- `MaterialManager` - 材料管理
- `VendorTaskManager` - 供应商任务管理
- `ResultManager` - 结果管理

### 3.2 表结构

| 表名 | 说明 |
|------|------|
| sessions | 用户会话表 |
| materials | 材料表 |
| vendor_tasks | 供应商任务表 |
| results | 结果表 |
| ops_log | 操作日志表 |
| settings | 配置表（供应商配置） |

---

## 4. poller 模块

### 4.1 模块说明

**职责**：批量轮询守护进程，定期检查供应商任务状态

**核心类**：
- `Poller` - 轮询主类

### 4.2 轮询流程

```
start()
    │
    ▼
while running:
    │
    ├─> 1. get_running_tasks()
    │
    ├─> 2. for each task:
    │       - check_status()
    │       - if succeeded: handle_success()
    │       - if failed: handle_failure()
    │
    ├─> 3. check_all_sessions_done()
    │       - if all vendors done: send_summary()
    │
    └─> 4. sleep(interval)
```

---

## 5. storage 模块

### 5.1 模块说明

**职责**：TOS 文件存储管理

**核心类**：
- `StorageManager` - 存储管理器

### 5.2 目录结构

```
tos://4-ark-claw/ai-3d-system/sessions/{session_uuid}/
├── materials/
│   └── {material_uuid}.{ext}
└── results/
    └── {vendor_id}.{format}
```

---

## 6. notifier 模块

### 6.1 模块说明

**职责**：汇总多供应商结果，发送飞书通知

**核心类**：
- `ResultSummarizer` - 结果汇总器
- `FeishuNotifier` - 飞书通知器

### 6.2 类图

```
ResultSummarizer
├── db: Database
├── summarize(session_uuid) -> dict
├── check_all_done(session_uuid) -> bool
├── calculate_duration(session_uuid) -> int
└── build_materials_preview(session_uuid) -> dict

FeishuNotifier
├── gateway_url: str
├── send_summary(session_key, summary) -> bool
├── build_card(summary) -> dict
└── send(session_key, card) -> bool
```

### 6.3 汇总报告格式

```python
{
    "event": "all_vendors_completed",
    "session_uuid": "sess-xxx",
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
            "share_url": "https://...",
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

### 6.4 核心方法

#### ResultSummarizer.summarize()

```python
def summarize(self, session_uuid: str) -> dict:
    """
    汇总会话的所有供应商结果
    
    Args:
        session_uuid: 会话UUID
    
    Returns:
        汇总报告字典
    """
    # 1. 获取所有任务
    tasks = self.db.vendor_tasks.get_by_session(session_uuid)
    
    # 2. 统计结果
    summary = {
        "total_vendors": len(tasks),
        "succeeded": sum(1 for t in tasks if t['status'] == 'succeeded'),
        "failed": sum(1 for t in tasks if t['status'] == 'failed'),
    }
    
    # 3. 构建结果列表
    results = []
    for task in tasks:
        result = {
            "vendor_name": task['vendor_name'],
            "vendor_id": task['vendor_id'],
            "status": task['status'],
        }
        
        if task['status'] == 'succeeded':
            result.update({
                "file_format": self._extract_format(task),
                "share_url": task['share_url'],
                "download_expires": self._format_expires(task['share_expires_at'])
            })
        else:
            result.update({
                "error_code": task['error_code'],
                "error_message": task['error_message']
            })
        
        results.append(result)
    
    return {
        "event": "all_vendors_completed",
        "session_uuid": session_uuid,
        "summary": summary,
        "results": results
    }
```

#### FeishuNotifier.build_card()

```python
def build_card(self, summary: dict) -> dict:
    """
    构建飞书消息卡片
    
    Args:
        summary: 汇总报告
    
    Returns:
        飞书卡片格式的字典
    """
    # 构建成功结果元素
    success_elements = []
    fail_elements = []
    
    for r in summary['results']:
        if r['status'] == 'succeeded':
            success_elements.append({
                "tag": "div",
                "text": f"✅ {r['vendor_name']} - {r['file_format']}"
            })
        else:
            fail_elements.append({
                "tag": "div", 
                "text": f"❌ {r['vendor_name']} - {r['error_message']}"
            })
    
    # 构建卡片
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "🎉 3D建模完成"},
                "template": "green" if summary['summary']['succeeded'] > 0 else "red"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "plain_text", "content": f"成功: {summary['summary']['succeeded']} | 失败: {summary['summary']['failed']}"}}
            ]
        }
    }
    
    return card
```

---

## 7. skill 模块

### 7.1 模块说明

**职责**：飞书 Skill 入口，解析用户意图、提取材料、创建任务

**核心函数**：
- `handle_message(event)` - 消息处理入口
- `parse_intent(text)` - 解析用户意图
- `extract_materials(event)` - 提取材料
- `create_session(event)` - 创建会话
- `submit_vendor_tasks(session_uuid, material)` - 提交供应商任务

### 7.2 类图

```
SkillHandler
├── db: Database
├── handle_message(event) -> dict
├── parse_intent(text) -> str
├── extract_materials(event) -> dict
└── submit_vendor_tasks(session_uuid, material) -> list

IntentParser
├── AI_3D_PATTERNS: list[str]
├── CANCEL_PATTERNS: list[str]
├── parse(text) -> str
└── is_3d_modeling_request(text) -> bool

MaterialExtractor
├── extract_from_text(text) -> str
├── extract_from_images(event) -> list[str]
└── extract(event) -> dict
```

### 7.3 意图类型

| 意图 | 说明 | 关键词 |
|------|------|--------|
| `3d_modeling` | 3D建模请求 | 生成、建模、3D模型 |
| `cancel` | 取消请求 | 取消、撤销 |
| `status` | 查询状态 | 状态、进度 |
| `other` | 其他 | - |

### 7.4 处理流程

```
收到消息
    │
    ▼
parse_intent() -> 判断是否为3D建模请求
    │
    ├── intent == "3d_modeling"
    │       │
    │       ▼
    │   extract_materials() -> 提取图片/文字
    │       │
    │       ▼
    │   create_session() -> 创建会话记录
    │       │
    │       ▼
    │   submit_vendor_tasks() -> 提交给各供应商
    │       │
    │       ▼
    │   返回处理中消息
    │
    ├── intent == "cancel"
    │       │
    │       ▼
    │   取消进行中的任务
    │
    └── intent == "other"
            │
            ▼
        返回帮助信息
```

### 7.5 核心方法

#### parse_intent()

```python
def parse_intent(text: str) -> str:
    """
    解析用户消息意图
    
    Args:
        text: 用户消息文本
    
    Returns:
        意图类型: "3d_modeling" | "cancel" | "status" | "other"
    """
    text_lower = text.lower()
    
    # 检查取消意图
    cancel_keywords = ['取消', '撤销', '停止', 'cancel', 'abort']
    for kw in cancel_keywords:
        if kw in text_lower:
            return "cancel"
    
    # 检查3D建模意图
    modeling_keywords = ['3d', '建模', '生成', '模型', '三维', 'obj', 'glb', 'stl']
    for kw in modeling_keywords:
        if kw in text_lower:
            return "3d_modeling"
    
    return "other"
```

#### extract_materials()

```python
def extract_materials(event: dict) -> dict:
    """
    从事件中提取材料（图片和文字）
    
    Args:
        event: 飞书事件字典，包含 content, image_keys 等
    
    Returns:
        材料字典，包含 image_urls 和 text_content
    """
    result = {
        "image_urls": [],
        "text_content": ""
    }
    
    # 1. 提取文字描述
    if event.get('content'):
        result['text_content'] = event['content'].strip()
    
    # 2. 提取图片URL
    if event.get('image_keys'):
        for key in event['image_keys']:
            url = download_image(key)  # 下载图片到本地或TOS
            result['image_urls'].append(url)
    
    return result
```

#### submit_vendor_tasks()

```python
def submit_vendor_tasks(session_uuid: str, material: dict) -> list:
    """
    向所有活跃供应商提交任务
    
    Args:
        session_uuid: 会话UUID
        material: 材料字典
    
    Returns:
        创建的供应商任务列表
    """
    # 1. 获取所有活跃供应商
    vendors = AdapterFactory.get_active_vendors()
    
    tasks = []
    for vendor in vendors:
        # 2. 检查材料是否满足供应商要求
        if len(material.get('image_urls', [])) > vendor.get('max_images', 1):
            continue
        
        # 3. 创建任务
        task_uuid = generate_uuid('task')
        adapter = AdapterFactory.create(vendor)
        
        # 4. 构建请求
        request_body = adapter.build_request(material)
        
        # 5. 发送到供应商
        response = await adapter.submit(request_body)
        
        # 6. 解析响应，获取 vendor_task_id
        parsed = adapter.parse_response(response)
        
        # 7. 保存任务记录
        task = db.vendor_tasks.create(
            vendor_task_uuid=task_uuid,
            session_uuid=session_uuid,
            material_uuid=material['material_uuid'],
            vendor_id=vendor['id'],
            vendor_name=vendor['name'],
            model_name=vendor['model'],
            api_endpoint=vendor['endpoint'],
            api_request_body=json.dumps(request_body)
        )
        
        # 8. 更新 vendor_task_id
        db.vendor_tasks.set_vendor_task_id(task_uuid, parsed['vendor_task_id'])
        
        tasks.append(task)
    
    return tasks
```

---

## 8. utils 模块

### 8.1 模块说明

**职责**：通用工具函数

**核心函数**：
- `generate_uuid(prefix)` - 生成UUID
- `get_timestamp()` - 获取时间戳
- `format_duration(seconds)` - 格式化时长
- `parse_content_type(url)` - 解析内容类型

---

## 9. 配置管理

### 9.1 供应商配置存储

所有供应商配置存储在 `settings` 表：

```sql
SELECT * FROM settings WHERE category = 'vendor' AND is_active = 1;
```

### 9.2 动态加载

```python
def load_vendor_configs() -> list:
    """从数据库加载所有活跃供应商配置"""
    configs = db.execute('''
        SELECT * FROM settings 
        WHERE category = 'vendor' 
        AND value LIKE '%"is_active": true%'
    ''')
    return [json.loads(c['value']) for c in configs]
```
