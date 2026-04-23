# AI-3D 建模系统 - API 接口文档

## 文档信息
- 版本：v1.0.0
- 创建时间：2026-04-23
- 说明：各模块接口定义

---

## 1. 模块接口概览

| 模块 | 主要接口 | 说明 |
|------|----------|------|
| `adapters` | `AdapterFactory.create()` | 创建适配器 |
| `db` | `Database`, `SessionManager` | 数据库操作 |
| `storage` | `StorageManager.upload()` | 文件存储 |
| `notifier` | `ResultSummarizer.summarize()` | 结果汇总 |
| `skill` | `handle_event()` | 事件处理 |

---

## 2. adapters 模块

### 2.1 AdapterFactory

```python
class AdapterFactory:
    @staticmethod
    def create(vendor_config: dict, api_key: str = None) -> BaseAdapter
        """
        创建适配器实例
        
        Args:
            vendor_config: 供应商配置字典
            api_key: API密钥
        
        Returns:
            BaseAdapter 实例
        """
    
    @staticmethod
    def get_active_vendors() -> List[dict]
        """
        获取所有活跃供应商配置
        
        Returns:
            活跃供应商配置列表
        """
```

### 2.2 BaseAdapter

```python
class BaseAdapter:
    def build_request(self, material: dict) -> dict
        """构建API请求体"""
    
    def parse_response(self, response: dict) -> dict
        """
        解析API响应
        
        Returns:
            包含 task_id, status, file_url 的字典
        """
    
    async def submit(self, request_body: dict) -> dict
        """
        提交任务到供应商API
        
        Returns:
            API 响应字典
        """
    
    async def query_status(self, vendor_task_id: str) -> dict
        """
        查询任务状态
        
        Returns:
            状态响应字典
        """
    
    def get_auth_headers(self) -> dict
        """获取认证头"""
```

---

## 3. db 模块

### 3.1 Database

```python
class Database:
    def __init__(self, db_path: str)
        """初始化数据库连接"""
    
    def initialize(self)
        """创建所有表"""
    
    def execute(self, sql: str, params: tuple = None) -> List[dict]
        """执行SQL查询"""
    
    def close()
        """关闭连接"""
```

### 3.2 SessionManager

```python
class SessionManager:
    def create(self, session_uuid: str, channel_type: str, 
              channel_user_id: str, **kwargs) -> dict
        """创建会话"""
    
    def get(self, session_uuid: str) -> Optional[dict]
        """获取会话"""
    
    def update_phase(self, session_uuid: str, phase: str)
        """更新会话阶段"""
    
    def update_status(self, session_uuid: str, status: str)
        """更新会话状态"""
    
    def get_active_sessions() -> List[dict]
        """获取所有活跃会话"""
```

### 3.3 MaterialManager

```python
class MaterialManager:
    def create(self, material_uuid: str, session_uuid: str,
              material_type: str, source_type: str, **kwargs) -> dict
        """创建材料记录"""
    
    def get(self, material_uuid: str) -> Optional[dict]
        """获取材料"""
    
    def get_by_session(self, session_uuid: str) -> List[dict]
        """获取会话的所有材料"""
    
    def update_status(self, material_uuid: str, status: str)
        """更新材料状态"""
```

### 3.4 VendorTaskManager

```python
class VendorTaskManager:
    def create(self, vendor_task_uuid: str, session_uuid: str,
              material_uuid: str, vendor_id: str, 
              vendor_name: str, model_name: str, **kwargs) -> dict
        """创建供应商任务"""
    
    def get(self, vendor_task_uuid: str) -> Optional[dict]
        """获取任务"""
    
    def get_by_session(self, session_uuid: str) -> List[dict]
        """获取会话的所有任务"""
    
    def get_running() -> List[dict]
        """获取所有运行中的任务"""
    
    def update_status(self, vendor_task_uuid: str, status: str, **kwargs)
        """更新任务状态"""
    
    def set_vendor_task_id(self, vendor_task_uuid: str, vendor_task_id: str)
        """设置供应商返回的任务ID"""
    
    def increment_poll_count(self, vendor_task_uuid: str)
        """增加轮询计数"""
    
    def check_all_done(self, session_uuid: str) -> bool
        """检查会话所有任务是否完成"""
```

---

## 4. storage 模块

### 4.1 StorageManager

```python
class StorageManager:
    def __init__(self, bucket: str, base_path: str)
    
    def upload(self, local_path: str, remote_path: str) -> str
        """
        上传文件到TOS
        
        Args:
            local_path: 本地文件路径
            remote_path: TOS 远程路径
        
        Returns:
            TOS 文件路径
        """
    
    def download(self, remote_path: str, local_path: str) -> str
        """
        从TOS下载文件
        
        Args:
            remote_path: TOS 远程路径
            local_path: 本地保存路径
        
        Returns:
            本地文件路径
        """
    
    def upload_result(self, vendor_task_uuid: str, file_url: str,
                     session_uuid: str) -> dict
        """
        下载供应商结果并上传到TOS
        
        Returns:
            包含 tos_path 和 share_url 的字典
        """
    
    def generate_share_url(self, remote_path: str, 
                          expire_seconds: int = 86400) -> str
        """
        生成带过期时间的下载链接
        
        Args:
            remote_path: TOS 文件路径
            expire_seconds: 过期秒数
        
        Returns:
            下载 URL
        """
    
    def build_tos_path(self, session_uuid: str, sub_path: str) -> str
        """构建完整的TOS路径"""
```

---

## 5. notifier 模块

### 5.1 ResultSummarizer

```python
class ResultSummarizer:
    def __init__(self, db: Database)
    
    def summarize(self, session_uuid: str) -> dict
        """
        汇总会话的所有供应商结果
        
        Returns:
            汇总报告字典
            {
                "event": "all_vendors_completed",
                "session_uuid": "...",
                "summary": {...},
                "results": [...],
                "materials": {...}
            }
        """
    
    def check_all_done(self, session_uuid: str) -> bool
        """检查是否所有任务都完成"""
    
    def calculate_duration(self, session_uuid: str) -> int
        """计算总耗时（秒）"""
    
    def build_materials_preview(self, session_uuid: str) -> dict
        """构建材料预览信息"""
```

### 5.2 FeishuNotifier

```python
class FeishuNotifier:
    def __init__(self, gateway_url: str)
    
    async def send_summary(self, session_key: str, summary: dict) -> bool
        """
        发送汇总通知到飞书
        
        Args:
            session_key: 会话标识
            summary: 汇总报告
        
        Returns:
            是否发送成功
        """
    
    def build_card(self, summary: dict) -> dict
        """
        构建飞书消息卡片
        
        Returns:
            飞书卡片格式字典
        """
    
    async def send(self, session_key: str, card: dict) -> bool
        """发送卡片消息"""
```

---

## 6. skill 模块

### 6.1 SkillHandler

```python
class SkillHandler:
    def __init__(self, db: Database, 
                 storage: StorageManager,
                 notifier: FeishuNotifier)
    
    async def handle_event(self, event: dict) -> dict
        """
        处理飞书事件
        
        Args:
            event: 飞书事件字典
        
        Returns:
            响应字典
        """
    
    def parse_intent(self, text: str) -> str
        """
        解析用户意图
        
        Returns:
            意图类型: "3d_modeling" | "cancel" | "status" | "other"
        """
    
    def extract_materials(self, event: dict) -> dict
        """
        从事件中提取材料
        
        Returns:
            包含 image_urls 和 text_content 的字典
        """
    
    async def submit_vendor_tasks(self, session_uuid: str, 
                                  material: dict) -> List[dict]
        """
        向供应商提交任务
        
        Returns:
            创建的任务列表
        """
```

### 6.2 入口函数

```python
async def handle_event(event: dict) -> dict:
    """
    Skill 入口函数
    
    Args:
        event: 飞书事件字典
    
    Returns:
        响应字典
    """
    handler = SkillHandler(...)
    return await handler.handle_event(event)
```

---

## 7. poller 模块

### 7.1 Poller

```python
class Poller:
    def __init__(self, db: Database, 
                 adapter_factory: AdapterFactory,
                 storage: StorageManager,
                 notifier: FeishuNotifier,
                 interval: int = 60)
    
    def start()
        """启动轮询"""
    
    def stop()
        """停止轮询"""
    
    async def _poll_once()
        """执行一次轮询"""
    
    async def _poll_task(self, task: dict, vendor_config: dict)
        """轮询单个任务"""
    
    async def _handle_success(self, task: dict, file_url: str)
        """处理任务成功"""
    
    async def _handle_failure(self, task: dict, error: str)
        """处理任务失败"""
    
    async def _check_and_send_summaries()
        """检查并发送汇总通知"""
```

---

## 8. utils 模块

```python
def generate_uuid(prefix: str = '') -> str
    """生成UUID"""

def get_timestamp() -> int
    """获取Unix时间戳（秒）"""

def format_duration(seconds: int) -> str
    """格式化时长，如 '2分5秒'"""

def parse_content_type(url: str) -> Optional[str]
    """从URL解析文件类型"""

def sanitize_path(path: str) -> str
    """清理路径，防止路径遍历"""

def build_tos_path(session_uuid: str, sub_path: str) -> str
    """构建TOS路径"""
```

---

## 9. 数据结构

### 9.1 Session

```python
{
    "session_uuid": "sess_abc123",
    "channel_type": "feishu",
    "channel_user_id": "ou_xxx",
    "channel_user_name": "张三",
    "group_id": "oc_xxx",
    "status": "active",          # active/completed/failed
    "phase": "processing",      # pending/processing/completed
    "user_input": "生成一个3D模型",
    "created_at": 1704067200,
    "updated_at": 1704067200,
    "completed_at": None
}
```

### 9.2 Material

```python
{
    "material_uuid": "mat_abc123",
    "session_uuid": "sess_abc123",
    "material_type": "image",    # image/text/mixed
    "source_type": "feishu",
    "text_content": "卡通人物",
    "image_urls": '["https://..."]',
    "status": "ready",
    "created_at": 1704067200
}
```

### 9.3 VendorTask

```python
{
    "vendor_task_uuid": "task_abc123",
    "session_uuid": "sess_abc123",
    "material_uuid": "mat_abc123",
    "vendor_id": "vendor_ark_seed3d",
    "vendor_name": "豆包Seed3D",
    "model_name": "doubao-seed3d",
    "vendor_task_id": "ark_12345",
    "status": "running",         # pending/queued/running/succeeded/failed
    "poll_count": 5,
    "created_at": 1704067200,
    "submitted_at": 1704067210,
    "completed_at": None
}
```

### 9.4 Summary

```python
{
    "event": "all_vendors_completed",
    "session_uuid": "sess_abc123",
    "summary": {
        "total_vendors": 3,
        "succeeded": 2,
        "failed": 1,
        "total_time_seconds": 245
    },
    "results": [
        {
            "vendor_name": "豆包Seed3D",
            "status": "succeeded",
            "file_format": "glb",
            "share_url": "https://tos.bytepluses.com/..."
        }
    ],
    "materials": {
        "type": "image",
        "count": 1
    }
}
```

---

## 10. 错误处理

### 10.1 异常类

```python
class AI3DError(Exception):
    """基础异常"""
    pass

class ConfigError(AI3DError):
    """配置错误"""
    pass

class DatabaseError(AI3DError):
    """数据库错误"""
    pass

class VendorAPIError(AI3DError):
    """供应商API错误"""
    def __init__(self, vendor_id: str, code: str, message: str)
```

### 10.2 错误处理示例

```python
try:
    task = await adapter.submit(request_body)
except VendorAPIError as e:
    logger.error(f"Vendor API error: {e.vendor_id} - {e.code}")
    db.vendor_tasks.update_status(task_id, 'failed', error_message=str(e))
except Exception as e:
    logger.exception("Unexpected error")
    raise
```
