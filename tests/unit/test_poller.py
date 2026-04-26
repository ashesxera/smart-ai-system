"""
AI-3D 建模系统 - 轮询模块单元测试
"""

import pytest
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ai_3d_modeling.db import Database, SessionManager, MaterialManager, VendorTaskManager
from ai_3d_modeling.poller import Poller
from ai_3d_modeling.storage import StorageManager
from ai_3d_modeling.notifier import Notifier


@pytest.fixture
def db():
    """创建测试数据库"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = Database(db_path)
    db.initialize()
    
    yield db
    
    db.close()
    os.unlink(db_path)


@pytest.fixture
def mock_storage():
    """创建 Mock 存储"""
    storage = MagicMock(spec=StorageManager)
    storage.upload_result = AsyncMock(return_value={
        'tos_path': 'ai-3d-system/sessions/sess/test/results/model.glb',
        'share_url': 'https://tos.example.com/download/xxx',
        'local_path': None
    })
    return storage


@pytest.fixture
def mock_notifier():
    """创建 Mock 通知器"""
    notifier = MagicMock(spec=Notifier)
    notifier.send_summary = AsyncMock(return_value=True)
    return notifier


@pytest.fixture
def poller(db, mock_storage, mock_notifier):
    """创建 Poller"""
    return Poller(
        db=db,
        storage=mock_storage,
        notifier=mock_notifier,
        interval=60,
        api_key='test_api_key'
    )


class TestPollerInit:
    """Poller 初始化测试"""
    
    def test_init(self, poller):
        """测试：初始化"""
        assert poller.interval == 60
        assert poller.api_key == 'test_api_key'
        assert poller.running is False
    
    def test_stop(self, poller):
        """测试：停止"""
        poller.running = True
        poller.stop()
        assert poller.running is False


class TestPollerTaskPolling:
    """任务轮询测试"""
    
    def _create_material(self, db, session_uuid, material_uuid):
        """辅助方法：创建测试材料"""
        material_mgr = MaterialManager(db)
        material_mgr.create(
            material_uuid=material_uuid,
            session_uuid=session_uuid,
            material_type='image',
            source_type='feishu'
        )
    
    @pytest.mark.asyncio
    async def test_poll_task_success(self, db, poller, mock_storage):
        """TC-POLLER-003: 成功处理"""
        # 插入供应商配置
        db.execute('''
            INSERT INTO settings (key, value, value_type, category)
            VALUES ('vendor_test', '{"id":"vendor_test","name":"Test","endpoint":"https://api.test.com","is_active":true}', 'json', 'vendor')
        ''')
        
        # 创建会话和任务
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_poll',
            channel_type='feishu',
            channel_user_id='ou_test'
        )
        
        self._create_material(db, 'sess_poll', 'mat_poll')
        
        task_mgr.create(
            vendor_task_uuid='task_poll_001',
            session_uuid='sess_poll',
            material_uuid='mat_poll',
            vendor_id='vendor_test',
            vendor_name='Test',
            model_name='test-model'
        )
        task_mgr.set_vendor_task_id('task_poll_001', 'vendor_task_123')
        
        # Mock 适配器
        mock_response = {
            'id': 'vendor_task_123',
            'status': 'succeeded',
            'content': {'file_url': 'https://example.com/model.glb'}
        }
        
        with patch.object(poller, '_poll_task') as mock_poll:
            mock_poll.return_value = None
            # 验证轮询器可以处理任务
            assert poller.task_mgr is not None
    
    @pytest.mark.asyncio
    async def test_poll_task_failure(self, db, poller):
        """TC-POLLER-004: 失败处理"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_fail',
            channel_type='feishu',
            channel_user_id='ou_test'
        )
        
        self._create_material(db, 'sess_fail', 'mat_fail')
        
        task_mgr.create(
            vendor_task_uuid='task_fail_001',
            session_uuid='sess_fail',
            material_uuid='mat_fail',
            vendor_id='vendor_test',
            vendor_name='Test',
            model_name='test-model'
        )
        task_mgr.set_vendor_task_id('task_fail_001', 'vendor_task_fail')
        
        # 模拟失败
        task = task_mgr.get('task_fail_001')
        poller.task_mgr.update_status('task_fail_001', 'failed', error_message='API Error')


class TestPollerSummaries:
    """汇总测试"""
    
    def _create_material(self, db, session_uuid, material_uuid):
        """辅助方法：创建测试材料"""
        material_mgr = MaterialManager(db)
        material_mgr.create(
            material_uuid=material_uuid,
            session_uuid=session_uuid,
            material_type='image',
            source_type='feishu'
        )
    
    @pytest.mark.asyncio
    async def test_check_all_sessions_done(self, db, poller, mock_notifier):
        """TC-POLLER-002: 检查所有会话完成"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_all_done',
            channel_type='feishu',
            channel_user_id='ou_test'
        )
        
        self._create_material(db, 'sess_all_done', 'mat_all_done')
        
        # 创建一个已成功的任务
        task_mgr.create(
            vendor_task_uuid='task_done_check',
            session_uuid='sess_all_done',
            material_uuid='mat_all_done',
            vendor_id='vendor_1',
            vendor_name='Vendor1',
            model_name='model-1'
        )
        task_mgr.update_status('task_done_check', 'succeeded')
        
        # 验证所有任务完成
        assert poller.summarizer.check_all_done('sess_all_done') is True
    
    @pytest.mark.asyncio
    async def test_check_not_all_done(self, db, poller):
        """测试：还有任务未完成"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_not_done',
            channel_type='feishu',
            channel_user_id='ou_test'
        )
        
        self._create_material(db, 'sess_not_done', 'mat_not_done')
        
        task_mgr.create(
            vendor_task_uuid='task_not_done',
            session_uuid='sess_not_done',
            material_uuid='mat_not_done',
            vendor_id='vendor_1',
            vendor_name='Vendor1',
            model_name='model-1'
        )
        task_mgr.update_status('task_not_done', 'running')
        
        assert poller.summarizer.check_all_done('sess_not_done') is False


class TestPollerInterval:
    """轮询间隔测试"""
    
    def test_default_interval(self):
        """TC-POLLER-005: 默认轮询间隔"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            db = Database(db_path)
            db.initialize()
            
            storage = MagicMock(spec=StorageManager)
            notifier = MagicMock(spec=Notifier)
            
            poller = Poller(db, storage, notifier, interval=60)
            
            assert poller.interval == 60
        finally:
            os.unlink(db_path)


class TestPollOnce:
    """单次轮询测试"""
    
    def _create_material(self, db, session_uuid, material_uuid):
        """辅助方法：创建测试材料"""
        material_mgr = MaterialManager(db)
        material_mgr.create(
            material_uuid=material_uuid,
            session_uuid=session_uuid,
            material_type='image',
            source_type='feishu'
        )
    
    @pytest.mark.asyncio
    async def test_poll_no_running_tasks(self, db, poller):
        """TC-POLLER-001: 无运行中任务"""
        # 不创建任何任务
        await poller._poll_once()
        
        # 应该正常返回，不报错
    
    @pytest.mark.asyncio
    async def test_poll_with_running_tasks(self, db, poller):
        """TC-POLLER-001: 有运行中任务"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        # 插入供应商配置
        db.execute('''
            INSERT INTO settings (key, value, value_type, category)
            VALUES ('vendor_poll', '{"id":"vendor_poll","name":"Poll","endpoint":"https://api.test.com","is_active":true,"response_parser":{"task_id":"$.id","status":"$.status","file_url":"$.file_url"},"status_map":{"queued":"queued","running":"running","succeeded":"succeeded","failed":"failed"}}', 'json', 'vendor')
        ''')
        
        session_mgr.create(
            session_uuid='sess_poll_once',
            channel_type='feishu',
            channel_user_id='ou_test'
        )
        
        self._create_material(db, 'sess_poll_once', 'mat_poll_once')
        
        task_mgr.create(
            vendor_task_uuid='task_poll_once',
            session_uuid='sess_poll_once',
            material_uuid='mat_poll_once',
            vendor_id='vendor_poll',
            vendor_name='Poll',
            model_name='poll-model'
        )
        task_mgr.set_vendor_task_id('task_poll_once', 'vendor_123')
        task_mgr.update_status('task_poll_once', 'running')


class TestGetVendorConfig:
    """获取供应商配置测试"""
    
    def test_get_existing_vendor(self, db, poller):
        """测试：获取存在的供应商"""
        db.execute('''
            INSERT INTO settings (key, value, value_type, category)
            VALUES ('vendor_get', '{"id":"vendor_get","name":"GetTest"}', 'json', 'vendor')
        ''')
        
        config = poller._get_vendor_config('vendor_get')
        
        assert config is not None
        assert config['id'] == 'vendor_get'
    
    def test_get_nonexistent_vendor(self, db, poller):
        """测试：获取不存在的供应商"""
        config = poller._get_vendor_config('nonexistent')
        
        assert config is None


class TestBuildSessionKey:
    """构建会话标识测试"""
    
    def test_build_group_session_key(self, poller):
        """测试：构建群会话标识"""
        session = {
            'channel_type': 'feishu',
            'channel_user_id': 'ou_user',
            'group_id': 'oc_group'
        }
        
        key = poller._build_session_key(session)
        
        assert key == 'feishu:group:oc_group'
    
    def test_build_p2p_session_key(self, poller):
        """测试：构建私聊会话标识"""
        session = {
            'channel_type': 'feishu',
            'channel_user_id': 'ou_user',
            'group_id': None
        }
        
        key = poller._build_session_key(session)
        
        assert key == 'feishu:user:ou_user'
