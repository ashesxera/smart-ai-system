"""skill/__init__.py -- AI-3D Modeling Skill Handler

【已弃用】此模块已被 skill/standalone.py 取代，请使用新模块。

---

此模块提供 Skill 事件处理器，原本设计为通过 HTTP 服务接收飞书 webhook 事件。

【为何不使用 HTTP 服务？】

1. OpenClaw 的 Skill 机制是基于对话的：
   - OpenClaw 接收用户消息后，将 SKILL.md 内容注入到 AI 的系统提示中
   - AI 根据 SKILL.md 的指引，在对话中直接执行 Python 代码
   - 不需要独立的 HTTP 服务来接收外部事件

2. OpenClaw 内部触发 Skill：
   - 当 AI 判断用户需要 3D 建模服务时，直接调用 skill 模块的函数
   - 事件来源是 OpenClaw 内部（而非外部 HTTP 请求）
   - 飞书消息通过 OpenClaw 的 channel 插件接收，已在内部转换为事件

3. 简化架构：
   - 减少部署复杂度（无需管理额外服务）
   - 减少维护成本（无需监控 HTTP 服务的可用性）
   - 任务结果由独立的 poller 进程轮询获取，无需服务端推送

【当前使用的模块】

请使用 `skill/standalone.py`，它提供了直接被 OpenClaw AI 调用的接口：

```python
from ai_3d_modeling.skill.standalone import handle_user_message

result = await handle_user_message(
    message_text="生成3D模型",
    sender_id="ou_xxx",
    sender_name="用户名",
    chat_id="",
    message_id="om_xxx",
    images=[]
)
```

---

历史记录：
- 2026-04-23: 初始版本，设计为 HTTP 服务模式
- 2026-04-23: 重构为 standalone.py，直接被 OpenClaw 调用
"""

import json
import logging
import os
import re
import httpx
from typing import Dict, List, Optional, Tuple
from ai_3d_modeling.db import Database, SessionManager, MaterialManager, VendorTaskManager
from ai_3d_modeling.adapters import AdapterFactory
from ai_3d_modeling.utils import generate_uuid, get_timestamp
from ai_3d_modeling.notifier import Notifier

# =============================================================================
# 【已弃用】此类和相关代码不再使用，请使用 skill/standalone.py
# =============================================================================


# 意图关键词配置
MODELING_KEYWORDS = [
    '3d', '三维', '建模', '生成', '模型', 'obj', 'glb', 'stl',
    'make 3d', 'generate model', 'create model', '图片建模'
]

CANCEL_KEYWORDS = ['取消', '撤销', '停止', 'cancel', 'abort', 'stop']

STATUS_KEYWORDS = ['状态', '进度', '怎么样了', '完成了吗', 'status', 'progress']

HELP_KEYWORDS = ['帮助', 'help', '怎么用', '使用说明', 'help me']


class SkillHandler:
    """Skill 事件处理器"""
    
    def __init__(self, db: Database, notifier: Notifier, feishu_credentials: Dict = None):
        """
        初始化处理器
        
        Args:
            db: 数据库实例
            notifier: 通知器
            feishu_credentials: 飞书凭证 {app_id, app_secret}
        """
        self.db = db
        self.session_mgr = SessionManager(db)
        self.material_mgr = MaterialManager(db)
        self.task_mgr = VendorTaskManager(db)
        self.notifier = notifier
        self.feishu_credentials = feishu_credentials or {}
        self._feishu_token = None
    
    async def handle_event(self, event: Dict) -> Dict:
        """
        处理飞书事件
        
        Args:
            event: 飞书事件字典
        
        Returns:
            响应字典
        """
        try:
            # 1. 解析意图
            intent, text_content = self._extract_intent_and_text(event)
            
            # 2. 根据意图处理
            if intent == '3d_modeling':
                return await self._handle_3d_modeling(event, text_content)
            elif intent == 'cancel':
                return await self._handle_cancel(event)
            elif intent == 'status':
                return await self._handle_status(event)
            elif intent == 'help':
                return self._handle_help(event)
            else:
                return self._handle_unknown(event)
        
        except Exception as e:
            return {
                'code': 50001,
                'msg': f'服务器内部错误: {str(e)}',
                'data': None
            }
    
    def _extract_intent_and_text(self, event: Dict) -> Tuple[str, str]:
        """
        从事件中提取意图和文本
        
        Returns:
            (意图类型, 文本内容)
        """
        message = event.get('event', {}).get('message', {})
        content_str = message.get('content', '{}')
        
        try:
            content = json.loads(content_str)
        except:
            content = {'text': content_str}
        
        text = content.get('text', '').strip()
        
        # 解析意图
        intent = self._parse_intent(text)
        
        return intent, text
    
    def _parse_intent(self, text: str) -> str:
        """
        解析用户意图
        
        Args:
            text: 用户文本
        
        Returns:
            意图类型
        """
        text_lower = text.lower()
        
        # 检查取消意图
        for kw in CANCEL_KEYWORDS:
            if kw in text_lower:
                return 'cancel'
        
        # 检查3D建模意图
        for kw in MODELING_KEYWORDS:
            if kw in text_lower:
                return '3d_modeling'
        
        # 检查状态查询
        for kw in STATUS_KEYWORDS:
            if kw in text_lower:
                return 'status'
        
        # 检查帮助
        for kw in HELP_KEYWORDS:
            if kw in text_lower:
                return 'help'
        
        return 'other'
    
    async def _handle_3d_modeling(self, event: Dict, text_content: str) -> Dict:
        """
        处理3D建模请求
        """
        sender = event.get('event', {}).get('sender', {})
        sender_id = sender.get('sender_id', {})
        message = event.get('event', {}).get('message', {})
        
        channel_type = 'feishu'
        channel_user_id = sender_id.get('open_id', '')
        channel_user_name = ''  # 可从飞书 API 获取
        group_id = event.get('event', {}).get('recipient', {}).get('chat_id', '')
        source_message_id = message.get('message_id', '')
        
        # 1. 提取材料
        image_urls = self._extract_images(event)
        material_type = 'image' if image_urls else ('text' if text_content else 'mixed')
        
        # 2. 创建会话
        session_uuid = generate_uuid('sess')
        self.session_mgr.create(
            session_uuid=session_uuid,
            channel_type=channel_type,
            channel_user_id=channel_user_id,
            channel_user_name=channel_user_name,
            group_id=group_id if group_id else None,
            user_input=text_content,
            source_message_id=source_message_id
        )
        
        # 3. 创建材料记录
        material_uuid = generate_uuid('mat')
        self.material_mgr.create(
            material_uuid=material_uuid,
            session_uuid=session_uuid,
            material_type=material_type,
            source_type='feishu',
            text_content=text_content if text_content else None,
            image_urls=image_urls if image_urls else None
        )
        
        # 4. 更新会话阶段
        self.session_mgr.update_phase(session_uuid, 'processing')
        
        # 5. 提交供应商任务
        tasks = await self._submit_vendor_tasks(session_uuid, material_uuid, {
            'material_uuid': material_uuid,
            'material_type': material_type,
            'text_content': text_content,
            'image_urls': image_urls
        })
        
        # 6. 返回响应
        return {
            'code': 0,
            'msg': 'success',
            'data': {
                'session_uuid': session_uuid,
                'message': f'已收到您的请求，正在处理中...（已提交{len(tasks)}个供应商）',
                'phase': 'processing'
            }
        }
    
    async def _download_feishu_image(self, image_key: str, message_id: str) -> Optional[str]:
        """
        从飞书下载图片并返回临时 URL
        
        Args:
            image_key: 飞书图片 key (img_xxx)
            message_id: 消息 ID
        
        Returns:
            图片 URL 或 None
        """
        app_id = self.feishu_credentials.get('app_id', os.getenv('FEISHU_APP_ID', ''))
        app_secret = self.feishu_credentials.get('app_secret', os.getenv('FEISHU_APP_SECRET', ''))
        
        if not app_id or not app_secret:
            logging.warning("Feishu credentials not configured, cannot download images")
            return None
        
        try:
            # 获取 tenant access token
            token = await self._get_feishu_token(app_id, app_secret)
            if not token:
                return None
            
            # 下载图片
            url = f'https://open.feishu.cn/open-apis/im/v1/images/{image_key}'
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    # 图片是二进制数据，上传到 TOS 获取 URL
                    # 这里返回数据作为临时方案
                    image_data = response.content
                    logging.info(f"Downloaded image {image_key}, size: {len(image_data)} bytes")
                    
                    # 后续可以将图片上传到 TOS
                    # 目前返回 None 表示需要后续处理
                    return None
                else:
                    logging.error(f"Failed to download image: {response.status_code}")
                    return None
        
        except Exception as e:
            logging.error(f"Error downloading Feishu image: {e}")
            return None
    
    async def _get_feishu_token(self, app_id: str, app_secret: str) -> Optional[str]:
        """
        获取飞书 tenant access token
        
        Args:
            app_id: 飞书 App ID
            app_secret: 飞书 App Secret
        
        Returns:
            token 字符串或 None
        """
        try:
            url = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal'
            headers = {'Content-Type': 'application/json'}
            data = {
                'app_id': app_id,
                'app_secret': app_secret
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=data)
                result = response.json()
                
                if result.get('code') == 0:
                    return result.get('tenant_access_token')
                else:
                    logging.error(f"Failed to get Feishu token: {result}")
                    return None
        
        except Exception as e:
            logging.error(f"Error getting Feishu token: {e}")
            return None
    
    def _extract_images(self, event: Dict) -> List[str]:
        """
        从事件中提取图片 URL
        
        支持的图片来源:
        1. 图片消息 (message_type=image) - 通过飞书 API 下载
        2. 合并转发消息中的图片
        3. 文本消息中的 URL
        
        Returns:
            图片 URL 列表
        """
        image_urls = []
        message = event.get('event', {}).get('message', {})
        message_type = message.get('message_type', '')
        message_id = message.get('message_id', '')
        
        # 1. 图片消息
        if message_type == 'image':
            content_str = message.get('content', '{}')
            try:
                content = json.loads(content_str)
                image_key = content.get('image_key')
                if image_key:
                    # image_key 需要通过飞书 API 下载
                    # 目前返回 feishu://image/{key} 作为占位
                    # 实际下载在 _download_feishu_image 中完成
                    image_urls.append(f'feishu://image/{image_key}?msg_id={message_id}')
                    logging.info(f"Found image message: {image_key}")
            except json.JSONDecodeError:
                logging.warning(f"Failed to parse image message content: {content_str}")
        
        # 2. 文本消息中的图片 URL
        content_str = message.get('content', '{}')
        try:
            content = json.loads(content_str)
            text = content.get('text', '')
            
            # 匹配常见的图片 URL 模式
            import re
            url_pattern = r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|gif|webp)(?:\?[^\s"<>]*)?'
            urls = re.findall(url_pattern, text, re.IGNORECASE)
            image_urls.extend(urls)
            
        except json.JSONDecodeError:
            # 纯文本消息
            pass
        
        # 3. 合并转发消息 (mixed)
        if message_type == 'mixed':
            try:
                content = json.loads(content_str)
                items = content.get('items', [])
                for item in items:
                    if item.get('message_type') == 'image':
                        item_content = json.loads(item.get('content', '{}'))
                        image_key = item_content.get('image_key')
                        if image_key:
                            image_urls.append(f'feishu://image/{image_key}?msg_id={item.get("message_id", "")}')
            except (json.JSONDecodeError, KeyError) as e:
                logging.warning(f"Failed to parse mixed message: {e}")
        
        return image_urls
    
    async def _submit_vendor_tasks(self, session_uuid: str, 
                                   material_uuid: str,
                                   material: Dict) -> List[Dict]:
        """
        向所有活跃供应商提交任务
        """
        # 获取活跃供应商
        vendors = self._get_active_vendors()
        
        tasks = []
        for vendor in vendors:
            try:
                task = await self._submit_to_vendor(
                    session_uuid, material_uuid, material, vendor
                )
                tasks.append(task)
            except Exception as e:
                # 单个供应商失败不影响其他供应商
                continue
        
        return tasks
    
    def _get_active_vendors(self) -> List[Dict]:
        """获取活跃供应商配置"""
        results = self.db.execute('''
            SELECT value FROM settings 
            WHERE category = 'vendor' 
            AND value LIKE '%"is_active": true%'
        ''')
        
        vendors = []
        for row in results:
            try:
                config = json.loads(row['value'])
                vendors.append(config)
            except:
                continue
        
        return vendors
    
    async def _submit_to_vendor(self, session_uuid: str,
                                 material_uuid: str,
                                 material: Dict,
                                 vendor: Dict) -> Dict:
        """
        向单个供应商提交任务
        """
        # 检查图片数量限制
        max_images = vendor.get('max_images', 4)
        image_urls = material.get('image_urls', [])
        if len(image_urls) > max_images:
            image_urls = image_urls[:max_images]
        
        # 构建材料（适配器格式）
        adapter_material = {
            'material_uuid': material_uuid,
            'material_type': material['material_type'],
            'text_content': material.get('text_content', ''),
            'image_urls': image_urls
        }
        
        # 创建适配器
        adapter = AdapterFactory.create(vendor)
        
        # 构建请求
        request_body = adapter.build_request(adapter_material)
        
        # 提交到供应商 API
        try:
            response = await adapter.submit(request_body)
        except Exception as e:
            raise RuntimeError(f"Vendor API error: {e}")
        
        # 解析响应
        parsed = adapter.parse_response(response)
        
        # 创建任务记录
        task_uuid = generate_uuid('task')
        self.task_mgr.create(
            vendor_task_uuid=task_uuid,
            session_uuid=session_uuid,
            material_uuid=material_uuid,
            vendor_id=vendor.get('id'),
            vendor_name=vendor.get('name'),
            model_name=vendor.get('model'),
            api_endpoint=vendor.get('endpoint'),
            api_request_body=json.dumps(request_body)
        )
        
        # 更新供应商任务ID
        if parsed.get('vendor_task_id'):
            self.task_mgr.set_vendor_task_id(
                task_uuid, 
                parsed['vendor_task_id'],
                json.dumps(response)
            )
        
        return {'vendor_task_uuid': task_uuid, 'vendor_id': vendor.get('id')}
    
    async def _handle_cancel(self, event: Dict) -> Dict:
        """处理取消请求"""
        sender_id = event.get('event', {}).get('sender', {}).get('sender_id', {})
        channel_user_id = sender_id.get('open_id', '')
        
        # 查找用户最近的进行中的会话
        active_sessions = self.session_mgr.get_active_sessions()
        user_sessions = [
            s for s in active_sessions 
            if s.get('channel_user_id') == channel_user_id
        ]
        
        if not user_sessions:
            return {
                'code': 0,
                'msg': 'success',
                'data': {
                    'message': '没有找到进行中的任务'
                }
            }
        
        # 取消最新的会话
        latest = user_sessions[0]
        self.session_mgr.update_status(latest['session_uuid'], 'cancelled')
        
        return {
            'code': 0,
            'msg': 'success',
            'data': {
                'session_uuid': latest['session_uuid'],
                'message': '已取消任务'
            }
        }
    
    async def _handle_status(self, event: Dict) -> Dict:
        """处理状态查询"""
        sender_id = event.get('event', {}).get('sender', {}).get('sender_id', {})
        channel_user_id = sender_id.get('open_id', '')
        
        # 查找用户最近的进行中的会话
        active_sessions = self.session_mgr.get_active_sessions()
        user_sessions = [
            s for s in active_sessions 
            if s.get('channel_user_id') == channel_user_id
        ]
        
        if not user_sessions:
            return {
                'code': 0,
                'msg': 'success',
                'data': {
                    'message': '没有找到进行中的任务'
                }
            }
        
        # 获取任务状态
        latest = user_sessions[0]
        tasks = self.task_mgr.get_by_session(latest['session_uuid'])
        
        running = sum(1 for t in tasks if t['status'] in ('queued', 'running'))
        succeeded = sum(1 for t in tasks if t['status'] == 'succeeded')
        failed = sum(1 for t in tasks if t['status'] == 'failed')
        
        return {
            'code': 0,
            'msg': 'success',
            'data': {
                'session_uuid': latest['session_uuid'],
                'message': f'任务进行中... 运行: {running}, 成功: {succeeded}, 失败: {failed}'
            }
        }
    
    def _handle_help(self, event: Dict) -> Dict:
        """处理帮助请求"""
        help_text = """
🎨 AI 3D 建模助手

发送图片+文字描述，即可生成3D模型！

📝 使用方法：
• 发送图片 + 文字描述
• 或只发送文字描述（AI会根据描述生成）

支持的格式：GLB, OBJ, FBX, STL, USDZ

🔧 命令：
• "状态" - 查看任务进度
• "取消" - 取消进行中的任务
• "帮助" - 显示此帮助
"""
        
        return {
            'code': 0,
            'msg': 'success',
            'data': {
                'message': help_text.strip()
            }
        }
    
    def _handle_unknown(self, event: Dict) -> Dict:
        """处理未知意图"""
        return {
            'code': 0,
            'msg': 'success',
            'data': {
                'message': '我不太理解您的意思，请发送"帮助"查看使用方法。'
            }
        }


async def handle_event(event: Dict, config: Dict = None) -> Dict:
    """
    Skill 入口函数
    
    Args:
        event: 飞书事件字典
        config: 配置字典 (可选)
    
    Returns:
        响应字典
    """
    config = config or {}
    
    # 从环境变量或配置读取
    db_path = config.get('db_path', os.getenv('DB_PATH', 'ai-3d-modeling.db'))
    gateway_url = config.get('gateway_url', os.getenv('GATEWAY_URL', 'http://127.0.0.1:18789/webhook/notify'))
    
    feishu_credentials = {
        'app_id': config.get('feishu_app_id') or os.getenv('FEISHU_APP_ID', ''),
        'app_secret': config.get('feishu_app_secret') or os.getenv('FEISHU_APP_SECRET', ''),
    }
    
    # 初始化组件
    db = Database(db_path)
    notifier = Notifier(gateway_url)
    
    handler = SkillHandler(db, notifier, feishu_credentials)
    return await handler.handle_event(event)
