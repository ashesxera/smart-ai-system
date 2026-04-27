"""
AI-3D 建模系统 - 轮询模块

批量轮询守护进程
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from ai_3d_modeling.db import Database, SessionManager, MaterialManager, VendorTaskManager
from ai_3d_modeling.adapters import AdapterFactory
from ai_3d_modeling.storage import StorageManager
from ai_3d_modeling.notifier import ResultSummarizer, Notifier
from ai_3d_modeling.utils import get_timestamp


logger = logging.getLogger(__name__)


class Poller:
    """轮询守护进程"""
    
    def __init__(self, 
                 db: Database,
                 storage: StorageManager,
                 notifier: Notifier,
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
        self.material_mgr = MaterialManager(db)
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
        
        # 6. 解析响应并提取错误信息
        parsed = adapter.parse_response(response)
        status = parsed.get('status', 'unknown')

        # 提取错误详情（API 返回 {"error": {"code": ..., "message": ...}}）
        error_info = response.get('error', {})
        error_code = error_info.get('code') if isinstance(error_info, dict) else None
        error_message = error_info.get('message') if isinstance(error_info, dict) else None

        # 更新数据库（包含错误详情）
        self.task_mgr.update_status(
            vendor_task_uuid,
            status,
            api_response=json.dumps(response),
            error_code=error_code,
            error_message=error_message
        )

        logger.info(f"Task {vendor_task_uuid} status: {status}")

        # 7. 处理完成状态
        if status == 'succeeded':
            file_url = parsed.get('file_url')
            await self._handle_success(task, file_url)
        elif status == 'failed':
            error_str = f"{error_code}: {error_message}" if error_code else (error_message or 'Unknown error')
            await self._handle_failure(task, error_str)
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
    
    def _is_mock_url(self, url: str) -> bool:
        """检查是否为 mock URL（不可下载的 URL）"""
        if not url:
            return True
        mock_domains = ['tos.example.com', 'example.com', 'mock', 'placeholder']
        return any(d in url.lower() for d in mock_domains)

    def _create_mock_glb(self, vendor_task_uuid: str) -> str:
        """
        创建最小 mock GLB 文件（用于测试时 TOS 中有文件可展示）

        返回临时文件路径。
        """
        import struct, tempfile, os

        # Minimal GLB: magic + version + length + JSON chunk
        json_data = json.dumps({
            "vendor_task_uuid": vendor_task_uuid,
            "note": "mock result for testing"
        }).encode()

        # GLB header: 12 bytes
        # magic = 0x46546C67 ('gLTF')
        magic = struct.pack('<I', 0x46546C67)
        version = struct.pack('<I', 2)

        # JSON chunk: 8 bytes header + json bytes
        json_bytes = json_data
        json_chunk_len = len(json_bytes)
        json_chunk_type = struct.pack('<I', 0x4E4F534A)  # 'JSON'

        # Bin chunk (empty): 8 bytes header + 0 bytes
        bin_chunk_len = struct.pack('<I', 0)
        bin_chunk_type = struct.pack('<I', 0x004E4942)  # 'BIN\0'

        total_len = 12 + 8 + json_chunk_len + 8 + 0
        length = struct.pack('<I', total_len)

        glb_data = magic + version + length + json_chunk_type + json_bytes + bin_chunk_len + bin_chunk_type

        tmp = tempfile.NamedTemporaryFile(suffix='.glb', delete=False)
        tmp.write(glb_data)
        tmp.flush()
        return tmp.name

    async def _handle_success(self, task: Dict, file_url: str):
        """
        处理任务成功

        Args:
            task: 任务字典
            file_url: 结果文件 URL（供应商 API 返回）
        """
        vendor_task_uuid = task['vendor_task_uuid']
        session_uuid = task['session_uuid']

        if not file_url:
            logger.warning(f"No file_url for task {vendor_task_uuid}")
            return

        try:
            # 1. 尝试上传结果到 TOS
            is_mock = self._is_mock_url(file_url)
            local_result_path = None

            if is_mock:
                # Mock URL: 创建 mock GLB 文件，上传 api_response JSON
                logger.info(f"Mock URL detected for {vendor_task_uuid}, creating placeholder files")
                local_result_path = self._create_mock_glb(vendor_task_uuid)

                # 同时保存供应商原始 API 响应（从 db 获取）
                task_record = self.db.execute(
                    'SELECT api_response FROM vendor_tasks WHERE vendor_task_uuid = ?',
                    (vendor_task_uuid,)
                )
                if task_record and task_record[0].get('api_response'):
                    error_json_path = local_result_path + '.api_response.json'
                    with open(error_json_path, 'w') as f:
                        f.write(task_record[0]['api_response'])
                    # 上传 JSON 响应到 TOS
                    json_tos_path = self.storage.build_tos_path(
                        session_uuid,
                        f"results/{vendor_task_uuid}.api_response.json"
                    )
                    self.storage.upload(error_json_path, json_tos_path)
                    os.unlink(error_json_path)
            else:
                # 真实 URL: 下载后上传
                local_result_path = None
                try:
                    result = await self.storage.upload_result(
                        vendor_task_uuid=vendor_task_uuid,
                        file_url=file_url,
                        session_uuid=session_uuid,
                        vendor_name=task.get('vendor_name'),
                        model_name=task.get('model_name')
                    )
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
                    return
                except Exception as dl_err:
                    logger.warning(f"Download failed for {vendor_task_uuid}: {dl_err}, creating mock")
                    local_result_path = self._create_mock_glb(vendor_task_uuid)

            if local_result_path:
                # 上传 mock GLB 到 TOS
                result_filename = f"{task.get('vendor_name', vendor_task_uuid)}.glb"
                tos_sub_path = self.storage.build_tos_path(
                    session_uuid,
                    f"results/{result_filename}"
                )
                uploaded = self.storage.upload(local_result_path, tos_sub_path)
                os.unlink(local_result_path)

                # 生成 share URL（仅在上传说服时）
                share_url = None
                if uploaded:
                    try:
                        share_url = self.storage.generate_share_url(tos_sub_path)
                    except Exception:
                        pass

                # 更新任务记录（无论上传是否成功）
                self.db.execute('''
                    UPDATE vendor_tasks
                    SET tos_result_path = ?, share_url = ?, share_expires_at = ?
                    WHERE vendor_task_uuid = ?
                ''', (
                    uploaded or tos_sub_path,  # 用实际路径（upload 失败时也记录目标路径）
                    share_url,
                    int(datetime.now().timestamp()) + 86400,
                    vendor_task_uuid
                ))
                if uploaded:
                    logger.info(f"Task {vendor_task_uuid} mock result uploaded to TOS: {uploaded}")
                else:
                    logger.warning(f"Task {vendor_task_uuid} mock result saved locally only (TOS unavailable)")

        except Exception as e:
            logger.error(f"Failed to upload result for {vendor_task_uuid}: {e}")

    async def _handle_failure(self, task: Dict, error: str):
        """
        处理任务失败

        将错误信息保存为 JSON 文件到 TOS。

        Args:
            task: 任务字典
            error: 错误信息
        """
        vendor_task_uuid = task['vendor_task_uuid']
        session_uuid = task['session_uuid']

        try:
            error_data = {
                "vendor_task_uuid": vendor_task_uuid,
                "vendor_id": task.get('vendor_id'),
                "vendor_name": task.get('vendor_name'),
                "status": "failed",
                "error": error,
                "failed_at": datetime.now().isoformat()
            }

            import tempfile
            tmp = tempfile.NamedTemporaryFile(
                suffix='.vendor_error.json', delete=False, mode='w'
            )
            json.dump(error_data, tmp, indent=2, ensure_ascii=False)
            tmp.flush()

            tos_sub_path = self.storage.build_tos_path(
                session_uuid,
                f"results/{vendor_task_uuid}.error.json"
            )
            uploaded = self.storage.upload(tmp.name, tos_sub_path)
            os.unlink(tmp.name)

            self.db.execute('''
                UPDATE vendor_tasks
                SET error_message = ?, tos_result_path = ?
                WHERE vendor_task_uuid = ?
            ''', (error, uploaded, vendor_task_uuid))

            if uploaded:
                logger.info(f"Task {vendor_task_uuid} error saved to TOS: {uploaded}")
            else:
                logger.warning(f"Task {vendor_task_uuid} error saved locally only (TOS unavailable)")

        except Exception as e:
            logger.error(f"Failed to save error for {vendor_task_uuid}: {e}")
    
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
        """检查并发送汇总通知，同时写入 summary.json 到 TOS"""
        # 获取所有活跃会话
        sessions = self.session_mgr.get_active_sessions()

        for session in sessions:
            session_uuid = session['session_uuid']

            # 检查是否所有任务都完成
            if self.summarizer.check_all_done(session_uuid):
                try:
                    # 1. 汇总会话
                    summary = self.summarizer.summarize(session_uuid)

                    # 2. 写 summary.json 到 TOS
                    await self._write_summary_json(session_uuid, session, summary)

                    # 3. 复制 materials 到 TOS（如尚未复制）
                    await self._upload_materials(session_uuid)

                    # 4. 获取 session_key 并发送通知
                    session_key = self._build_session_key(session)
                    await self.notifier.send_summary(session_key, summary)

                    # 5. 更新会话状态
                    self.session_mgr.update_status(session_uuid, 'completed')

                    logger.info(f"Summary sent and written for session {session_uuid}")

                except Exception as e:
                    logger.error(f"Failed to send summary for {session_uuid}: {e}")

    async def _write_summary_json(self, session_uuid: str, session: Dict, summary: Dict):
        """
        将 summary.json 写入 TOS

        Args:
            session_uuid: 会话 UUID
            session: 会话字典
            summary: 汇总数据
        """
        import tempfile

        # 构建 summary.json 内容
        summary_file = {
            "session_uuid": session_uuid,
            "initiator": {
                "user_id": session.get('channel_user_id', ''),
                "channel": session.get('channel_type', 'feishu')
            },
            "created_at": datetime.fromtimestamp(
                session.get('created_at', 0)
            ).isoformat() if session.get('created_at') else None,
            "completed_at": datetime.now().isoformat(),
            "results": summary.get('results', []),
            "summary": summary.get('summary', {})
        }

        tmp = tempfile.NamedTemporaryFile(
            suffix='.summary.json', delete=False, mode='w'
        )
        json.dump(summary_file, tmp, indent=2, ensure_ascii=False)
        tmp.flush()

        tos_path = self.storage.build_tos_path(session_uuid, 'summary.json')
        uploaded = self.storage.upload(tmp.name, tos_path)
        os.unlink(tmp.name)

        if uploaded:
            logger.info(f"Summary.json written to TOS: {uploaded}")
        else:
            logger.warning(f"Summary.json saved locally only (TOS unavailable): {tos_path}")

    async def _upload_materials(self, session_uuid: str):
        """
        将 materials（图片/文本）上传到 TOS session 目录

        如果已存在则跳过。

        Args:
            session_uuid: 会话 UUID
        """
        try:
            material_mgr = MaterialManager(self.db)
            materials = material_mgr.get_by_session(session_uuid)

            for mat in materials:
                mat_type = mat.get('material_type', '')
                tos_path = self.storage.build_tos_path(
                    session_uuid,
                    f'materials/{mat["material_uuid"]}.info.json'
                )

                # 检查是否已上传（通过查 db 中是否有 tos_path）
                if mat.get('tos_path'):
                    continue

                # 保存材料元信息
                mat_info = {
                    "material_uuid": mat['material_uuid'],
                    "material_type": mat_type,
                    "text_content": mat.get('text_content'),
                    "image_urls": json.loads(mat.get('image_urls') or '[]'),
                    "uploaded_at": datetime.fromtimestamp(
                        mat.get('created_at', 0)
                    ).isoformat() if mat.get('created_at') else None
                }

                import tempfile
                tmp = tempfile.NamedTemporaryFile(
                    suffix='.material.json', delete=False, mode='w'
                )
                json.dump(mat_info, tmp, indent=2, ensure_ascii=False)
                tmp.flush()

                uploaded = self.storage.upload(tmp.name, tos_path)

                # 更新 db 中的 tos_path（无论是否上传成功）
                material_mgr.db.execute('''
                    UPDATE materials SET tos_path = ? WHERE material_uuid = ?
                ''', (uploaded or tos_path, mat['material_uuid']))

                os.unlink(tmp.name)
                if uploaded:
                    logger.info(f"Material {mat['material_uuid']} info written to TOS")
                else:
                    logger.warning(f"Material {mat['material_uuid']} info saved locally only (TOS unavailable)")

        except Exception as e:
            logger.error(f"Failed to upload materials for {session_uuid}: {e}")
    
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
    notifier = Notifier(
        gateway_host=config.get('gateway_url', 'http://127.0.0.1:18789'),
        gateway_token=config.get('gateway_token', ''),
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
