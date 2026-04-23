# AI-3D Modeling System

基于 Volcengine Ark 3D API 的多供应商 AI 3D 建模平台

## 项目结构

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

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 初始化数据库

```bash
python -m ai_3d_modeling.db.init
```

### 运行轮询守护进程

```bash
python -m ai_3d_modeling.poller
```

## 模块说明

### adapters - 模板驱动适配器

支持通过配置文件定义新的供应商，无需修改代码：

```json
{
  "name": "新供应商",
  "endpoint": "https://api.example.com/submit",
  "request_template": {"model": "${model}", "content": ${content}},
  "response_parser": {"task_id": "$.id", "status": "$.status"}
}
```

### db - 数据库模块

SQLite 数据库，提供会话、材料、任务、结果管理。

### poller - 轮询模块

60秒批量轮询，检查供应商任务状态。

### storage - 存储模块

TOS 文件上传下载、生成下载链接。

### notifier - 通知模块

多供应商结果汇总、飞书卡片通知。

## 测试

```bash
# 运行所有测试
pytest tests/

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 查看测试覆盖率
pytest --cov=ai_3d_modeling tests/
```

## 设计文档

- [系统设计 v3.0](./docs/ai-3d-modeling-system-design-v3.md)
- [项目模块设计](./docs/project-module-design-v1.md)
- [单元测试设计](./docs/unit-test-design-v1.md)
