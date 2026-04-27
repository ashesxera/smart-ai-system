# AI-3D 建模系统 - 部署与迁移文档

## 文档信息
- 版本：v1.1.0
- 更新：2026-04-27
- 说明：系统部署、配置与运维指南

---

## 1. 环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Linux (Ubuntu 20.04+) / macOS |
| Python | 3.10+ |
| 依赖服务 | SQLite、TOS（字节对象存储）、Volcengine Ark API、OpenClaw Gateway |

---

## 2. 项目结构

```
smart-ai-system/
├── src/
│   └── ai_3d_modeling/     # 主程序包
│       ├── adapters/         # API 适配器（模板驱动）
│       ├── db/               # SQLite 数据库管理
│       ├── notifier/         # 通知模块（通过 OpenClaw Gateway 投递）
│       ├── poller/           # 轮询守护进程
│       ├── skill/            # 飞书 Skill 模块
│       ├── storage/          # TOS 存储管理
│       └── utils/            # 工具函数
├── scripts/
│   ├── init_db.py           # 数据库初始化
│   └── run_poller.py        # 轮询守护进程启动
├── tests/                    # 测试
├── docs/                     # 文档
├── data/                     # 数据目录（数据库文件）
├── .env                      # 环境变量配置（不提交 git）
└── requirements.txt          # Python 依赖
```

---

## 3. 环境变量配置

### 3.1 创建配置文件

项目根目录的 `.env` 文件包含所有密钥信息，**不提交 git**（已在 `.gitignore` 中排除）。

```bash
# 在项目根目录创建 .env
touch .env
```

### 3.2 配置内容

```bash
# ARK API 配置
ARK_API_KEY=ark-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# TOS 配置
TOS_ACCESS_KEY=AKLTxxxxxxxxxxxxxxxx
TOS_SECRET_ACCESS_KEY=TkRGak1qZ3lOak5rTTJaa05Ea3lZMkZoTTJJMVpHWXdObVUyTTJNelpqUQ==

# 飞书配置
FEISHU_APP_ID=cli_xxxxxxxxxxxxxxxx
FEISHU_APP_SECRET=

# OpenClaw Gateway 配置
GATEWAY_HOST=http://127.0.0.1:18789
GATEWAY_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3.3 配置说明

| 变量 | 来源 | 说明 |
|------|------|------|
| `ARK_API_KEY` | Volcengine Ark 控制台 | ARK API 访问密钥 |
| `TOS_ACCESS_KEY` | TOS 控制台 | 对象存储 Access Key |
| `TOS_SECRET_ACCESS_KEY` | TOS 控制台 | 对象存储 Secret Key（Base64 原始格式，**不要解码**） |
| `FEISHU_APP_ID` | 飞书开放平台 | 应用 App ID，格式 `cli_xxx` |
| `FEISHU_APP_SECRET` | 飞书开放平台 | 应用 App Secret（当前版本未使用） |
| `GATEWAY_HOST` | OpenClaw Gateway | Gateway 服务地址，本地部署为 `http://127.0.0.1:18789` |
| `GATEWAY_TOKEN` | OpenClaw 配置 | `/hooks/wake` 认证 Token，见 `openclaw.json` 中的 `hooks.token` |

### 3.4 获取 GATEWAY_TOKEN

```bash
# 从 OpenClaw 配置中获取
cat ~/.openclaw/openclaw.json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('hooks',{}).get('token','not found'))"
```

### 3.5 TOS Endpoint

TOS SDK 的 region 和 endpoint 对照：

| 区域 | Region | Endpoint |
|------|--------|----------|
| 北京 | `cn-beijing` | `tos-cn-beijing.volces.com` |

---

## 4. 飞书通知配置（关键）

### 4.1 为什么需要特殊配置

Notifier 模块不直接调飞书 API，而是通过 OpenClaw Gateway 的 `/hooks/wake` 接口注入通知 payload，由主会话（AI）自动调 `message tool` 投送给用户。

**完整链路：**
```
Poller 检测任务完成
  → Notifier.send_summary()
    → POST /hooks/wake (JSON payload)
      → Gateway 注入主会话
        → AI 收到 payload
          → 自动调 message tool
            → 飞书用户收到通知
```

### 4.2 SOUL.md 规则（必须）

**这是链路打通的关键。** 必须在 OpenClaw 主会话的 `SOUL.md` 中加入以下规则，使 AI 收到 `ai_3d_modeling.notification` 类型的 wake payload 时自动调 `message tool` 发送：

```markdown
## Notification Auto-Forward

When you receive a system message (injected via `/hooks/wake`) with `kind: "ai_3d_modeling.notification"`, automatically call the `message` tool to deliver the `text` content to the specified `channel` and `target`. Do not ask — just do it. The payload looks like:

```json
{"kind": "ai_3d_modeling.notification", "channel": "feishu", "target": "ou_xxx", "text": "..."}
```

- `channel`: the messaging channel (e.g. "feishu")
- `target`: the user or chat ID
- `text`: the notification content to deliver

Simply call `message(action=send, channel=<channel>, target=<target>, message=<text>)` and reply with NO_REPLY after sending.
```

### 4.3 验证通知链路

```bash
# 手动注入一条测试通知
curl -X POST http://127.0.0.1:18789/hooks/wake \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <GATEWAY_TOKEN>" \
  -d '{"text":"{\"kind\":\"ai_3d_modeling.notification\",\"channel\":\"feishu\",\"target\":\"<your_open_id>\",\"text\":\"测试消息\"}"}'

# 如果飞书收到消息，说明链路正常
```

---

## 5. 安装步骤

### 5.1 克隆代码

```bash
git clone https://github.com/ashesxera/smart-ai-system.git
cd smart-ai-system
```

### 5.2 安装 Python 依赖

```bash
# 安装到临时目录（用于测试）
pip install tos httpx pyyaml python-dateutil --target=/tmp/smart-ai-libs

# 或使用虚拟环境
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install tos
```

### 5.3 初始化数据库

```bash
source .env && python -m ai_3d_modeling.db.init
```

### 5.4 验证配置

```bash
# 验证 ARK API
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $ARK_API_KEY" \
  https://ark.cn-beijing.volces.com/api/v3/models

# 验证 TOS
PYTHONPATH=/tmp/smart-ai-libs python3 -c "
from tos.clientv2 import TosClientV2
import os, sys
with open('.env') as f:
    for l in f:
        l = l.strip()
        if l and not l.startswith('#') and '=' in l:
            k, v = l.split('=', 1)
            os.environ[k] = v
c = TosClientV2(ak=os.environ['TOS_ACCESS_KEY'], sk=os.environ['TOS_SECRET_ACCESS_KEY'], endpoint='tos-cn-beijing.volces.com', region='cn-beijing')
print('Buckets:', [b.name for b in c.list_buckets().buckets])
"
```

---

## 6. 运行

### 6.1 轮询守护进程

```bash
# 加载环境变量后运行
source .env && python -m ai_3d_modeling.poller

# 后台运行
nohup bash -c "source .env && python -m ai_3d_modeling.poller" > logs/poller.log 2>&1 &
```

### 6.2 Skill 服务

```bash
source .env && python -m ai_3d_modeling.skill
```

---

## 7. Docker 部署

### 7.1 Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir tos

COPY src/ ./src/
COPY scripts/ ./scripts/

RUN mkdir -p data logs

ENV PYTHONPATH=/app

CMD ["python", "-m", "ai_3d_modeling.poller"]
```

### 7.2 docker-compose.yml

```yaml
version: '3.8'
services:
  ai-3d-poller:
    build: .
    container_name: ai-3d-poller
    restart: unless-stopped
    environment:
      - ARK_API_KEY=${ARK_API_KEY}
      - TOS_ACCESS_KEY=${TOS_ACCESS_KEY}
      - TOS_SECRET_ACCESS_KEY=${TOS_SECRET_ACCESS_KEY}
      - FEISHU_APP_ID=${FEISHU_APP_ID}
      - GATEWAY_HOST=${GATEWAY_HOST}
      - GATEWAY_TOKEN=${GATEWAY_TOKEN}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    command: python -m ai_3d_modeling.poller
```

---

## 8. 升级流程

```bash
# 1. 停止轮询进程
pkill -f "ai_3d_modeling.poller"  # 或 systemctl stop ai-3d-poller

# 2. 拉取新代码
git pull origin main

# 3. 重新安装依赖（如有变更）
pip install -r requirements.txt
pip install tos

# 4. 重启服务
nohup bash -c "source .env && python -m ai_3d_modeling.poller" > logs/poller.log 2>&1 &
```

---

## 9. 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| TOS 签名错误 | Secret Key 格式不对 | Secret Key 填 Base64 原始字符串，不要解码 |
| TOS 连接超时 | Endpoint 错误 | 确认 region 为 `cn-beijing`，endpoint 为 `tos-cn-beijing.volces.com` |
| 通知未送达 | SOUL.md 未添加规则 | 按 4.2 节添加 Notification Auto-Forward 规则 |
| Hook 401 | GATEWAY_TOKEN 错误 | 重新从 `openclaw.json` 获取 token |
| 数据库路径错误 | 从不同目录运行脚本 | 使用绝对路径，脚本已自动基于项目根目录定位 |
