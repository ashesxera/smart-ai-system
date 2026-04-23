# AI-3D 建模系统 - 配置文件格式

## 文档信息
- 版本：v1.0.0
- 创建时间：2026-04-23
- 说明：系统配置文件格式定义

---

## 1. 配置目录结构

```
config/
├── config.yaml              # 主配置文件
├── vendors/                 # 供应商配置目录（可选）
│   ├── seed3d.yaml
│   ├── yingmou.yaml
│   └── shumei.yaml
└── .env                    # 环境变量（敏感信息）
```

---

## 2. 主配置文件 (config.yaml)

```yaml
# AI-3D 建模系统配置

app:
  name: "ai-3d-modeling"
  version: "1.0.0"
  environment: "development"  # development / production

# 数据库配置
database:
  path: "./data/ai-3d-modeling.db"
  # 或使用 SQLite in-memory
  # path: ":memory:"

# TOS 存储配置
tos:
  bucket: "4-ark-claw"
  base_path: "ai-3d-system"
  endpoint: "https://tos.bytepluses.com"
  region: "cn-north-1"
  # 访问密钥（建议使用环境变量）
  access_key: "${TOS_ACCESS_KEY}"
  secret_key: "${TOS_SECRET_KEY}"

# API 配置
api:
  # Ark API 配置（所有供应商共用）
  ark:
    base_url: "https://ark.cn-beijing.volces.com/api/v3"
    timeout: 30
    max_retries: 3
  
  # 飞书 API 配置
  feishu:
    app_id: "${FEISHU_APP_ID}"
    app_secret: "${FEISHU_APP_SECRET}"
    webhook_url: "http://127.0.0.1:18789/webhook/notify"

# 轮询配置
poller:
  interval: 60          # 轮询间隔（秒）
  enabled: true         # 是否启用轮询
  batch_size: 100       # 每次轮询的最大任务数

# 任务配置
task:
  timeout_minutes: 60   # 任务超时时间（分钟）
  max_images: 4         # 最大图片数量
  share_url_expire: 86400  # 分享链接过期时间（秒）

# 日志配置
logging:
  level: "INFO"         # DEBUG / INFO / WARNING / ERROR
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "./logs/ai-3d-modeling.log"
```

---

## 3. 环境变量 (.env)

```bash
# TOS 存储
TOS_ACCESS_KEY=AKxxx
TOS_SECRET_KEY=xxx

# 飞书应用
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx

# 数据库（可选）
DATABASE_PATH=./data/ai-3d-modeling.db
```

---

## 4. 供应商配置文件 (vendors/seed3d.yaml)

```yaml
# 豆包 Seed3D 供应商配置
id: "vendor_ark_seed3d"
name: "豆包Seed3D"
model: "doubao-seed3d"

# API 配置
api:
  endpoint: "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
  method: "POST"
  auth_type: "bearer"

# 请求配置
request:
  max_images: 1
  max_image_size_mb: 10
  timeout_minutes: 30
  formats: ["glb"]

# 模板配置
templates:
  request:
    model: "${model}"
    content: ${content}
  content:
    - type: "image_url"
      image_url:
        url: "${image_url_0}"
  response:
    task_id: "$.id"
    status: "$.status"
    file_url: "$.content.file_url"

# 状态映射
status_map:
  queued: "queued"
  running: "running"
  succeeded: "succeeded"
  failed: "failed"

# 优先级（数字越大优先级越高）
priority: 10
enabled: true
```

---

## 5. 配置加载器

```python
"""
配置加载模块

用法：
    from config import Config
    config = Config.load('config.yaml')
"""

import os
import yaml
from typing import Any, Dict, Optional


class Config:
    """配置管理类"""
    
    _instance: Optional['Config'] = None
    
    def __init__(self, config_dict: Dict[str, Any]):
        self._config = config_dict
    
    @classmethod
    def load(cls, config_path: str = 'config/config.yaml') -> 'Config':
        """加载配置文件"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        
        # 处理环境变量替换
        config_dict = cls._resolve_env_vars(config_dict)
        
        cls._instance = cls(config_dict)
        return cls._instance
    
    @classmethod
    def get_instance(cls) -> 'Config':
        """获取配置实例"""
        if cls._instance is None:
            return cls.load()
        return cls._instance
    
    @classmethod
    def _resolve_env_vars(cls, obj: Any) -> Any:
        """递归解析环境变量"""
        if isinstance(obj, str):
            # 处理 ${VAR_NAME} 格式
            if obj.startswith('${') and obj.endswith('}'):
                var_name = obj[2:-1]
                return os.environ.get(var_name, obj)
            return obj
        elif isinstance(obj, dict):
            return {k: cls._resolve_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [cls._resolve_env_vars(item) for item in obj]
        return obj
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value
    
    @property
    def database(self) -> Dict[str, Any]:
        return self._config.get('database', {})
    
    @property
    def tos(self) -> Dict[str, Any]:
        return self._config.get('tos', {})
    
    @property
    def poller(self) -> Dict[str, Any]:
        return self._config.get('poller', {})
    
    @property
    def api(self) -> Dict[str, Any]:
        return self._config.get('api', {})
```

---

## 6. 配置验证

```python
"""
配置验证模块
"""

from dataclasses import dataclass
from typing import List


@dataclass
class VendorConfig:
    """供应商配置验证"""
    id: str
    name: str
    model: str
    endpoint: str
    max_images: int
    supported_formats: List[str]
    enabled: bool


def validate_vendor_config(config: dict) -> VendorConfig:
    """验证供应商配置"""
    required_fields = ['id', 'name', 'model', 'endpoint']
    
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field: {field}")
    
    return VendorConfig(
        id=config['id'],
        name=config['name'],
        model=config['model'],
        endpoint=config['endpoint'],
        max_images=config.get('max_images', 1),
        supported_formats=config.get('supported_formats', ['glb']),
        enabled=config.get('enabled', True)
    )
```

---

## 7. 默认配置常量

```python
"""
默认配置常量
"""

# 数据库
DEFAULT_DB_PATH = "./data/ai-3d-modeling.db"

# TOS
DEFAULT_TOS_BUCKET = "4-ark-claw"
DEFAULT_TOS_BASE_PATH = "ai-3d-system"

# 轮询
DEFAULT_POLL_INTERVAL = 60  # 秒
DEFAULT_BATCH_SIZE = 100

# 任务
DEFAULT_TIMEOUT_MINUTES = 60
DEFAULT_MAX_IMAGES = 4
DEFAULT_SHARE_URL_EXPIRE = 86400  # 24小时

# API
DEFAULT_API_TIMEOUT = 30  # 秒
DEFAULT_MAX_RETRIES = 3
```
