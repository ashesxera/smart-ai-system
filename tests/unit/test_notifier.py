"""
AI-3D 建模系统 - 通知模块单元测试
"""

import pytest
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ai_3d_modeling.db import Database, SessionManager, MaterialManager, VendorTaskManager
from ai_3d_modeling.notifier import ResultSummarizer, FeishuNotifier


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
def summarizer(db):
    """创建 ResultSummarizer"""
    return ResultSummarizer(db)


@pytest.fixture
def notifier():
    """创建 FeishuNotifier"""
    return FeishuNotifier(gateway_url='http://127.0.0.1:18789/webhook/notify')


class TestResultSummarizer:
    """ResultSummarizer 测试"""
    
    def test_summarize_success_results(self, db, summarizer):
        """TC-SUM-001: 汇总成功结果"""
        # 创建测试数据
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_sum_001',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        # 创建成功任务
        task_mgr.create(
            vendor_task_uuid='task_sum_1',
            session_uuid='sess_sum_001',
            material_uuid='mat_001',
            vendor_id='vendor_1',
            vendor_name='Vendor1',
            model_name='model-1'
        )
        task_mgr.update_status('task_sum_1', 'succeeded', result_file_url='https://example.com/1.glb')
        
        # 创建失败任务
        task_mgr.create(
            vendor_task_uuid='task_sum_2',
            session_uuid='sess_sum_001',
            material_uuid='mat_001',
            vendor_id='vendor_2',
            vendor_name='Vendor2',
            model_name='model-2'
        )
        task_mgr.update_status('task_sum_2', 'failed', error_message='API error')
        
        # 汇总
        summary = summarizer.summarize('sess_sum_001')
        
        assert summary['event'] == 'all_vendors_completed'
        assert summary['summary']['total_vendors'] == 2
        assert summary['summary']['succeeded'] == 1
        assert summary['summary']['failed'] == 1
    
    def test_check_all_done_true(self, db, summarizer):
        """TC-SUM-002: 检查所有任务完成 - True"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_done_001',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        task_mgr.create(
            vendor_task_uuid='task_done_1',
            session_uuid='sess_done_001',
            material_uuid='mat_001',
            vendor_id='vendor_1',
            vendor_name='Vendor1',
            model_name='model-1'
        )
        task_mgr.update_status('task_done_1', 'succeeded')
        
        assert summarizer.check_all_done('sess_done_001') is True
    
    def test_check_all_done_false(self, db, summarizer):
        """TC-SUM-002: 检查所有任务完成 - False"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_done_002',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        task_mgr.create(
            vendor_task_uuid='task_done_2',
            session_uuid='sess_done_002',
            material_uuid='mat_001',
            vendor_id='vendor_1',
            vendor_name='Vendor1',
            model_name='model-1'
        )
        task_mgr.update_status('task_done_2', 'running')
        
        assert summarizer.check_all_done('sess_done_002') is False
    
    def test_calculate_duration(self, db, summarizer):
        """TC-SUM-003: 计算总耗时"""
        import time
        
        session_mgr = SessionManager(db)
        
        session_mgr.create(
            session_uuid='sess_dur_001',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        # 计算耗时（会话刚创建，应该很短）
        duration = summarizer.calculate_duration('sess_dur_001')
        
        assert isinstance(duration, int)
        assert duration >= 0
    
    def test_build_materials_preview(self, db, summarizer):
        """TC-SUM-004: 构建材料预览"""
        session_mgr = SessionManager(db)
        material_mgr = MaterialManager(db)
        
        session_mgr.create(
            session_uuid='sess_mat_preview',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        material_mgr.create(
            material_uuid='mat_preview_001',
            session_uuid='sess_mat_preview',
            material_type='image',
            source_type='feishu',
            image_urls=['https://example.com/1.jpg']
        )
        
        preview = summarizer.build_materials_preview('sess_mat_preview')
        
        assert preview['type'] == 'image'
        assert preview['count'] == 1


class TestFeishuNotifier:
    """FeishuNotifier 测试"""
    
    def test_build_feishu_card(self, notifier):
        """TC-NOTIFY-001: 构建飞书卡片"""
        summary = {
            'summary': {
                'total_vendors': 3,
                'succeeded': 2,
                'failed': 1
            },
            'results': [
                {
                    'vendor_name': 'Seed3D',
                    'status': 'succeeded',
                    'file_format': 'glb',
                    'share_url': 'https://example.com/1.glb'
                },
                {
                    'vendor_name': 'Vendor2',
                    'status': 'failed',
                    'error_message': 'API error'
                }
            ]
        }
        
        card = notifier.build_card(summary)
        
        assert card['msg_type'] == 'interactive'
        assert 'card' in card
        assert 'header' in card['card']
    
    def test_format_duration_in_card(self, notifier):
        """TC-NOTIFY-003: 通知内容格式化"""
        from ai_3d_modeling.utils import format_duration
        
        result = format_duration(125)
        
        assert result == "2分5秒"
    
    def test_show_failure_in_card(self, notifier):
        """TC-NOTIFY-004: 失败结果展示"""
        summary = {
            'summary': {'total_vendors': 1, 'succeeded': 0, 'failed': 1},
            'results': [
                {
                    'vendor_name': 'FailedVendor',
                    'status': 'failed',
                    'error_code': 'IMAGE_TOO_SMALL',
                    'error_message': '图片分辨率过低'
                }
            ]
        }
        
        card = notifier.build_card(summary)
        
        # 验证卡片包含错误信息
        elements = card['card']['elements']
        text_content = str(elements)
        
        assert 'IMAGE_TOO_SMALL' in text_content or '图片分辨率过低' in text_content
    
    def test_show_success_in_card(self, notifier):
        """TC-NOTIFY-005: 成功结果展示"""
        summary = {
            'summary': {'total_vendors': 1, 'succeeded': 1, 'failed': 0},
            'results': [
                {
                    'vendor_name': 'SuccessVendor',
                    'status': 'succeeded',
                    'file_format': 'glb',
                    'share_url': 'https://example.com/model.glb'
                }
            ]
        }
        
        card = notifier.build_card(summary)
        
        elements = card['card']['elements']
        text_content = str(elements)
        
        assert 'SuccessVendor' in text_content
        assert 'glb' in text_content


class TestNotifierIntegration:
    """通知集成测试"""
    
    def test_full_summary_flow(self, db, summarizer):
        """测试：完整汇总流程"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        session_mgr.create(
            session_uuid='sess_flow_001',
            channel_type='feishu',
            channel_user_id='ou_123'
        )
        
        # 创建多个任务
        for i in range(3):
            task_mgr.create(
                vendor_task_uuid=f'task_flow_{i}',
                session_uuid='sess_flow_001',
                material_uuid='mat_001',
                vendor_id=f'vendor_{i}',
                vendor_name=f'Vendor{i}',
                model_name=f'model-{i}'
            )
        
        # 更新状态
        task_mgr.update_status('task_flow_0', 'succeeded')
        task_mgr.update_status('task_flow_1', 'succeeded')
        task_mgr.update_status('task_flow_2', 'failed')
        
        # 汇总
        summary = summarizer.summarize('sess_flow_001')
        
        assert summary['summary']['total_vendors'] == 3
        assert summarizer.check_all_done('sess_flow_001') is True
