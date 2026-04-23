"""
AI-3D 建模系统 - 轮询模块

批量轮询守护进程
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from ai_3d_modeling.db import Database, SessionManager, VendorTaskManager
from ai_3d_modeling.adapters import AdapterFactory
from ai_3d_modeling.storage import StorageManager
from ai_3d_modeling.notifier import ResultSummarizer, FeishuNotifier
from ai_3d_modeling.utils import get_timestamp


logger = logging.getLogger(__name__)


class Poller:
    """轮询守护进程"""
    
    def __init__(self, 
                 db: Database,
                 storage: StorageManager,
                 notifier: FeishuNotifier,
                 interval: int = 60,
                 api_key: str = None):
        """
        初始化轮询器
        
        Args:
            db: 数据库实例
            storage: 存储管理器
            notifier: 通知器
            interval: 轮询间隔（秒）
            api_key: API 密钥
        """
        self.db = db
        self.session_mgr = SessionManager(db)
        self.task_mgr = VendorTaskManager(db)
        self.storage = storage
        self.notifier = notifier
        self.summarizer = ResultSummarizer(db)
        self.interval = interval
        self.api_key = api_key
        self.running = False
    
    def start(self):
        """启动轮询 (同步入口)"""
        logger.info(f"Poller.start called, running={self.running}")
        self.running = True
        
        # 检查是否已有事件循环
        try:
            loop = asyncio.get_running_loop()
            logger.info(f"Found running loop, creating task")
            # 已在事件循环中，使用 create_task
            loop.create_task(self._run())
            logger.info("Task created in running loop")
        except RuntimeError:
            # 没有运行中的事件循环，可以创建新的
            logger.info("No running loop, using asyncio.run")
            asyncio.run(self._run())
    
    async def _run(self):
        """异步运行轮询循环"""
        logger.info(f"Poller _run started, running={self.running}")
        while self.running:
            try:
                await self._poll_once()
            except Exception as e:
                logger.error(f"Poll error: {e}")
            
            await asyncio.sleep(self.interval)
        logger.info("Poller _run finished")
    
    def stop(self):
        """停止轮询"""
        logger.info("Poller stopping")
        self.running = False
    
    async def _poll_once(self):
        """执行一次轮询"""
        # 1. 获取所有运行中的任务
        tasks = self.task_mgr.get_running()
        
        if not tasks:
            logger.debug("No running tasks")
            return
        
        logger.info(f"Polling {len(tasks)} tasks")
        
        # 2. 批量处理任务
        for task in tasks:
            try:
                await self._poll_task(task)
            except Exception as e:
                logger.error(f"Error polling task {task['vendor_task_uuid']}: {e}")
        
        # 3. 检查并发送汇总
        await self._check_and_send_summaries()
    
    async def _poll_task(self, task: Dict):
        """
        轮询单个任务
        
        Args:
            task: 任务字典
        """
        vendor_task_uuid = task['vendor_task_uuid']
        vendor_id = task['vendor_id']
        vendor_task_id = task.get('vendor_task_id')
        
        if not vendor_task_id:
            logger.warning(f"Task {vendor_task_uuid} has no vendor_task_id")
            return
        
        # 1. 获取供应商配置
        vendor_config = self._get_vendor_config(vendor_id)
        if not vendor_config:
            logger.error(f"Vendor config not found: {vendor_id}")
            return
        
        # 2. 创建适配器
        adapter = AdapterFactory.create(vendor_config, self.api_key)
        
        # 3. 增加轮询计数
        self.task_mgr.increment_poll_count(vendor_task_uuid)
        
        # 4. 查询状态
        try:
            response = await adapter.query_status(vendor_task_id)
        except Exception as e:
            logger.error(f"Query failed for {vendor_task_uuid}: {e}")
            return
        
        # 5. 解析响应
        parsed = adapter.parse_response(response)
        
        # 6. 更新状态
        status = parsed.get('status', 'unknown')
        self.task_mgr.update_status(
            vendor_task_uuid,
            status,
            api_response=json.dumps(response)
        )
        
        logger.info(f"Task {vendor_task_uuid} status: {status}")
        
        # 7. 处理完成状态
        if status == 'succeeded':
            file_url = parsed.get('file_url')
            await self._handle_success(task, file_url)
        elif status == 'failed':
            error = parsed.get('error', 'Unknown error')
            await self._handle_failure(task, error)
        elif status == 'timeout':
            await self._handle_timeout(task)
    
    def _get_vendor_config(self, vendor_id: str) -> Optional[Dict]:
        """获取供应商配置"""
        results = self.db.execute(
            "SELECT value FROM settings WHERE key = ? AND category = 'vendor'",
            (vendor_id,)
        )
        
        if results:
            try:
                return json.loads(results[0]['value'])
            except:
                return None
        return None
    
    async def _handle_success(self, task: Dict, file_url: str):
        """
        处理任务成功
        
        Args:
            task: 任务字典
            file_url: 结果文件 URL
        """
        vendor_task_uuid = task['vendor_task_uuid']
        session_uuid = task['session_uuid']
        
        if not file_url:
            logger.warning(f"No file_url for task {vendor_task_uuid}")
            return
        
        try:
            # 1. 上传到 TOS
            result = await self.storage.upload_result(
                vendor_task_uuid=vendor_task_uuid,
                file_url=file_url,
                session_uuid=session_uuid
            )
            
            # 2. 更新任务记录
            self.db.execute('''
                UPDATE vendor_tasks 
                SET tos_result_path = ?, share_url = ?, share_expires_at = ?
                WHERE vendor_task_uuid = ?
            ''', (
                result.get('tos_path'),
                result.get('share_url'),
                int(datetime.now().timestamp()) + 86400,
                vendor_task_uuid
            ))
            
            logger.info(f"Task {vendor_task_uuid} result uploaded to TOS")
        
        except Exception as e:
            logger.error(f"Failed to upload result for {vendor_task_uuid}: {e}")
    
    async def _handle_failure(self, task: Dict, error: str):
        """
        处理任务失败
        
        Args:
            task: 任务字典
            error: 错误信息
        """
        logger.warning(f"Task {task['vendor_task_uuid']} failed: {error}")
    
    async def _handle_timeout(self, task: Dict):
        """
        处理任务超时
        
        Args:
            task: 任务字典
        """
        vendor_task_uuid = task['vendor_task_uuid']
        
        self.task_mgr.update_status(
            vendor_task_uuid,
            'timeout',
            error_message='Task timeout'
        )
        
        logger.warning(f"Task {vendor_task_uuid} timeout")
    
    async def _check_and_send_summaries(self):
        """检查并发送汇总通知"""
        # 获取所有活跃会话
        sessions = self.session_mgr.get_active_sessions()
        
        for session in sessions:
            session_uuid = session['session_uuid']
            
            # 检查是否所有任务都完成
            if self.summarizer.check_all_done(session_uuid):
                try:
                    # 汇总会话
                    summary = self.summarizer.summarize(session_uuid)
                    
                    # 获取 session_key
                    session_key = self._build_session_key(session)
                    
                    # 发送通知
                    await self.notifier.send_summary(session_key, summary)
                    
                    # 更新会话状态
                    self.session_mgr.update_status(session_uuid, 'completed')
                    
                    logger.info(f"Summary sent for session {session_uuid}")
                
                except Exception as e:
                    logger.error(f"Failed to send summary for {session_uuid}: {e}")
    
    def _build_session_key(self, session: Dict) -> str:
        """
        构建会话标识
        
        Args:
            session: 会话字典
        
        Returns:
            session_key 字符串
        """
        channel_type = session.get('channel_type', 'feishu')
        channel_user_id = session.get('channel_user_id', '')
        group_id = session.get('group_id', '')
        
        if group_id:
            return f"feishu:group:{group_id}"
        else:
            return f"feishu:user:{channel_user_id}"


async def run_poller(config: Dict = None):
    """
    运行轮询器
    
    Args:
        config: 配置字典
    """
    config = config or {}
    
    # 初始化组件
    db = Database(config.get('db_path', 'ai-3d-modeling.db'))
    storage = StorageManager(
        bucket=config.get('tos_bucket', '4-ark-claw'),
        base_path=config.get('tos_base_path', 'ai-3d-system')
    )
    notifier = FeishuNotifier(
        gateway_url=config.get('gateway_url', 'http://127.0.0.1:18789/webhook/notify')
    )
    
    # 创建轮询器
    poller = Poller(
        db=db,
        storage=storage,
        notifier=notifier,
        interval=config.get('polling_interval', 60),
        api_key=config.get('api_key')
    )
    
    # 标记为运行中
    poller.running = True
    
    # 直接运行异步轮询循环
    try:
        await poller._run()
    except KeyboardInterrupt:
        logger.info('Poller 已停止')
        poller.stop()


if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    run_poller()
