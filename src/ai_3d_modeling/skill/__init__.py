"""
AI-3D 建模系统 - Skill 模块

飞书 Skill 入口，处理用户消息
"""

import json
import re
import httpx
from typing import Dict, List, Optional, Tuple
from .db import Database, SessionManager, MaterialManager, VendorTaskManager
from .adapters import AdapterFactory
from .utils import generate_uuid, get_timestamp
from .notifier import FeishuNotifier


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
    
    def __init__(self, db: Database, notifier: FeishuNotifier):
        self.db = db
        self.session_mgr = SessionManager(db)
        self.material_mgr = MaterialManager(db)
        self.task_mgr = VendorTaskManager(db)
        self.notifier = notifier
    
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
    
    def _extract_images(self, event: Dict) -> List[str]:
        """
        从事件中提取图片
        
        Returns:
            图片 URL 列表
        """
        image_urls = []
        message = event.get('event', {}).get('message', {})
        
        # 图片消息
        if message.get('message_type') == 'image':
            content_str = message.get('content', '{}')
            try:
                content = json.loads(content_str)
                image_key = content.get('image_key')
                if image_key:
                    # 实际需要通过飞书 API 下载图片获取 URL
                    # 这里返回 image_key 作为占位
                    image_urls.append(f'feishu://image/{image_key}')
            except:
                pass
        
        # 合并转发消息中的图片
        # 其他类型的图片提取...
        
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


async def handle_event(event: Dict) -> Dict:
    """
    Skill 入口函数
    
    Args:
        event: 飞书事件字典
    
    Returns:
        响应字典
    """
    # 初始化（实际应该通过依赖注入）
    db = Database('ai-3d-modeling.db')
    notifier = FeishuNotifier('http://127.0.0.1:18789/webhook/notify')
    
    handler = SkillHandler(db, notifier)
    return await handler.handle_event(event)
