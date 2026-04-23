# AI-3D 建模系统 - 部署文档

## 文档信息
- 版本：v1.0.0
- 创建时间：2026-04-23
- 说明：系统部署和运维指南

---

## 1. 系统要求

### 1.1 运行环境

| 项目 | 要求 |
|------|------|
| 操作系统 | Linux (Ubuntu 20.04+) / macOS |
| Python | 3.10+ |
| 内存 | 最小 512MB，推荐 2GB+ |
| 磁盘 | 最小 1GB |

### 1.2 依赖服务

| 服务 | 说明 | 必需 |
|------|------|------|
| SQLite | 数据库 | ✅ |
| TOS | 文件存储 | ✅ |
| 飞书 | 消息通知 | ✅ |
| Volcengine Ark API | 3D建模服务 | ✅ |

---

## 2. 项目结构

```
ai-3d-modeling/
├── src/
│   └── ai_3d_modeling/     # 主程序
├── tests/                   # 测试
├── docs/                    # 文档
├── config/                  # 配置文件
├── data/                    # 数据目录（数据库等）
├── logs/                    # 日志目录
├── scripts/                 # 脚本
│   ├── init_db.py          # 数据库初始化
│   └── run_poller.py       # 轮询守护进程启动
└── requirements.txt         # Python 依赖
```

---

## 3. 安装步骤

### 3.1 克隆代码

```bash
git clone https://github.com/ashesxera/smart-ai-system.git
cd smart-ai-system
```

### 3.2 创建虚拟环境

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3.3 安装依赖

```bash
pip install -r requirements.txt
```

### 3.4 配置环境变量

```bash
# 复制环境变量模板
cp config/.env.example config/.env

# 编辑配置
vim config/.env
```

```bash
# config/.env 内容
TOS_ACCESS_KEY=your_access_key
TOS_SECRET_KEY=your_secret_key
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
```

### 3.5 初始化数据库

```bash
python -m ai_3d_modeling.db.init
```

---

## 4. 运行方式

### 4.1 启动轮询守护进程

```bash
# 前台运行
python -m ai_3d_modeling.poller

# 后台运行
nohup python -m ai_3d_modeling.poller > logs/poller.log 2>&1 &

# 使用 systemd
sudo systemctl start ai-3d-poller
```

### 4.2 启动 Skill 服务

```bash
# 前台运行
python -m ai_3d_modeling.skill

# 后台运行
nohup python -m ai_3d_modeling.skill > logs/skill.log 2>&1 &
```

---

## 5. Docker 部署（推荐）

### 5.1 Dockerfile

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# 创建目录
RUN mkdir -p data logs

# 环境变量
ENV PYTHONPATH=/app
ENV CONFIG_PATH=/app/config/config.yaml

CMD ["python", "-m", "ai_3d_modeling.poller"]
```

### 5.2 docker-compose.yml

```yaml
version: '3.8'

services:
  ai-3d-poller:
    build: .
    container_name: ai-3d-poller
    restart: unless-stopped
    environment:
      - TOS_ACCESS_KEY=${TOS_ACCESS_KEY}
      - TOS_SECRET_KEY=${TOS_SECRET_KEY}
      - FEISHU_APP_ID=${FEISHU_APP_ID}
      - FEISHU_APP_SECRET=${FEISHU_APP_SECRET}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    command: python -m ai_3d_modeling.poller

  ai-3d-skill:
    build: .
    container_name: ai-3d-skill
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - TOS_ACCESS_KEY=${TOS_ACCESS_KEY}
      - TOS_SECRET_KEY=${TOS_SECRET_KEY}
      - FEISHU_APP_ID=${FEISHU_APP_ID}
      - FEISHU_APP_SECRET=${FEISHU_APP_SECRET}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    command: python -m ai_3d_modeling.skill
```

### 5.3 启动

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f ai-3d-poller

# 停止
docker-compose down
```

---

## 6. 系统服务配置

### 6.1 systemd 服务文件

```bash
# /etc/systemd/system/ai-3d-poller.service

[Unit]
Description=AI-3D-Modeling Poller Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/ai-3d-modeling
ExecStart=/opt/ai-3d-modeling/venv/bin/python -m ai_3d_modeling.poller
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 启用服务
sudo systemctl daemon-reload
sudo systemctl enable ai-3d-poller
sudo systemctl start ai-3d-poller
```

---

## 7. 监控和日志

### 7.1 日志位置

```
logs/
├── ai-3d-modeling.log     # 主日志
├── poller.log             # 轮询日志
└── skill.log              # Skill 日志
```

### 7.2 日志级别

| 级别 | 说明 |
|------|------|
| DEBUG | 详细信息（开发环境） |
| INFO | 一般信息 |
| WARNING | 警告 |
| ERROR | 错误 |

### 7.3 健康检查

```bash
# 检查进程状态
ps aux | grep ai_3d_modeling

# 检查端口监听
netstat -tlnp | grep 8000

# 检查数据库连接
sqlite3 data/ai-3d-modeling.db "SELECT COUNT(*) FROM sessions;"
```

---

## 8. 数据备份

### 8.1 数据库备份

```bash
# 备份
cp data/ai-3d-modeling.db "data/backup/ai-3d-modeling-$(date +%Y%m%d).db"

# 压缩
tar -czf "data/backup-$(date +%Y%m%d).tar.gz" data/
```

### 8.2 定时备份 (crontab)

```bash
# 每天凌晨3点备份
0 3 * * * /opt/ai-3d-modeling/scripts/backup.sh
```

---

## 9. 升级流程

```bash
# 1. 停止服务
sudo systemctl stop ai-3d-poller

# 2. 拉取新代码
cd /opt/ai-3d-modeling
git pull origin main

# 3. 更新依赖
pip install -r requirements.txt

# 4. 运行数据库迁移（如有）
python -m ai_3d_modeling.db.migrate

# 5. 重启服务
sudo systemctl start ai-3d-poller
```

---

## 10. 故障排查

### 10.1 常见问题

| 问题 | 可能原因 | 解决方案 |
|------|----------|----------|
| 任务提交失败 | API Key 错误 | 检查配置 |
| 轮询无响应 | 网络问题 | 检查防火墙 |
| 数据库锁定 | 并发写入 | 重启服务 |
| TOS 上传失败 | 权限问题 | 检查 AK/SK |

### 10.2 调试模式

```bash
# 设置日志级别为 DEBUG
export LOG_LEVEL=DEBUG
python -m ai_3d_modeling.poller
```

---

## 11. 目录权限

```bash
# 设置目录权限
chown -R www-data:www-data /opt/ai-3d-modeling
chmod -R 755 /opt/ai-3d-modeling
chmod -R 700 /opt/ai-3d-modeling/config/.env
```
