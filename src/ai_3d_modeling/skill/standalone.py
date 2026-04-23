"""
skill/standalone.py -- OpenClaw 直接调用的 Skill 模块

【使用说明】
此模块供 OpenClaw AI Assistant 直接调用。当用户在飞书中发送包含 3D 建模
相关关键词的消息时，OpenClaw 会激活此技能，AI 根据本模块的指引直接调用
相关函数完成操作。

【为何不使用 HTTP 服务？】
1. OpenClaw 的 Skill 机制是基于对话的，AI 读取 SKILL.md 后直接在对话中
   执行 Python 代码，不需要独立的网络服务。
2. 轮询任务结果由独立的 poller 进程处理，不需要飞书服务端推送事件。
3. 简化部署，无需管理额外的服务进程。

【工作流程】
用户发消息 → OpenClaw 接收 → AI 激活 Skill → 解析意图 → 调用本模块
→ 创建数据库记录 → poller 轮询结果 → AI 通知用户

【调用方式】
AI 在读取 SKILL.md 后，会执行类似这样的操作：
    from ai_3d_modeling.skill.standalone import process_modeling_request
    
    result = await process_modeling_request(
        user_message="生成一个3D模型",
        sender_id="ou_xxx",
        images=[...]
    )
"""

import asyncio
import json
import logging
import os
from typing import Dict, List, Optional, Any

from ai_3d_modeling.db import Database, SessionManager, MaterialManager, VendorTaskManager
from ai_3d_modeling.adapters import AdapterFactory
from ai_3d_modeling.utils import generate_uuid
from ai_3d_modeling.notifier import FeishuNotifier

logger = logging.getLogger(__name__)


# ============================================================================
# 核心处理函数 (供 OpenClaw AI 直接调用)
# ============================================================================

async def process_modeling_request(
    user_message: str,
    sender_id: str,
    sender_name: str = "",
    chat_id: str = "",
    message_id: str = "",
    images: List[str] = None
) -> Dict[str, Any]:
    """
    处理用户的 3D 建模请求
    
    此函数是 OpenClaw Skill 的主入口。当 AI 激活技能后，会调用此函数
    来处理用户的建模请求。
    
    Args:
        user_message: 用户的文本消息
        sender_id: 发送者的 open_id
        sender_name: 发送者的显示名称
        chat_id: 会话 ID (私聊为空，群聊为群 ID)
        message_id: 消息 ID
        images: 图片 URL 列表 (可选)
    
    Returns:
        处理结果字典，包含:
        - success: 是否成功
        - session_uuid: 会话 UUID
        - message: 给用户的回复消息
        - phase: 当前阶段 (received/processing/completed)
    """
    images = images or []
    
    # 初始化数据库
    db = Database(get_db_path())
    session_mgr = SessionManager(db)
    material_mgr = MaterialManager(db)
    task_mgr = VendorTaskManager(db)
    
    try:
        # 1. 创建会话记录
        session_uuid = generate_uuid('sess')
        session_mgr.create(
            session_uuid=session_uuid,
            channel_type='feishu',
            channel_user_id=sender_id,
            channel_user_name=sender_name,
            group_id=chat_id if chat_id else None,
            user_input=user_message,
            source_message_id=message_id
        )
        logger.info(f"Created session {session_uuid} for user {sender_id}")
        
        # 2. 确定材料类型
        material_type = 'mixed'
        if images and user_message.strip():
            material_type = 'mixed'
        elif images:
            material_type = 'image'
        elif user_message.strip():
            material_type = 'text'
        else:
            return {
                'success': False,
                'message': '请提供图片或文字描述',
                'phase': 'received'
            }
        
        # 3. 创建材料记录
        material_uuid = generate_uuid('mat')
        material_mgr.create(
            material_uuid=material_uuid,
            session_uuid=session_uuid,
            material_type=material_type,
            source_type='feishu',
            text_content=user_message if user_message else None,
            image_urls=images if images else None
        )
        
        # 4. 更新会话阶段
        session_mgr.update_phase(session_uuid, 'processing')
        
        # 5. 提交供应商任务
        tasks = await _submit_vendor_tasks(
            db, session_uuid, material_uuid,
            material_type, user_message, images
        )
        
        logger.info(f"Submitted {len(tasks)} vendor tasks for session {session_uuid}")
        
        return {
            'success': True,
            'session_uuid': session_uuid,
            'message': _build_success_message(len(tasks), material_type),
            'phase': 'processing',
            'tasks_count': len(tasks)
        }
        
    except Exception as e:
        logger.error(f"Error processing modeling request: {e}")
        return {
            'success': False,
            'message': f'处理失败: {str(e)}',
            'phase': 'error'
        }


async def process_cancel_request(
    sender_id: str,
    chat_id: str = ""
) -> Dict[str, Any]:
    """
    处理取消请求
    
    Args:
        sender_id: 发送者的 open_id
        chat_id: 会话 ID
    
    Returns:
        取消结果
    """
    db = Database(get_db_path())
    session_mgr = SessionManager(db)
    
    # 查找用户最近的进行中的会话
    active_sessions = session_mgr.get_active_sessions()
    user_sessions = [
        s for s in active_sessions
        if s.get('channel_user_id') == sender_id
    ]
    
    if not user_sessions:
        return {
            'success': True,
            'message': '没有找到进行中的任务'
        }
    
    # 取消最新的会话
    latest = user_sessions[0]
    session_mgr.update_status(latest['session_uuid'], 'cancelled')
    
    return {
        'success': True,
        'session_uuid': latest['session_uuid'],
        'message': '已取消任务'
    }


async def process_status_request(
    sender_id: str,
    chat_id: str = ""
) -> Dict[str, Any]:
    """
    处理状态查询请求
    
    Args:
        sender_id: 发送者的 open_id
        chat_id: 会话 ID
    
    Returns:
        状态信息
    """
    db = Database(get_db_path())
    session_mgr = SessionManager(db)
    task_mgr = VendorTaskManager(db)
    
    # 查找用户最近的进行中的会话
    active_sessions = session_mgr.get_active_sessions()
    user_sessions = [
        s for s in active_sessions
        if s.get('channel_user_id') == sender_id
    ]
    
    if not user_sessions:
        return {
            'success': True,
            'message': '没有找到进行中的任务'
        }
    
    # 获取任务状态
    latest = user_sessions[0]
    tasks = task_mgr.get_by_session(latest['session_uuid'])
    
    running = sum(1 for t in tasks if t['status'] in ('queued', 'running'))
    succeeded = sum(1 for t in tasks if t['status'] == 'succeeded')
    failed = sum(1 for t in tasks if t['status'] == 'failed')
    
    return {
        'success': True,
        'session_uuid': latest['session_uuid'],
        'message': f'任务进行中... 运行: {running}, 成功: {succeeded}, 失败: {failed}',
        'tasks': {
            'running': running,
            'succeeded': succeeded,
            'failed': failed
        }
    }


def get_help_text() -> str:
    """
    获取帮助文本
    
    Returns:
        帮助文档字符串
    """
    return """
🎨 AI 3D 建模助手

发送图片+文字描述，即可生成3D模型！

📝 使用方法：
• 发送图片 + 文字描述
• 或只发送文字描述（AI会根据描述生成）
• 或只发送图片

支持的格式：GLB, OBJ, FBX, STL, USDZ

🔧 命令：
• "状态" - 查看任务进度
• "取消" - 取消进行中的任务
• "帮助" - 显示此帮助

⏱️ 处理时间：通常需要 1-3 分钟
"""


# ============================================================================
# 内部辅助函数
# ============================================================================

async def _submit_vendor_tasks(
    db: Database,
    session_uuid: str,
    material_uuid: str,
    material_type: str,
    text_content: str,
    image_urls: List[str]
) -> List[Dict]:
    """
    向所有活跃供应商提交任务
    
    Args:
        db: 数据库实例
        session_uuid: 会话 UUID
        material_uuid: 材料 UUID
        material_type: 材料类型
        text_content: 文本内容
        image_urls: 图片 URL 列表
    
    Returns:
        提交的任务列表
    """
    # 获取活跃供应商
    vendors = _get_active_vendors(db)
    
    tasks = []
    for vendor in vendors:
        try:
            task = await _submit_to_vendor(
                db, session_uuid, material_uuid,
                material_type, text_content, image_urls, vendor
            )
            tasks.append(task)
        except Exception as e:
            logger.error(f"Failed to submit to vendor {vendor.get('id')}: {e}")
            continue
    
    return tasks


def _get_active_vendors(db: Database) -> List[Dict]:
    """获取活跃供应商配置"""
    results = db.execute('''
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


async def _submit_to_vendor(
    db: Database,
    session_uuid: str,
    material_uuid: str,
    material_type: str,
    text_content: str,
    image_urls: List[str],
    vendor: Dict
) -> Dict:
    """
    向单个供应商提交任务
    """
    task_mgr = VendorTaskManager(db)
    
    # 检查图片数量限制
    max_images = vendor.get('max_images', 4)
    if len(image_urls) > max_images:
        image_urls = image_urls[:max_images]
    
    # 构建材料
    adapter_material = {
        'material_uuid': material_uuid,
        'material_type': material_type,
        'text_content': text_content or '',
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
    task_mgr.create(
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
        task_mgr.set_vendor_task_id(
            task_uuid,
            parsed['vendor_task_id'],
            json.dumps(response)
        )
    
    return {'vendor_task_uuid': task_uuid, 'vendor_id': vendor.get('id')}


def _build_success_message(tasks_count: int, material_type: str) -> str:
    """构建成功消息"""
    type_desc = {
        'image': '图片',
        'text': '文字描述',
        'mixed': '图片和文字'
    }
    
    msg = f"已收到您的请求，正在处理中...\n\n"
    msg += f"📊 已提交 {tasks_count} 个供应商\n"
    msg += f"📁 材料类型: {type_desc.get(material_type, '未知')}\n"
    msg += f"\n⏱️ 处理时间通常需要 1-3 分钟\n"
    msg += f"完成后我会通知您~"
    
    return msg


def get_db_path() -> str:
    """获取数据库路径"""
    return os.getenv('DB_PATH', './data/ai-3d-modeling.db')


# ============================================================================
# 便捷入口函数 (供 AI 简单调用)
# ============================================================================

async def handle_user_message(
    message_text: str,
    sender_id: str,
    sender_name: str = "",
    chat_id: str = "",
    message_id: str = "",
    images: List[str] = None
) -> Dict[str, Any]:
    """
    处理用户消息的便捷入口函数
    
    AI 调用此函数处理用户消息，函数内部会根据消息内容
    自动识别意图（建模/取消/状态查询/帮助）并调用相应处理函数。
    
    Args:
        message_text: 用户消息文本
        sender_id: 发送者 ID
        sender_name: 发送者名称
        chat_id: 会话 ID
        message_id: 消息 ID
        images: 图片列表
    
    Returns:
        处理结果
    """
    message_lower = message_text.lower().strip()
    
    # 意图识别
    if any(kw in message_lower for kw in ['取消', '撤销', '停止', 'cancel', 'abort', 'stop']):
        return await process_cancel_request(sender_id, chat_id)
    
    if any(kw in message_lower for kw in ['状态', '进度', '怎么样了', 'status', 'progress']):
        return await process_status_request(sender_id, chat_id)
    
    if any(kw in message_lower for kw in ['帮助', 'help', '怎么用', '使用说明']):
        return {
            'success': True,
            'message': get_help_text(),
            'phase': 'help'
        }
    
    if any(kw in message_lower for kw in ['3d', '三维', '建模', '生成', '模型', 'obj', 'glb', 'stl', 'make 3d', 'generate model', 'create model']):
        return await process_modeling_request(
            user_message=message_text,
            sender_id=sender_id,
            sender_name=sender_name,
            chat_id=chat_id,
            message_id=message_id,
            images=images
        )
    
    # 无法识别
    return {
        'success': True,
        'message': '我不太理解您的意思，请发送"帮助"查看使用方法。',
        'phase': 'unknown'
    }
