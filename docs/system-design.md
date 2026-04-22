# Smart AI 任务系统设计文档

## 文档信息
- 版本：v3.2
- 创建时间：2026-04-20
- 更新时间：2026-04-22
- 状态：架构设计阶段

---

## 1. 系统概述

### 1.1 系统用途

Smart AI 任务系统是一个**通用异步AI任务处理平台**，通过多种渠道（飞书、企业微信等）接收用户请求，自动化完成AI任务（3D建模、音频生成、视频生成等）的提交、跟踪和结果推送。

### 1.2 核心功能

| 功能 | 说明 |
|------|------|
| 多渠道接入 | 支持飞书、企业微信等多种用户渠道 |
| 对话式交互 | 通过对话接收用户任务需求 |
| 意图识别 | 自动识别用户想要的AI任务类型 |
| 需求引导 | 逐步引导用户提交必要的素材和参数 |
| 智能推荐 | 根据需求推荐最合适的供应商 |
| 自动化处理 | 自动提交任务、跟踪状态、下载结果 |
| 消息推送 | 任务完成后自动推送结果通知 |

### 1.3 支持的任务类型

| 任务类型 | task_type | 示例Vendor |
|----------|-----------|------------|
| 3D建模 | 3d_model | Meshy.AI、火山引擎、Tripo3D |
| 音频生成 | audio | TTS、语音合成（规划中） |
| 视频生成 | video | 视频生成、AI剪辑（规划中） |

---

## 2. 设计理念

### 2.1 基础与应用分离

系统采用**分层架构**，将通用的基础设施能力（任务队列、轮询、存储、通知、日志）与上层的业务逻辑（对话理解、任务编排）分离。

**好处**：
- 通用能力只需实现一次，各任务类型复用
- 新增任务类型只需编写适配器，无需改动基础设施
- 便于维护和测试

### 2.2 数据完整追溯

所有任务相关数据（材料、成品、操作过程）完整记录，便于审计和问题排查。

### 2.3 轻量级部署

在资源有限的服务器环境下（双核4G RAM），使用 SQLite 而非 Redis 等额外服务，降低部署复杂度。

### 2.4 与 OpenClaw 集成

系统充分利用 OpenClaw 的能力：
- 消息接入：利用 OpenClaw 消息能力接入多渠道用户
- 意图理解：利用 OpenClaw LLM 能力进行语义理解
- 消息推送：利用 OpenClaw 发送通知
- 文件处理：利用 OpenClaw 处理文件上传下载

### 2.5 可迁移性

- 配置化：数据库连接、TOS配置、供应商配置均可配置
- 模块化：核心逻辑与 OpenClaw 集成层分离
- 可独立部署：后台进程可独立部署，不绑定 OpenClaw 实例

---

## 3. 核心概念

### 3.1 业务模型

```
委托人 ─── 1:N ─── 材料 ─── M:N ─── 任务 ─── N:1 ─── 供应商
```

### 3.2 术语定义

| 术语 | 英文 | 说明 |
|------|------|------|
| 委托人 | Delegator | 提交任务的用户，抽象多渠道 |
| 材料 | Material | 委托的材料（含语义理解+资源+参数） |
| 任务 | Task | 材料委托给供应商生产的AI产品 |
| 供应商 | Vendor | AI服务供应商（供应商+模型） |

### 3.3 材料定义

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

### 3.4 解耦设计

| 角色 | 职责 | 不关心 |
|------|------|--------|
| 委托人 | 提交材料、查看状态、获取结果 | 具体用哪个供应商 |
| 供应商 | 接收材料、处理、返回结果 | 谁提交的 |
| 系统 | 匹配调度、状态跟踪、结果分发 | - |

---

## 4. 系统架构

### 4.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                    OpenClaw 集成层                                    │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐   ┌───────────┐  │
│  │  消息接入  │   │ Skill调用  │   │  消息推送  │   │  文件处理  │  │
│  │(飞书/企微)│   │(对话理解) │   │(飞书/企微)│   │           │  │
│  └───────────┘   └───────────┘   └───────────┘   └───────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      对话理解层（OpenClaw Skill）                    │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  ai-task-understanding Skill                                 │  │
│  │  • LLM 对话理解                                            │  │
│  │  • 戳记机制（开始/结束）                                   │  │
│  │  • 引导用户提供材料                                        │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │       戳记消息 (桥梁)        │
                    │ 【📍会话开始 task-xxx】      │
                    │ 【📍会话结束 task-xxx】      │
                    └───────────────┬───────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        后台任务层                                    │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    常驻进程（20秒轮询）                      │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │ 戳记扫描 │ 材料解析 │ 任务创建 │ 供应商选择 │ 通知  │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         数据库层                                    │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐                 │
│  │delegators │   │ materials │   │   tasks  │                 │
│  └───────────┘   └───────────┘   └───────────┘                 │
│  ┌───────────┐   ┌───────────┐   ┌───────────┐                 │
│  │ai_vendors │   │operations│   │ settings │                 │
│  └───────────┘   └───────────┘   └───────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```
```

### 4.2 分层说明

| 层级 | 说明 |
|------|------|
| OpenClaw 集成层 | 消息接入、Skill调用、消息推送、文件处理 |
| 对话理解层 | OpenClaw Skill 对话理解，戳记机制（开始/结束） |
| 后台任务层 | 常驻进程轮询（戳记扫描、材料解析、任务创建、供应商选择、通知推送） |
| 数据库层 | 持久化存储（TOS网盘、AI供应商为外部依赖） |

**数据流**：
```
用户消息 → OpenClaw → Skill → 戳记消息 → 后台扫描 → 解析材料 → 创建任务 → 数据库
```

---

## 5. 模块说明

### 5.1 消息接入模块

#### 功能
接收来自多渠道（飞书、企业微信等）的用户消息和文件。

#### 设计方案
- 利用 OpenClaw 消息能力接入
- 支持私聊和群聊
- 支持文件上传

#### 消息来源
| 渠道 | 消息类型 |
|------|----------|
| 飞书 | 文本、图片、文件 |
| 企业微信 | 文本、图片、文件 |

---

### 5.2 对话理解模块（OpenClaw Skill）

#### 功能
通过 OpenClaw Skill 实现多轮对话，理解用户需求并引导收集材料。

#### 架构设计

```
用户消息 → OpenClaw Skill → LLM 对话理解 → 引导回复
                                         ↓
                                  等待用户确认
                                         ↓
                              用户确认 → 后台进程创建任务
```

#### Skill 设计

```yaml
name: ai-task-understanding
description: 理解用户AI任务需求，引导收集材料

input: 用户消息 + 历史上下文
output: 引导回复 + 材料收集状态
```

#### 职责说明（v3 方案）

| 职责 | 说明 |
|------|------|
| 对话理解 | LLM 生成引导回复 |
| 戳记管理 | 生成/发送开始和结束戳记，不直接写数据库 |

**注意（v3）**：
- Skill 只负责对话理解和戳记，不处理文件（下载/上传），文件处理交给后台进程
- Skill **不直接写 materials 表**，而是通过戳记消息告知后台进程
- 后台进程扫描 session 文件，检测戳记后解析材料创建任务

#### 触发机制

采用 **LLM 自主判断 + 戳记机制**，不依赖关键词匹配。

| 阶段 | 触发条件 | 说明 |
|------|----------|------|
| 第1次 | LLM 判断用户有创建任务意图 | 用户说"帮我做3D"等 → Skill 生成 task_id，发送开始戳记 |
| 中间每次 | 每条消息 | 用户每条消息都触发 Skill，继续对话 |
| 最后1次 | LLM 判断材料完备 | 用户说"没有了"等 → Skill 发送结束戳记 |

**核心流程**：
1. Skill 收到用户消息，LLM 判断意图
2. 需要开始 → 生成 UUID 作为 task_id，发送【📍会话开始 task-xxx】
3. 对话收集材料过程中，Skill 引导用户提供完整信息
4. LLM 判断材料完备 → 发送【📍会话结束 task-xxx】现在开始准备任务
5. 后台进程扫描 session 文件，检测到结束戳记后解析材料创建任务

#### 对话历史管理

```
用户：帮我做3D模型 → OpenClaw 触发 Skill
Skill：【📍会话开始 task-abc123】请问...
用户：做一只猫 → OpenClaw 触发 Skill（带历史）
Skill：请提供图片参考
用户：[上传图片]
用户：没有了 → OpenClaw 触发 Skill（带历史）
Skill：【📍会话结束 task-abc123】现在开始准备任务
    ↓
后台进程扫描 session：
  - 检测到结束戳记 task-abc123
  - 解析从开始戳记到结束戳记之间的消息
  - 提取材料 → 创建任务
```

**关键点**：
- OpenClaw 自动管理对话历史
- 每次触发 Skill，OpenClaw 发送从第一次触发开始的完整对话
- Skill 不直接写数据库，通过戳记消息告知后台处理
- 后台进程负责解析 session 文件提取材料

#### 结束处理（v3 方案）

v3 方案中，Skill **不直接写入数据库**，而是通过戳记消息告知后台处理：

```python
def handle_confirm(user_message, history):
    # 1. 生成 task_id（UUID）
    task_id = generate_uuid()  # 如 task-abc123def
    
    # 2. 返回带结束戳记的消息
    reply = f"【📍会话结束 {task_id}】现在开始准备任务"
    
    return reply
    # 后台进程会扫描 session 文件，检测到戳记后自动创建任务
```

**与 v2 方案的区别**：
- v2：Skill 解析对话历史，直接写入 materials 表
- v3：Skill 发送戳记消息，由后台进程扫描 session 文件提取材料

#### Skill 传递给后台的数据结构

**注意**：v3 方案不再需要此数据结构，材料由后台进程从 session 文件中解析提取。

#### 对话流程示例（v3 方案）

```
用户：我想做个3d模型
Skill：【📍会话开始 task-a1b2】请问想做什么东西的模型？

用户：做一只猫
Skill：请提供图片参考，可以上传图片或提供图片URL

用户：没有图片
Skill：请描述一下这只猫的外观，比如颜色、体型、神态等

用户：胖乎乎的白猫，竖着尾巴
Skill：好的，还有其他补充吗？说"没有了"结束提交

用户：没有了
Skill：【📍会话结束 task-a1b2】现在开始准备任务
```

**流程说明**：
1. 用户表达意图 → Skill 生成 task_id，发送开始戳记
2. 对话收集材料 → Skill 引导用户提供完整信息
3. 用户表示完成 → Skill 发送结束戳记
4. 后台进程检测到结束戳记 → 解析材料 → 创建任务

#### LLM Prompt 设计（v3 方案）

```python
DIALOGUE_PROMPT = """
你是 Smart AI 任务助手，负责引导用户收集材料。

## 判断逻辑

当用户想要创建任务时，你需要判断当前处于哪个阶段：

### 阶段1：用户表达意图（开始）
- 用户说"帮我做个3D模型"、"我想生成视频"等
→ 生成 task_id（UUID格式，如 task-abc123）
→ 回复带开始戳记："【📍会话开始 {task_id}】请问..."

### 阶段2：收集材料
- 用户上传图片、描述、URL 等
→ 继续引导或确认

### 阶段3：材料完备（结束）
- 用户说"没有了"、"好了"、"就这些"等
- 或者用户明确表示材料都给了
→ 回复带结束戳记："【📍会话结束 {task_id}】现在开始准备任务"

### 阶段4：取消
- 用户说"不做了"、"算了"、"取消"等
→ 礼貌回复，不发送戳记

## 输出格式

请直接输出回复内容，不需要 JSON 格式。
"""
```

**注意**：
- task_id 使用 UUID 格式（如 task-a1b2c3d4e5f6）
- 开始和结束戳记使用同一个 task_id
- 戳记消息由后台进程扫描检测，用于提取材料
```

#### 供应商自动选择（后台进程）

对话确认后，后台进程自动选择供应商：

```python
def select_vendor(task_type, materials):
    """
    根据材料和任务类型自动选择供应商 - 规则算法
    """
    # 1. 获取支持的供应商（按优先级排序）
    vendors = db.query("""
        SELECT * FROM ai_vendors 
        WHERE task_type = ? AND is_active = 1
        ORDER BY priority DESC
    """, task_type)
    
    # 2. 检查素材是否支持
    for vendor in vendors:
        if supports_materials(vendor, materials):
            if is_available(vendor):
                return vendor
    
    # 3. 返回默认供应商
    return get_default_vendor(task_type)
```

**说明**：
- 供应商选择用规则算法，不调用 LLM
- 根据素材类型、供应商支持情况、优先级自动匹配
- 用户无需关心具体使用哪个供应商

---

### 5.2.1 材料收集方案v3（自动扫描版）

**背景**：v2方案使用标记文件方式存在并发处理的问题。v3方案改为自动扫描session文件，通过戳记机制实现更简洁可靠的材料收集。

#### 核心思路

```
用户：帮我做3D模型
       ↓
Skill（LLM判断）→ 生成 task_id → 回复：【📍会话开始 task-abc123】请问...
       ↓
用户：做一只猫 + 上传图片
       ↓
Skill（LLM判断）→ 识别材料完备 → 回复：【📍会话结束 task-abc123】现在开始准备任务
       ↓
后台扫描 → 检测到结束戳记 → 解析材料 → 创建任务（task_id=task-abc123）
```

#### 核心设计

| 设计点 | 说明 |
|--------|------|
| **戳记生成** | Skill 生成 UUID 作为 task_id，成对出现在开始/结束消息中 |
| **LLM 判断** | 通过提示词让 OpenClaw 自主判断何时发戳记，不依赖关键词 |
| **自动扫描** | 后台进程自动发现活跃 session，增量读取新消息 |
| **去重机制** | 已处理的 task_id 记录到 SQLite，避免重复 |
| **群聊支持** | 每个用户有独立 task_id，互不干扰 |

#### 戳记格式

```python
# 开始戳记
【📍会话开始 task-abc123def】请问想做什么？

# 结束戳记
【📍会话结束 task-abc123def】现在开始准备任务
```

- task_id：UUID 格式（如 task-a1b2c3d4e5f6），贯穿整个流程

#### Skill 提示词设计

```markdown
# 你的职责

你是 Smart AI 任务助手，负责引导用户收集材料。

## 判断逻辑

当用户想要创建任务时，你需要判断当前处于哪个阶段：

### 阶段1：用户表达意图（开始）
- 用户说"帮我做个3D模型"、"我想生成视频"等
→ 回复带开始戳记：`【📍会话开始 {task_id}】请问...`

### 阶段2：收集材料
- 用户上传图片、描述、URL 等
→ 继续引导或确认

### 阶段3：材料完备（结束）
- 用户说"没有了"、"好了"、"就这些"等
- 或者用户明确表示材料都给了
→ 回复带结束戳记：`【📍会话结束 {task_id}】现在开始准备任务`

### 阶段4：取消
- 用户说"不做了"、"算了"、"取消"等
→ 礼貌回复，不发送戳记
```

#### 群聊场景支持

```
群会话（session_id = abc）
├── 用户A：开始3D
├── Skill：【📍会话开始 task-A1】请问...
├── 用户B：开始建模
├── Skill：【📍会话开始 task-B2】请问...
├── 用户A：[图片A] + 没有了
├── Skill：【📍会话结束 task-A1】现在开始准备任务
└── 用户B：[图片B] + 没有了
    Skill：【📍会话结束 task-B2】现在开始准备任务
```

每个用户有独立的 task_id，后台按戳记 ID 隔离处理，互不干扰。

#### 后台进程设计

##### 1. 获取活跃 Session

```python
import glob
from pathlib import Path

def get_active_sessions(hours=1):
    """获取最近修改的 session 文件"""
    sessions_dir = Path("/root/.openclaw/agents/main/sessions")
    pattern = str(sessions_dir / "*.jsonl")
    files = glob.glob(pattern)
    
    recent_files = []
    for f in files:
        mtime = os.path.getmtime(f)
        if is_recent(mtime, hours=hours):
            recent_files.append({"path": f, "mtime": mtime})
    
    return recent_files
```

##### 2. 增量读取

```python
# 记录每个文件的读取位置
file_positions = {}  # {file_path: last_size}

def read_new_lines(file_path):
    """只读取文件新增的内容"""
    current_size = os.path.getsize(file_path)
    last_size = file_positions.get(file_path, 0)
    
    if current_size <= last_size:
        return []
    
    with open(file_path, 'r') as f:
        f.seek(last_size)
        new_content = f.read()
    
    file_positions[file_path] = current_size
    
    lines = new_content.strip().split('\n')
    return [json.loads(line) for line in lines if line]
```

##### 3. 戳记检测与去重

```python
import re

MARKER_PATTERN = re.compile(r"【📍会话开始 (task-[a-zA-Z0-9]+)】")
END_PATTERN = re.compile(r"【📍会话结束 (task-[a-zA-Z0-9]+)】")

# 已处理的戳记（持久化到 SQLite）
processed_markers = set()

def extract_markers(text):
    """提取戳记"""
    start_match = MARKER_PATTERN.search(text)
    end_match = END_PATTERN.search(text)
    return start_match.group(1) if start_match else None, \
           end_match.group(1) if end_match else None
```

##### 4. 材料解析

```python
def extract_materials(session_file, task_id):
    """从戳记位置解析到文件末尾，提取材料"""
    messages = read_all_messages(session_file)
    
    # 找到结束戳记位置
    end_idx = None
    user_id = None
    for i, msg in enumerate(messages):
        content = msg.get("content", "")
        if f"【📍会话结束 {task_id}】" in content:
            end_idx = i
            user_id = msg["sender"]["user_id"]
            break
    
    if end_idx is None:
        return None
    
    # 找到开始戳记位置
    start_idx = None
    for i, msg in enumerate(messages):
        if f"【📍会话开始 {task_id}】" in msg.get("content", ""):
            start_idx = i
            break
    
    # 解析该用户戳记之间的材料
    materials = []
    for msg in messages[start_idx:end_idx]:
        if msg["sender"]["user_id"] != user_id:
            continue
        
        # 解析文本、图片、URL...
        # ...
    
    return materials
```

##### 5. 主循环

```python
def poll_worker():
    """主轮询循环"""
    while True:
        try:
            active_sessions = get_active_sessions(hours=1)
            
            for session in active_sessions:
                new_messages = read_new_lines(session["path"])
                
                for msg in new_messages:
                    content = msg.get("content", "")
                    _, end_marker = extract_markers(content)
                    
                    if not end_marker:
                        continue
                    if is_processed(end_marker):
                        continue
                    
                    # 解析材料并创建任务
                    materials = extract_materials(session["path"], end_marker)
                    create_task(task_id=end_marker, materials=materials)
                    
                    mark_as_processed(end_marker)
        
        except Exception as e:
            print(f"错误: {e}")
        
        time.sleep(20)  # 20秒轮询间隔
```

#### 已处理戳记存储

```sql
CREATE TABLE processed_markers (
    marker_id TEXT PRIMARY KEY,
    task_id TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 定期清理（保留7天）
DELETE FROM processed_markers WHERE processed_at < datetime('now', '-7 days');
```

#### 配置参数

```sql
INSERT INTO settings (key, value, description) VALUES
('scan_session_hours', '1', '扫描最近几小时的session文件'),
('poll_interval_seconds', '20', '轮询间隔'),
('marker_retention_days', '7', '戳记保留天数');
```

#### 方案对比

| 方案 | v1（Skill解析） | v2（标记文件） | v3（自动扫描） |
|------|----------------|---------------|---------------|
| 材料提取 | Skill 解析对话历史 | 后台读取 session | 后台自动扫描 |
| 触发方式 | 关键词 | 标记文件 | 戳记消息 |
| 并发处理 | 差 | 一般 | 好 |
| 群聊支持 | 差 | 差 | 好 |
| 复杂度 | 低 | 中 | 中 |

#### 适用场景

- **v1 方案**：简单对话、纯文本材料
- **v2 方案**：需要附件、图片等富媒体材料（已废弃）
- **v3 方案**：需要附件、图片，且支持群聊并发

---

### 5.3 材料解析模块

#### 功能
从 session JSONL 文件中提取任务段落，生成 semantic.md，解析资源文件并上传到 TOS，解析 API 参数，更新数据库。

#### 处理流程

```
后台进程轮询（20秒）
        ↓
1. 全量扫描所有 session JSONL 文件
        ↓
2. 找到【📍任务开始 task-xxx】到【📍任务结束 task-xxx】之间的文本
        ↓
3. 生成 semantic.md（原始对话文本）
        ↓
4. 解析附件路径（提取 [media attached: xxx]）
        ↓
5. 上传资源到 TOS，生成 presign URL
        ↓
6. 解析 API 参数（使用 LLM），保存 api_params.json
        ↓
7. 更新 materials 表记录
        ↓
8. 创建 tasks 表记录
```

##### 5.3.1 扫描 session 文件

- **扫描范围**：所有 `*.jsonl` 文件（排除 `.lock` 和 `.reset` 后缀）
- **扫描方式**：每次轮询全量扫描
- **负载评估**：100 任务/天约 50ms 扫描时间，可接受

```python
def scan_session_files():
    session_dir = "/root/.openclaw/agents/main/sessions/"
    for f in glob.glob(f"{session_dir}*.jsonl"):
        if ".lock" in f or ".reset" in f:
            continue
        process_session_file(f)
```

##### 5.3.2 提取任务段落

- **查找戳记**：搜索 "【📍任务开始" 和 "【📍任务结束"
- **提取 task_id**：从戳记中解析 UUID
- **提取对话**：两个戳记之间的所有文本

```
semantic.md 内容示例：
【📍任务开始 task-xxx】
用户：帮我做个3D模型
助手：好的，请上传一张图片
用户：[上传了图片]
助手：图片收到了，正在生成3D模型...
【📍任务结束 task-xxx】
```

##### 5.3.3 去重处理

- **去重方式**：比对数据库 tasks 表，找出不存在的 task_id
- **流程**：
  1. 扫描所有 session，找出所有 task_id
  2. 查询数据库，找出已存在的 task_id
  3. 取差集，找出需要处理的新任务

```python
def get_new_tasks():
    all_task_ids = scan_all_session_files()
    existing = db.query("SELECT task_id FROM tasks")
    existing_set = set([r['task_id'] for r in existing])
    return all_task_ids - existing_set
```

##### 5.3.4 解析附件路径

从对话文本中提取附件路径：

```
格式：[media attached: /root/.openclaw/media/inbound/xxx.jpg (image/jpeg) | /path]
```

- 提取本地路径：正则匹配 `/root/.openclaw/media/inbound/`
- 文件类型：从 MIME 类型获取（如 image/jpeg）

##### 5.3.5 上传 TOS

- **目标路径**：`smart-ai-tasks/{task_id}/materials/{uuid}.{ext}`
- **presign URL**：有效期 1 天

##### 5.3.6 解析 API 参数

- **输入**：semantic.md 内容
- **方式**：使用 LLM 解析
- **输出**：api_params.json

```json
{
  "task_type": "3d_model",
  "model": "meshy-v2",
  "prompt": "将图片转换为3D模型",
  "format": "glb"
}
```

##### 5.3.7 更新数据库

1. **更新 materials 表**：
   - task_id
   - material_type（image/file/url）
   - source_type（channel_file/url/base64）
   - file_name
   - file_size
   - file_mime_type
   - resource_uuid
   - tos_path

2. **创建 tasks 表**：
   - task_id
   - vendor_id（选择供应商）
   - status = 'pending'

##### 5.3.8 与其他模块的关系

| 模块 | 交互 |
|------|------|
| 5.2 对话理解 | 触发：Skill 发送戳记，后台检测到后处理 |
| 5.4 后台处理 | 读取 materials 表，提交供应商 API |

---

### 5.4 后台任务处理模块

#### 功能
统一处理戳记扫描、材料解析、任务创建、供应商状态轮询。

#### 轮询设计

采用**常驻进程轮询**，20秒间隔：

| 处理对象 | 频率 | 说明 |
|----------|------|------|
| 戳记扫描 | 20秒 | 检测 session 文件中的结束戳记 |
| 材料解析 | 20秒 | 解析戳记间的用户材料 |
| 任务创建 | 20秒 | 创建任务并提交给供应商 |
| 状态轮询 | 3分钟 | 查询供应商状态（90次循环*20秒） |

#### 轮询逻辑

```python
def worker():
    counter = 0  # 循环计数器
    
    while True:
        counter += 1
        
        # 1. 戳记扫描（每次循环，20秒）
        scan_session_markers()
        
        # 2. 材料解析与任务创建（检测到结束戳记时）
        process_completed_markers()
        
        # 3. 每90次循环（约3分钟）查询一次供应商API
        if counter >= 90:
            counter = 0
            poll_vendor_status()
        
        sleep(20)  # 20秒周期
```

#### 部署配置

轮询进程配置：
```sql
-- 轮询配置
INSERT INTO settings (key, value, value_type, description, category) VALUES
('worker_cycle_seconds', '20', 'int', '轮询周期（秒）', 'worker'),
('api_poll_interval', '90', 'int', 'API轮询间隔（次数，90*20秒≈3分钟）', 'worker');
```

**说明**：
- worker_cycle_seconds：每次唤醒间隔，默认20秒
- api_poll_interval：每多少次循环查询一次API，默认90次（约3分钟）

---

### 5.5 存储管理模块

#### 功能
管理输入素材和输出成品的存储、下载、分享链接。

#### 目录结构
```
tos://{bucket}/
└─ smart-ai-tasks/
    └─ {task_id}/                         ← 任务级别
        ├─ materials/                    ← materials + resources 合并
        │   ├─ semantic.md               ← 原始会话内容
        │   ├─ api_params.json          ← API参数
        │   └─ {uuid}.ext               ← 输入文件
        │
        ├─ results/                     ← 输出文件
        │   └─ {default_filename}        ← 供应商返回的默认文件名
        │
        └─ summary.json                  ← 任务汇总信息
```

**设计说明**：
- materials 是 resources 的父集，1对1关系
- materials/ 目录下包含语义文件、API参数和输入文件
- semantic.md 保存原始会话内容，api_params.json 保存 API 参数
- results/ 保存供应商返回的输出文件

#### 文件命名规则

| 文件 | 命名来源 | 说明 |
|------|----------|------|
| 输入文件 | uuid | 本地生成，用于提交供应商 |
| 输出文件 | vendor返回的默认文件名 | 一个任务可能输出多个文件 |
| summary.json | 自动生成 | 任务完成时写入 |

#### summary.json 结构

```json
{
  "task_id": "task-abc123",
  "task_type": "3d_model",
  "status": "succeeded",
  "created_at": "2026-04-22T10:00:00Z",
  "finished_at": "2026-04-22T10:05:00Z",
  
  "user": {
    "user_id": "ou_xxx",
    "user_name": "张三",
    "channel_type": "feishu"
  },
  
  "vendor": {
    "name": "meshy",
    "model": "meshy-v2"
  },
  
  "materials": [
    {
      "task_id": "task-abc123",
      "material_type": "image",
      "file_name": "cat.jpg",
      "resource_uuid": "uuid-001",
      "path": "materials/uuid-001.jpg"
    }
  ],
  
  "results": [
    {
      "filename": "model.glb",
      "path": "results/model.glb"
    }
  ],
  
  "api": {
    "vendor_task_id": "vendor-xxx",
    "poll_count": 5
  }
}
```

#### URL资源处理

当用户提交的是外部URL时，统一下载保存到TOS：

| 方案 | 说明 |
|------|------|
| 推荐方案 | 下载保存到TOS，存实际文件 |

**处理流程**：
```
用户提交 URL
     ↓
下载到本地 /tmp/{uuid}.{ext}
     ↓
上传到 TOS: smart-ai-tasks/{task_id}/materials/{uuid}.ext
     ↓
生成 presign URL 供供应商调用
```

#### 分享方式

| 类型 | 方式 | 有效期 |
|------|------|--------|
| 输入素材 | presign URL | 24小时 |
| 输出成品 | presign URL | 24小时 |

#### 清理策略

| 类型 | 策略 |
|------|------|
| 本地临时文件 | 1小时后删除 |
| TOS输入/输出 | 永久保留（数据追溯要求） |

---

### 5.6 通知推送模块

#### 功能
通过多渠道向用户推送任务状态通知。

#### 通知类型

| 类型 | 触发 | 内容 |
|------|------|------|
| 任务已提交 | 用户提交成功 | 任务ID、预计等待时间 |
| 任务完成 | 轮询发现成功 | 下载链接 |
| 任务失败 | 轮询发现失败 | 失败原因、建议 |
| 任务超时 | 轮询超时 | 超时提示、建议重新提交 |

#### 发送方式

**方式1：OpenClaw Gateway Webhook（推荐）**
- 系统通过 OpenClaw Gateway 发送消息
- 配置简单，无需直接调用飞书/企微 API
- 消息通过 OpenClaw 机器人发送

**方式2：直接调用**
- 直接调用飞书/企业微信 API 发送消息
- 需要配置 API 凭证

#### 发送身份
- **发送身份**：OpenClaw 机器人（飞书/企业微信）
- **发送渠道**：原路返回
  - 私聊（DM）提交 → 私聊通知
  - 群里@机器人提交 → 群里通知

#### 重试机制
- **指数退避**：1分钟 → 2分钟 → 4分钟
- **最大重试次数**：3次（配置在 settings 表）
- **失败记录**：通知发送失败记录到 operations 表

#### 消息格式
飞书/企业微信消息卡片

---

### 5.7 日志记录模块

#### 功能
记录所有关键操作，用于审计和问题排查。

#### 记录范围

| 操作 | 是否记录 |
|------|----------|
| 材料创建 | ✅ |
| 任务创建 | ✅ |
| 任务状态变更 | ✅ |
| 供应商提交 | ✅ |
| 供应商轮询 | ✅ |
| TOS上传/下载 | ✅ |
| 通知发送 | ✅ |
| 错误发生 | ✅ |

#### 存储位置
operations 表（按 task_id 关联查询）

#### 日志级别

| 级别 | 用途 |
|------|------|
| INFO | 正常操作 |
| WARNING | 可恢复的错误 |
| ERROR | 严重错误 |

---

## 6. 数据库设计

### 6.1 表结构（7张）

| 表 | 说明 |
|---|------|
| delegators | 委托人表（多渠道用户） |
| materials | 材料表（已合并资源信息） |
| tasks | 任务表 |
| ai_vendors | 供应商表 |
| operations | 操作日志表 |
| settings | 系统配置表 |

### 6.2 ER关系

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

### 6.3 关系说明

| 关系 | 类型 | 说明 |
|------|------|------|
| 委托人 → 材料 | 1对多 | 一个委托人可提交多份材料 |
| 材料 → 任务 | 1对多 | 一份材料可分发给多个任务 |
| 任务 → 供应商 | 多对一 | 多个任务使用同一个供应商 |
| 材料 ↔ 供应商 | 多对多 | 通过任务连接 |

---

## 7. 业务流程

### 7.1 任务提交流程（v3 戳记机制）

```
用户消息
    ↓
OpenClaw Skill（LLM判断）
    ↓
用户表达意图 → Skill 发送【📍会话开始 task-xxx】
    ↓
用户上传材料（图片/文本/URL）
    ↓
用户表示完成 → Skill 发送【📍会话结束 task-xxx】
    ↓
后台进程扫描 session 文件：
  - 检测结束戳记
  - 解析戳记之间的材料
  - 创建任务
    ↓
返回任务创建成功
```

### 7.2 后台处理流程

```
常驻进程（20秒轮询）
    ↓
┌─────────────────────────────────────────┐
│ 每次循环（20秒）：                        │
│   - 扫描活跃 session 文件                │
│   - 检测戳记（开始/结束）               │
│   - 解析材料并创建任务                  │
│   - 每90次循环，查询一次 API 状态       │
└─────────────────────────────────────────┘
    ↓
任务完成 → 下载结果 → 通知用户
```
### 7.3 状态流转

```
pending → submitting → queued → running → succeeded
                              │           │
                              │           └──> failed
                              │
                              └──> cancelled / error / timeout
```

### 7.4 材料分发流程

```
一份材料 → 分发给多个供应商
    ↓
Task1 → Vendor1 → 结果1
    ↓
Task2 → Vendor2 → 结果2
    ↓
Task3 → Vendor3 → 结果3
    ↓
用户选择最佳结果
```

---

## 8. 部署说明

### 8.1 部署架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        服务器                                      │
│  ┌─────────────────┐                                            │
│  │   OpenClaw      │ ← 用户交互入口                             │
│  └─────────────────┘                                            │
│  ┌─────────────────┐                                            │
│  │ 常驻轮询进程    │ ← 戳记扫描、材料解析、任务创建、状态轮询  │
│  └─────────────────┘                                            │
│  ┌─────────────────┐                                            │
│  │   SQLite       │ ← 数据存储                                 │
│  └─────────────────┘                                            │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 进程管理

**常驻进程部署（推荐）**
```bash
# supervisor 配置
[program:smart-ai-poller]
command=python poller.py
directory=/opt/smart-ai
autostart=true
autorestart=true
stdout_logfile=/var/log/smart-ai-poller.log
```

### 8.3 配置说明

所有配置存储在 `settings` 表中：
```sql
-- 轮询配置
poll_interval_seconds: 20
api_poll_interval: 90
scan_session_hours: 1
marker_retention_days: 7

-- TOS配置
tos_bucket_name: 4-ark-claw

-- 通知配置
notification_retry_times: 3
```

---

## 9. 变更日志

### v3.2 (2026-04-22)
- 细化 5.3 材料解析模块：session扫描、任务段落提取、去重处理、附件解析

### v3.1 (2026-04-22)
- 5.3 改为材料解析模块：资源文件解析、上传TOS、解析API参数、更新数据库

### v3.0 (2026-04-22)
- 细化 5.3 任务队列模块：状态流转、代码示例、优先级调度

### v2.9 (2026-04-22)
- 同步最新数据库设计：删除 material_resources 表
- materials 表：material_id 改为 task_id，删除 status/semantic_path/api_params_path
- materials 表：resource_type 改为 material_type
- ER 图删除 material_resources
- summary.json 结构更新

### v2.8 (2026-04-22)
- 5.5 存储管理：目录结构 {material_id}/ 改为 materials/

### v2.7 (2026-04-22)
- 5.5 存储管理：修正目录结构，materials 和 resources 合并为 materials/

### v2.6 (2026-04-22)
- 5.5 存储管理：更新目录结构为 {task_id}/{material_id}/
- 新增 materials/ 目录：semantic.md + api_params.json
- 新增 resources/ 目录：可被多个 material 复用
- 新增 summary.json：任务汇总信息

### v2.5 (2026-04-22)
- 更新 7、8 章内容，与全文保持一致

### v2.4 (2026-04-22)
- 5.2 触发机制：改为 LLM 自主判断 + 戳记机制
- 5.2.1 材料收集方案：升级为 v3（自动扫描版）
- 架构图：戳记消息作为对话理解层和后台任务层的桥梁
- 移除 Cron 方案，统一为常驻进程轮询
- 新增前后台分离说明

### v2.3 (2026-04-21)
- 新增 Skill 触发机制说明（第1次关键词→每条消息触发→最后1次关键词）
- 新增对话历史管理说明（OpenClaw 自动管理，Skill 无状态）
- 新增最后一次触发处理逻辑（解析历史→写入数据库→清空历史）

### v2.2 (2026-04-21)
- Skill 只写 materials 表（status=pending），不创建 tasks
- 后台进程轮询 pending materials，创建 tasks 后标记 completed
- materials 表增加 status 字段

### v2.1 (2026-04-21)
- 对话理解层改为 OpenClaw Skill 实现
- Skill 只做对话理解 + 材料收集，不写数据库，不处理文件
- 后台进程负责创建任务、选择供应商、轮询、通知
- 供应商选择采用规则算法，不调用 LLM
- Skill 传递给后台的数据结构
- 统一高频轮询进程设计：20秒周期，90次循环查询一次API（约3分钟）

### v2.0 (2026-04-21)
- 架构升级为 5 层：OpenClaw集成层 + 对话理解层 + 任务编排层 + 后台任务层 + 数据库层
- 支持多渠道用户抽象（delegators表）
- 术语更新：apis → ai_vendors
- 术语更新：resources → materials
- 新增后台任务层，支持 Cron 和独立进程两种方案
- ER关系更新：委托人 → 材料 → 任务 → 供应商
- 材料支持对话语义（semantic字段）
- 结果支持多文件（result_files JSON字段）

### v1.0 (2026-04-20)
- 初始版本

---

## 10. 文件路径

- 文档版本：v2.8
- 最后更新：2026-04-22

---

## 参考文档

- `database-design.md` - 数据库设计方案（v3.3）
- `architecture-discussion-v2-2.md` - 架构讨论记录
