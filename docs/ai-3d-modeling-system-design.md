# AI-3D 建模系统设计方案

## 文档信息
- 版本：v2.0
- 更新说明：v2.0 - 简化轮询设计，采用批量轮询；多供应商结果汇总模式

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

```
用户提交一个请求
    |
    └── session (会话)
            |
            ├── materials (材料 - 图片/文字)
            |
            └── [vendor_task_1, vendor_task_2, vendor_task_3] (3个供应商任务)
                    |
                    ├── Vendor A 结果 -|
                    ├── Vendor B 结果 -|---> 汇总报告 -> 用户
                    └── Vendor C 结果 -|
```

**通知策略：等所有供应商完成后，发送汇总报告给用户**

---

## 2. 数据库设计 (v2.0)

### 表结构总览

| 表名 | 说明 |
|------|------|
| sessions | 用户会话表 |
| materials | 材料表 |
| vendor_tasks | 供应商任务表 |
| results | 结果表 |
| ops_log | 操作日志表 |

### sessions 表

| 字段 | 类型 | 说明 |
|------|------|------|
| session_uuid | TEXT | 会话唯一ID |
| channel_type | TEXT | 渠道类型 |
| channel_user_id | TEXT | 用户ID |
| channel_user_name | TEXT | 用户名称 |
| group_id | TEXT | 群ID |
| status | TEXT | active/completed |
| phase | TEXT | pending/processing/completed |
| created_at | INTEGER | 创建时间 |

### vendor_tasks 表

| 字段 | 类型 | 说明 |
|------|------|------|
| vendor_task_uuid | TEXT | 任务唯一ID |
| session_uuid | TEXT | 关联会话 |
| material_uuid | TEXT | 关联材料 |
| vendor_id | TEXT | 供应商ID |
| vendor_name | TEXT | 供应商名称 |
| status | TEXT | pending/queued/running/succeeded/failed |
| poll_count | INTEGER | 轮询次数 |
| last_poll_at | INTEGER | 最后轮询时间 |

### results 表

| 字段 | 类型 | 说明 |
|------|------|------|
| result_uuid | TEXT | 结果唯一ID |
| vendor_task_uuid | TEXT | 关联任务 |
| file_name | TEXT | 文件名 |
| file_size | INTEGER | 文件大小 |
| tos_path | TEXT | TOS存储路径 |
| share_url | TEXT | 分享链接 |

---

## 3. 简化轮询设计

### 设计原则

**结果完整性 > 实时性**

- 不需要独立轮询 + next_poll_at
- 不需要动态间隔调整
- 简单批量轮询，60秒间隔

### 轮询逻辑

```python
async def poll():
    while True:
        tasks = db.get_all_running_tasks()
        
        for task in tasks:
            result = await api.query_task(task['vendor_task_id'])
            db.update_status(task['vendor_task_uuid'], result['status'])
            
            if result['status'] == 'succeeded':
                await handle_success(task, result)
            elif result['status'] in ['failed', 'timeout']:
                await handle_failure(task, result)
        
        for session_uuid in get_active_sessions():
            if check_all_vendors_done(session_uuid):
                await send_summary_notification(session_uuid)
        
        await asyncio.sleep(60)
```

### 核心区别

| | 之前设计 (v1.0) | 现在 (v2.0) |
|---|---|---|
| 轮询方式 | 独立轮询 + next_poll_at | 简单批量轮询 |
| 间隔 | 动态间隔 (20s/30s) | 固定间隔 (60s) |
| 实时性 | 高 | 中等 |
| 复杂度 | 高 | 低 |

---

## 4. 多供应商结果汇总

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

### 飞书消息卡片

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": { "tag": "plain_text", "content": "3D 模型生成完成 (2/3 成功)" },
      "template": "green"
    },
    "elements": [
      { "tag": "div", "fields": [
        { "is_short": true, "text": { "tag": "lark_md", "content": "**豆包Seed3D**\n成功 (1.2MB)" }},
        { "is_short": true, "text": { "tag": "lark_md", "content": "**影眸 Hyper3D**\n成功 (2.3MB)" }}
      ]},
      { "tag": "action", "actions": [
        { "tag": "button", "text": { "tag": "plain_text", "content": "下载" }, "url": "${url}" }
      ]}
    ]
  }
}
```

---

## 5. TOS 存储设计

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
