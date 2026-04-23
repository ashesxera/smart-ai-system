# AI-3D 建模系统 - 项目模块文档

## 文档信息
- 版本：v1.0.0
- 创建时间：2026-04-23
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

### 2.2 核心方法

#### TemplateRequestBuilder.build()

```python
def build(self, vendor_config: dict, material: dict) -> dict:
    # 1. 构建 content 数组
    content = self._build_content(vendor_config, material)
    
    # 2. 准备变量
    variables = {
        'model': vendor_config['model'],
        'content': json.dumps(content),
        'text_content': material.get('text_content', ''),
        **{f'image_url_{i}': url 
           for i, url in enumerate(material.get('image_urls', []))},
    }
    
    # 3. 递归替换模板中的变量
    request_template = vendor_config.get('request_template', {})
    return self._substitute(request_template, variables)
```

#### TemplateResponseParser.parse()

```python
def parse(self, vendor_config: dict, response: dict) -> dict:
    parser_config = vendor_config['response_parser']
    
    result = {}
    for field, path in parser_config.items():
        result[field] = self._extract(response, path)
    
    # 映射状态
    raw_status = result.get('status')
    status_map = vendor_config.get('status_map', {})
    result['status'] = status_map.get(raw_status, raw_status)
    
    return result
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

---

## 7. skill 模块

### 7.1 模块说明

**职责**：飞书 Skill 入口，解析用户意图、提取材料、创建任务

### 7.2 处理流程

```
收到消息
    │
    ▼
parse_intent() -> 判断是否为3D建模请求
    │
    ▼
extract_materials() -> 提取图片/文字
    │
    ▼
create_session() -> 创建会话记录
    │
    ▼
submit_vendor_tasks() -> 提交给各供应商
    │
    ▼
返回处理中消息给用户
```

---

## 8. utils 模块

### 8.1 模块说明

**职责**：通用工具函数

**核心函数**：
- `generate_uuid()` - 生成UUID
- `get_timestamp()` - 获取时间戳
- `format_duration(seconds)` - 格式化时长
- `parse_content_type(url)` - 解析内容类型
