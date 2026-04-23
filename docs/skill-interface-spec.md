# AI-3D 建模系统 - Skill 接口规范

## 文档信息
- 版本：v1.0.0
- 创建时间：2026-04-23
- 说明：飞书 Skill 事件输入输出格式定义

---

## 1. 概述

### 1.1 模块位置

```
src/ai_3d_modeling/skill/__init__.py
```

### 1.2 入口函数

```python
async def handle_event(event: dict) -> dict:
    """
    处理飞书事件
    
    Args:
        event: 飞书事件字典
    
    Returns:
        响应字典
    """
    pass
```

---

## 2. 输入事件格式

### 2.1 用户文本消息事件

```python
{
    "schema": "feishu.event.message",
    "header": {
        "event_id": "evt_123456789",
        "event_type": "im.message.receive_v1",
        "create_time": "1704067200000",
        "token": "xxx",
        "app_id": "cli_xxx",
        "tenant_key": "xxx"
    },
    "event": {
        "sender": {
            "sender_id": {
                "open_id": "ou_xxx",
                "union_id": "un_xxx",
                "user_id": "xxx"
            },
            "sender_type": "user",
            "tenant_key": "xxx"
        },
        "recipient": {
            "chat_id": "oc_xxx",
            "recipient_id": {
                "open_id": "ou_yyy"
            }
        },
        "message": {
            "message_id": "om_xxx",
            "root_id": "",
            "parent_id": "",
            "create_time": "1704067200000",
            "chat_id": "oc_xxx",
            "chat_type": "group",  # group 或 p2p
            "message_type": "text",
            "content": "{\"text\":\"生成一个3D模型\"}"
        }
    }
}
```

### 2.2 用户图片消息事件

```python
{
    "schema": "feishu.event.message",
    "header": {...},
    "event": {
        "sender": {...},
        "message": {
            "message_id": "om_xxx",
            "chat_id": "oc_xxx",
            "chat_type": "group",
            "message_type": "image",
            "content": "{\"image_key\":\"img_xxx\"}",
            "media": {
                "file_key": "boxAPi/xxx",
                "file_name": "image.jpg",
                "file_size": 123456
            }
        }
    }
}
```

### 2.3 卡片交互事件

```python
{
    "schema": "feishu.event.interactive",
    "header": {...},
    "event": {
        "action": {
            "action_tag": "btn_download",
            "value": "{\"task_id\":\"task_xxx\"}"
        },
        "message": {
            "message_id": "om_xxx"
        },
        "operator": {
            "operator_id": {
                "open_id": "ou_xxx"
            }
        }
    }
}
```

---

## 3. 输出响应格式

### 3.1 成功响应（处理中）

```python
{
    "code": 0,
    "msg": "success",
    "data": {
        "session_uuid": "sess_abc123",
        "message": "已收到您的请求，正在处理中...",
        "phase": "processing"
    }
}
```

### 3.2 成功响应（汇总完成）

```python
{
    "code": 0,
    "msg": "success",
    "data": {
        "session_uuid": "sess_abc123",
        "message": "处理完成",
        "phase": "completed",
        "summary": {
            "total_vendors": 3,
            "succeeded": 2,
            "failed": 1
        }
    }
}
```

### 3.3 错误响应

```python
{
    "code": 40001,
    "msg": "参数错误：未检测到图片或文字描述",
    "data": None
}
```

### 3.4 飞书消息卡片响应

```python
{
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {"tag": "plain_text", "content": "🎉 3D建模完成"},
            "template": "green"
        },
        "elements": [
            {"tag": "div", "text": {"tag": "plain_text", "content": "成功: 2 | 失败: 1"}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "plain_text", "content": "✅ 豆包Seed3D - glb"}},
            {"tag": "div", "text": {"tag": "plain_text", "content": "📥 下载链接: https://..."}},
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "plain_text", "content": "❌ 数美 Hitem3D - 图片分辨率过低"}}
        ]
    }
}
```

---

## 4. 意图识别

### 4.1 意图类型

| 意图 | 说明 | 优先级 |
|------|------|--------|
| `3d_modeling` | 3D建模请求 | 1 |
| `cancel` | 取消请求 | 1 |
| `status` | 查询状态 | 2 |
| `help` | 帮助信息 | 3 |
| `other` | 其他 | 4 |

### 4.2 关键词匹配

```python
# 3D建模意图关键词
MODELING_KEYWORDS = [
    '3d', '三维', '建模', '生成', '模型', 'obj', 'glb', 'stl',
    'make 3d', 'generate model', 'create model'
]

# 取消意图关键词
CANCEL_KEYWORDS = [
    '取消', '撤销', '停止', 'cancel', 'abort', 'stop'
]

# 状态查询关键词
STATUS_KEYWORDS = [
    '状态', '进度', '怎么样了', '完成了吗', 'status', 'progress'
]

# 帮助关键词
HELP_KEYWORDS = [
    '帮助', 'help', '怎么用', '使用说明'
]
```

---

## 5. 材料提取

### 5.1 提取规则

| 消息类型 | 提取内容 | 示例 |
|----------|----------|------|
| text | text_content | 用户输入的文字描述 |
| image | image_urls | 用户发送的图片 |
| mixed | text_content + image_urls | 文字+图片混合 |

### 5.2 图片数量限制

```python
# 默认限制
DEFAULT_MAX_IMAGES = 4

# 按供应商限制
MAX_IMAGES_BY_VENDOR = {
    'vendor_ark_seed3d': 1,
    'vendor_ark_yingmou': 5,
    'vendor_ark_shumei': 4,
}
```

---

## 6. 会话状态机

```
                    ┌─────────────┐
                    │   pending   │
                    └──────┬──────┘
                           │
              用户提交 ──────┼────── 用户取消
                           ▼
                    ┌─────────────┐
            ┌───────│ processing  │───────┐
            │       └─────────────┘       │
            │              │              │
      所有供应商完成      超时           错误
            │              │              │
            ▼              ▼              ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │  completed  │ │   timeout   │ │   failed    │
    └─────────────┘ └─────────────┘ └─────────────┘
```

### 6.1 状态说明

| 状态 | 说明 | 可能的下一状态 |
|------|------|---------------|
| `pending` | 等待处理 | processing, cancelled |
| `processing` | 处理中 | completed, failed, timeout |
| `completed` | 完成 | - |
| `failed` | 失败 | - |
| `timeout` | 超时 | - |
| `cancelled` | 已取消 | - |

---

## 7. 错误码定义

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 40001 | 参数错误 |
| 40002 | 素材无效 |
| 40003 | 不支持的格式 |
| 40101 | 未授权 |
| 40301 | 禁止访问 |
| 50001 | 服务器内部错误 |
| 50002 | 供应商API错误 |
| 50003 | 存储服务错误 |

---

## 8. API 端点

### 8.1 Skill 事件接收

```
POST /skill/ai-3d-modeling
```

### 8.2 Webhook 状态回调（可选）

```
POST /webhook/status
```

---

## 9. 示例场景

### 9.1 纯文字请求

**用户输入**: "帮我生成一个卡通人物的3D模型"

**系统行为**:
1. 解析意图 = `3d_modeling`
2. 提取 text_content = "卡通人物"
3. 提取 image_urls = []
4. 创建会话
5. 向供应商提交任务
6. 返回 "正在处理中..."

### 9.2 图片+文字请求

**用户输入**: [图片] + "生成同款造型"

**系统行为**:
1. 解析意图 = `3d_modeling`
2. 提取 text_content = "生成同款造型"
3. 提取 image_urls = ["https://..."]
4. 创建会话 + 材料
5. 向供应商提交任务
6. 返回 "正在处理中..."

### 9.3 取消请求

**用户输入**: "取消刚才的请求"

**系统行为**:
1. 解析意图 = `cancel`
2. 查询用户最近的 pending/processing 会话
3. 更新会话状态 = `cancelled`
4. 返回 "已取消"
