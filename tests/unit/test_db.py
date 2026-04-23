"""
AI-3D 建模系统 - 数据库模块单元测试
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ai_3d_modeling.db import (
    Database,
    SessionManager,
    MaterialManager,
    VendorTaskManager,
    ResultManager
)


@pytest.fixture
def db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = Database(db_path)
    db.initialize()
    
    yield db
    
    db.close()
    os.unlink(db_path)


class TestDatabase:
    """Database 测试"""
    
    def test_initialize_creates_tables(self, db):
        """TC-DB-001: 初始化数据库"""
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        table_names = [t['name'] for t in tables]
        
        assert 'sessions' in table_names
        assert 'materials' in table_names
        assert 'vendor_tasks' in table_names
        assert 'results' in table_names
        assert 'ops_log' in table_names
        assert 'settings' in table_names
    
    def test_connection_reuse(self, db):
        """TC-DB-002: 数据库连接复用"""
        conn1 = db.get_connection()
        conn2 = db.get_connection()
        
        assert conn1 is conn2


class TestSessionManager:
    """SessionManager 测试"""
    
    def test_create_session(self, db):
        """TC-SESSION-001: 创建会话"""
        manager = SessionManager(db)
        
        session = manager.create(
            session_uuid='sess_test_001',
            channel_type='feishu',
            channel_user_id='ou_123',
            channel_user_name='测试用户'
        )
        
        assert session['session_uuid'] == 'sess_test_001'
        assert session['status'] == 'active'
        assert session['phase'] == 'pending'
    
    def test_get_session(self, db):
        """TC-SESSION-002: 获取会话"""
        manager = SessionManager(db)
        
        manager.create(
            session_uuid='sess_test_002',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        session = manager.get('sess_test_002')
        
        assert session is not None
        assert session['session_uuid'] == 'sess_test_002'
    
    def test_get_session_not_found(self, db):
        """测试：获取不存在的会话"""
        manager = SessionManager(db)
        
        session = manager.get('nonexistent')
        
        assert session is None
    
    def test_update_session_phase(self, db):
        """TC-SESSION-003: 更新会话阶段"""
        manager = SessionManager(db)
        
        manager.create(
            session_uuid='sess_test_003',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        manager.update_phase('sess_test_003', 'materials_ready')
        
        session = manager.get('sess_test_003')
        assert session['phase'] == 'materials_ready'
    
    def test_update_session_status(self, db):
        """测试：更新会话状态"""
        manager = SessionManager(db)
        
        manager.create(
            session_uuid='sess_test_004',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        manager.update_status('sess_test_004', 'completed')
        
        session = manager.get('sess_test_004')
        assert session['status'] == 'completed'
    
    def test_get_active_sessions(self, db):
        """TC-SESSION-004: 获取活跃会话"""
        manager = SessionManager(db)
        
        manager.create(
            session_uuid='sess_active_1',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        manager.create(
            session_uuid='sess_active_2',
            channel_type='feishu',
            channel_user_id='ou_456'
        )
        manager.create(
            session_uuid='sess_completed',
            channel_type='feishu',
            channel_user_id='ou_789'
        )
        
        # 手动设置一个为 completed
        manager.update_status('sess_completed', 'completed')
        
        active = manager.get_active_sessions()
        
        assert len(active) == 2
        assert all(s['status'] == 'active' for s in active)


class TestMaterialManager:
    """MaterialManager 测试"""
    
    def test_create_material(self, db):
        """TC-MATERIAL-001: 创建材料记录"""
        session_mgr = SessionManager(db)
        material_mgr = MaterialManager(db)
        
        session_mgr.create(
            session_uuid='sess_mat_001',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        material = material_mgr.create(
            material_uuid='mat_test_001',
            session_uuid='sess_mat_001',
            material_type='image',
            source_type='feishu',
            text_content='测试描述',
            image_urls=['https://example.com/1.jpg']
        )
        
        assert material['material_uuid'] == 'mat_test_001'
        assert material['material_type'] == 'image'
    
    def test_get_material(self, db):
        """测试：获取材料"""
        session_mgr = SessionManager(db)
        material_mgr = MaterialManager(db)
        
        session_mgr.create(
            session_uuid='sess_mat_002',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        material_mgr.create(
            material_uuid='mat_test_002',
            session_uuid='sess_mat_002',
            material_type='text',
            source_type='feishu',
            text_content='纯文字'
        )
        
        material = material_mgr.get('mat_test_002')
        
        assert material is not None
        assert material['text_content'] == '纯文字'
    
    def test_get_materials_by_session(self, db):
        """TC-MATERIAL-002: 按会话获取材料"""
        session_mgr = SessionManager(db)
        material_mgr = MaterialManager(db)
        
        session_mgr.create(
            session_uuid='sess_mat_003',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        material_mgr.create(
            material_uuid='mat_1',
            session_uuid='sess_mat_003',
            material_type='image',
            source_type='feishu'
        )
        material_mgr.create(
            material_uuid='mat_2',
            session_uuid='sess_mat_003',
            material_type='image',
            source_type='feishu'
        )
        
        materials = material_mgr.get_by_session('sess_mat_003')
        
        assert len(materials) == 2


class TestVendorTaskManager:
    """VendorTaskManager 测试"""
    
    def test_create_vendor_task(self, db):
        """TC-TASK-001: 创建供应商任务"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_task_001',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        task = task_mgr.create(
            vendor_task_uuid='task_test_001',
            session_uuid='sess_task_001',
            material_uuid='mat_001',
            vendor_id='vendor_seed3d',
            vendor_name='Seed3D',
            model_name='doubao-seed3d',
            api_endpoint='https://api.example.com/submit'
        )
        
        assert task['vendor_task_uuid'] == 'task_test_001'
        assert task['status'] == 'pending'
        assert task['poll_count'] == 0
    
    def test_get_running_tasks(self, db):
        """TC-TASK-002: 获取运行中任务"""
        # 先插入供应商配置
        db.execute('''
            INSERT INTO settings (key, value, value_type, category)
            VALUES ('vendor_seed3d', '{"is_active": true}', 'json', 'vendor')
        ''')
        
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_running',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        task_mgr.create(
            vendor_task_uuid='task_running_1',
            session_uuid='sess_running',
            material_uuid='mat_001',
            vendor_id='vendor_seed3d',
            vendor_name='Seed3D',
            model_name='doubao-seed3d'
        )
        
        # 更新状态为 running
        db.execute('''
            UPDATE vendor_tasks SET status = 'running' 
            WHERE vendor_task_uuid = 'task_running_1'
        ''')
        
        running = task_mgr.get_running()
        
        assert len(running) >= 1
    
    def test_update_task_status(self, db):
        """TC-TASK-003: 更新任务状态"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_status',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        task_mgr.create(
            vendor_task_uuid='task_status_001',
            session_uuid='sess_status',
            material_uuid='mat_001',
            vendor_id='vendor_seed3d',
            vendor_name='Seed3D',
            model_name='doubao-seed3d'
        )
        
        task_mgr.update_status('task_status_001', 'running')
        
        task = task_mgr.get('task_status_001')
        assert task['status'] == 'running'
    
    def test_set_vendor_task_id(self, db):
        """TC-TASK-004: 设置供应商任务ID"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_vendor_id',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        task_mgr.create(
            vendor_task_uuid='task_vid_001',
            session_uuid='sess_vendor_id',
            material_uuid='mat_001',
            vendor_id='vendor_seed3d',
            vendor_name='Seed3D',
            model_name='doubao-seed3d'
        )
        
        task_mgr.set_vendor_task_id('task_vid_001', 'ark_12345')
        
        task = task_mgr.get('task_vid_001')
        assert task['vendor_task_id'] == 'ark_12345'
        assert task['status'] == 'queued'
    
    def test_increment_poll_count(self, db):
        """TC-TASK-005: 增加轮询计数"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_poll',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        task_mgr.create(
            vendor_task_uuid='task_poll_001',
            session_uuid='sess_poll',
            material_uuid='mat_001',
            vendor_id='vendor_seed3d',
            vendor_name='Seed3D',
            model_name='doubao-seed3d'
        )
        
        task_mgr.increment_poll_count('task_poll_001')
        task_mgr.increment_poll_count('task_poll_001')
        
        task = task_mgr.get('task_poll_001')
        assert task['poll_count'] == 2
    
    def test_check_all_done_true(self, db):
        """TC-TASK-006: 会话所有任务完成"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_done',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        task_mgr.create(
            vendor_task_uuid='task_done_1',
            session_uuid='sess_done',
            material_uuid='mat_001',
            vendor_id='vendor_1',
            vendor_name='Vendor1',
            model_name='model-1'
        )
        task_mgr.create(
            vendor_task_uuid='task_done_2',
            session_uuid='sess_done',
            material_uuid='mat_001',
            vendor_id='vendor_2',
            vendor_name='Vendor2',
            model_name='model-2'
        )
        
        # 两个都成功
        task_mgr.update_status('task_done_1', 'succeeded')
        task_mgr.update_status('task_done_2', 'succeeded')
        
        assert task_mgr.check_all_done('sess_done') is True
    
    def test_check_all_done_false(self, db):
        """TC-TASK-006: 还有任务未完成"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_partial',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        task_mgr.create(
            vendor_task_uuid='task_part_1',
            session_uuid='sess_partial',
            material_uuid='mat_001',
            vendor_id='vendor_1',
            vendor_name='Vendor1',
            model_name='model-1'
        )
        task_mgr.create(
            vendor_task_uuid='task_part_2',
            session_uuid='sess_partial',
            material_uuid='mat_001',
            vendor_id='vendor_2',
            vendor_name='Vendor2',
            model_name='model-2'
        )
        
        # 一个成功，一个还在运行
        task_mgr.update_status('task_part_1', 'succeeded')
        task_mgr.update_status('task_part_2', 'running')
        
        assert task_mgr.check_all_done('sess_partial') is False


class TestResultManager:
    """ResultManager 测试"""
    
    def test_create_result(self, db):
        """测试：创建结果记录"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        result_mgr = ResultManager(db)
        
        session_mgr.create(
            session_uuid='sess_result',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        task_mgr.create(
            vendor_task_uuid='task_result_001',
            session_uuid='sess_result',
            material_uuid='mat_001',
            vendor_id='vendor_seed3d',
            vendor_name='Seed3D',
            model_name='doubao-seed3d'
        )
        
        result = result_mgr.create(
            result_uuid='result_001',
            vendor_task_uuid='task_result_001',
            file_name='model.glb',
            file_size=12345,
            file_format='glb',
            tos_path='ai-3d-system/sessions/sess_result/results/model.glb'
        )
        
        assert result['result_uuid'] == 'result_001'
        assert result['file_format'] == 'glb'
