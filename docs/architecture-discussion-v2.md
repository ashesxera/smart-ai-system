# Smart AI 任务系统架构讨论记录 v2

## 讨论时间
2026-04-20 16:00 - 19:02

---

## 1. 系统架构（4层）

```
┌─────────────────────────────────────────────────────────┐
│  对话理解层（应用层）                                    │
│  • 意图识别 • 需求引导 • 智能推荐                       │
├─────────────────────────────────────────────────────────┤
│  任务编排层（应用层）                                    │
│  • 任务创建 • API适配器 • 成品处理                      │
├─────────────────────────────────────────────────────────┤
│  通用基础设施层（基础件）                                │
│  • 任务队列 • 状态轮询 • 存储管理 • 通知推送 • 日志    │
├─────────────────────────────────────────────────────────┤
│  数据库层                                                │
│  • tasks • resources • operations • settings • apis •  │
│    resources_tasks                                      │
└─────────────────────────────────────────────────────────┘
```

---

## 2. 数据库设计

### 表结构（6张）

| 表 | 说明 |
|---|------|
| tasks | 任务主表 |
| resources | 资源表（输入/输出） |
| resources_tasks | 资源-任务关联表（多对多） |
| operations | 操作日志表 |
| apis | API配置表 |
| settings | 系统配置表 |

### ER关系

```
resources (N) ───< resources_tasks >─── tasks (1) ───> apis (1)
    │                                              ▲
    │                                              │
    (N)                                            (N)
operations <──────────────────────────────────────┘
```

### 关系说明

- **tasks → apis**：多对一 (N)→(1) - 多个task使用同一个API
- **resources ↔ tasks**：多对多 (N)↔(N) - 一套素材可提交多个API产生多个task
- **tasks → operations**：一对多 (1)→(N) - 一个task多条操作日志

---

## 3. 任务队列管理

### 方案：SQLite

| 设计 | 说明 |
|------|------|
| 队列存储 | tasks表 |
| 待处理查询 | `WHERE status IN ('pending', 'queued') ORDER BY created_at ASC` |
| 优先级 | 按创建时间顺序，先到先处理 |

### 理由
- 任务量小（100条/天），SQLite完全够用
- 无需额外部署服务
- 4G RAM 虚拟机资源有限

---

## 4. 状态轮询

### 方案：独立进程 + 批量查询

| 设计 | 值 |
|------|-----|
| 轮询方式 | 后台独立进程 |
| 轮询间隔 | 3分钟（180秒） |
| 查询方式 | 批量查询（按api_id分组） |
| 并发处理 | 单进程串行 |

### 理由
- 3D生成任务通常需要几分钟，30秒查询太频繁
- 批量查询减少API调用次数

### 轮询逻辑

```python
while True:
    # 1. 获取所有活跃任务
    tasks = db.query("""
        SELECT task_id, api_task_id, api_id 
        FROM tasks 
        WHERE status IN ('pending', 'queued', 'running')
    """)
    
    if tasks:
        # 2. 批量查询（按api_id分组）
        api_groups = group_by(tasks, 'api_id')
        for api_id, group in api_groups.items():
            api_task_ids = [t.api_task_id for t in group]
            results = api.batch_query(api_id, api_task_ids)
            
            # 3. 更新状态
            for task_id, status in results.items():
                db.update_status(task_id, status)
    
    sleep(180)  # 3分钟
```

---

## 5. 存储管理

### 5.1 目录结构

```
tos://{bucket}/
└─ smart-ai-tasks/
    └── {task_id}/                        ← 本地任务ID（UUID）
        ├── resources/
        │   └─ {uuid}.ext                 ← 输入文件
        └── {api_task_id}.ext              ← 输出文件（API返回ID）
```

### 5.2 文件命名

| 文件 | 命名来源 | 说明 |
|------|----------|------|
| 输入文件 | uuid | 本地生成，用于提交API |
| 输出文件 | api_task_id | API返回，用于保存成品 |

### 5.3 分享方式

| 类型 | 方式 | 有效期 |
|------|------|--------|
| 输入素材 | presign URL | 24小时 |
| 输出成品 | presign URL | 24小时 |

### 5.4 清理策略

| 类型 | 策略 |
|------|------|
| 本地临时文件 | 1小时后删除 |
| TOS输入/输出 | 永久保留 |

---

## 6. 待讨论模块

- [x] 任务队列管理
- [x] 状态轮询
- [x] 存储管理
- [ ] 通知推送
- [ ] 日志记录

---

## 参考文档

- `database-design.md` - 数据库设计方案
- `architecture-discussion-v1.md` - 第一次讨论记录
