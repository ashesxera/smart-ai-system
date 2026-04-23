---
name: ai-3d-modeling
description: |
  AI-3D Modeling System - 3D model generation from images/text via vendor APIs
  激活关键词: 3D, 三维, 建模, 生成模型, obj, glb, stl, make 3d, generate model, create model
alwaysActive: false
---

# AI-3D Modeling System

## 简介

AI-3D 建模系统，接收用户的图片或文字描述，调用供应商 API 生成 3D 模型。

**当前状态：需要配置 TOS AK/SK 后方可运行**

## 为何不使用 HTTP 服务？

部分开发者可能注意到项目中存在 `skill/__main__.py`（HTTP 服务版本），
但当前实际使用的是 `skill/standalone.py`（直接调用版本）。

**原因：**

1. **OpenClaw 内部触发 Skill**
   - 飞书消息由 OpenClaw 的 channel 插件接收（openclaw 进程）
   - 消息被转换为内部事件，注入到 AI 对话中
   - AI 根据 SKILL.md 指引，直接调用 Python 函数
   - 不需要独立的 HTTP 服务来接收外部事件

2. **简化架构**
   - poller 进程负责轮询供应商 API 获取结果
   - 无需服务端推送机制
   - 减少部署和维护复杂度

3. **直接调用更自然**
   - AI 在对话中直接处理请求
   - 用户体验更流畅
   - 调试更容易

## 工作流程

```
用户发消息 (飞书)
    ↓
OpenClaw 接收消息
    ↓
AI 激活 Skill，读取 SKILL.md
    ↓
AI 解析意图，直接调用 skill/standalone.py
    ↓
创建任务记录 → poller 轮询 → 通知用户
```

## 核心接口

### handle_user_message (推荐)

处理用户消息的便捷入口函数，AI 直接调用：

```python
from ai_3d_modeling.skill.standalone import handle_user_message

result = await handle_user_message(
    message_text="生成一个3D模型",
    sender_id="ou_xxx",
    sender_name="用户名",
    chat_id="",  # 私聊为空，群聊为群 ID
    message_id="om_xxx",
    images=[]    # 可选，图片 URL 列表
)
```

返回值：
```python
{
    'success': True,
    'session_uuid': 'sess_xxx',
    'message': '已收到您的请求，正在处理中...',
    'phase': 'processing',
    'tasks_count': 3
}
```

### 其他便捷函数

```python
from ai_3d_modeling.skill.standalone import (
    process_modeling_request,  # 处理建模请求
    process_cancel_request,    # 处理取消请求
    process_status_request,    # 处理状态查询
    get_help_text              # 获取帮助文本
)
```

## 意图识别

函数内部自动识别以下意图：

| 意图 | 关键词 | 处理 |
|------|--------|------|
| 3D建模 | 3D/建模/生成/模型 等 | 创建建模任务 |
| 取消 | 取消/停止/cancel 等 | 取消任务 |
| 状态 | 状态/进度/status 等 | 返回进度 |
| 帮助 | 帮助/help 等 | 返回帮助文本 |

## 激活关键词

当用户消息包含以下关键词时，AI 会激活此技能：
- 3D、三维、建模、生成模型
- obj、glb、stl、usdz
- make 3d、generate model、create model

## 配置要求

| 变量名 | 说明 | 必需 |
|--------|------|------|
| TOS_ACCESS_KEY | TOS Access Key | ✅ |
| TOS_SECRET_KEY | TOS Secret Key | ✅ |
| FEISHU_APP_ID | 飞书 App ID | ✅ |
| FEISHU_APP_SECRET | 飞书 App Secret | ✅ |
| DB_PATH | 数据库路径 | 否 (默认 ./data/ai-3d-modeling.db) |

## 项目结构

```
skill/
├── __init__.py      # 已弃用，HTTP 服务版本
├── __main__.py      # 已弃用，HTTP 服务入口
└── standalone.py     # 当前使用，直接被 OpenClaw 调用
```

## 数据库表

- `sessions`：用户会话
- `materials`：材料记录
- `vendor_tasks`：供应商任务
- `results`：结果记录

## 供应商

当前活跃供应商：
- 豆包Seed3D (vendor_ark_seed3d)
- 影眸 Hyper3D (vendor_ark_yingmou)
- 数美 Hitem3D (vendor_ark_shumei)

## 状态码

| code | 说明 |
|------|------|
| 0 | 成功 |
| 40001 | 请求参数错误 |
| 50001 | 服务器内部错误 |

## 故障排查

1. **任务提交失败**：检查 Ark API Key 是否配置
2. **图片处理失败**：检查飞书 App ID/Secret 是否配置
3. **TOS 上传失败**：检查 TOS AK/SK 是否配置
4. **通知发送失败**：检查 Gateway URL 是否可达

## 文件路径

- 项目根目录：`/root/smart-ai-system`
- 源码：`/root/smart-ai-system/src/ai_3d_modeling`
- 数据库：`./data/ai-3d-modeling.db`
- 日志：`./logs/ai-3d-modeling.log`
