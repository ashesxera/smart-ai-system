"""
AI-3D 建模系统 - Skill 模块单元测试
"""

import pytest
import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ai_3d_modeling.db import Database, SessionManager, MaterialManager, VendorTaskManager
from ai_3d_modeling.skill import SkillHandler, MODELING_KEYWORDS, CANCEL_KEYWORDS


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
def skill_handler(db):
    """创建 SkillHandler"""
    from ai_3d_modeling.notifier import FeishuNotifier
    notifier = FeishuNotifier(gateway_url='http://127.0.0.1:18789/webhook/notify')
    return SkillHandler(db, notifier)


class TestIntentParsing:
    """意图解析测试"""
    
    def test_parse_3d_modeling_intent(self, skill_handler):
        """TC-SKILL-INTENT-001: 识别3D建模请求"""
        intent = skill_handler._parse_intent("帮我生成一个3D模型")
        assert intent == '3d_modeling'
    
    def test_parse_3d_modeling_intent_english(self, skill_handler):
        """TC-SKILL-INTENT-001: 识别英文3D建模"""
        intent = skill_handler._parse_intent("generate a 3D model")
        assert intent == '3d_modeling'
    
    def test_parse_cancel_intent(self, skill_handler):
        """TC-SKILL-INTENT-002: 识别取消意图"""
        intent = skill_handler._parse_intent("取消刚才的请求")
        assert intent == 'cancel'
    
    def test_parse_cancel_intent_english(self, skill_handler):
        """TC-SKILL-INTENT-002: 识别英文取消"""
        intent = skill_handler._parse_intent("cancel the request")
        assert intent == 'cancel'
    
    def test_parse_non_3d_intent(self, skill_handler):
        """TC-SKILL-INTENT-003: 非3D请求"""
        intent = skill_handler._parse_intent("今天天气怎么样")
        assert intent == 'other'
    
    def test_parse_status_intent(self, skill_handler):
        """测试：识别状态查询"""
        intent = skill_handler._parse_intent("任务状态怎么样")
        assert intent == 'status'
    
    def test_parse_help_intent(self, skill_handler):
        """测试：识别帮助"""
        intent = skill_handler._parse_intent("怎么用")
        assert intent == 'help'


class TestMaterialExtraction:
    """材料提取测试"""
    
    def test_extract_text_only(self, skill_handler):
        """TC-SKILL-EXTRACT-002: 提取文字描述"""
        event = {
            'event': {
                'message': {
                    'content': '{"text":"生成一个卡通人物"}'
                }
            }
        }
        
        _, text = skill_handler._extract_intent_and_text(event)
        assert text == '生成一个卡通人物'
    
    def test_extract_empty_text(self, skill_handler):
        """测试：空文本"""
        event = {
            'event': {
                'message': {
                    'content': '{"text":""}'
                }
            }
        }
        
        _, text = skill_handler._extract_intent_and_text(event)
        assert text == ''


class TestSessionCreation:
    """会话创建测试"""
    
    @pytest.mark.asyncio
    async def test_create_session(self, db, skill_handler):
        """TC-SKILL-CREATE-001: 创建会话"""
        event = {
            'event': {
                'sender': {
                    'sender_id': {
                        'open_id': 'ou_test_123'
                    }
                },
                'recipient': {
                    'chat_id': 'oc_test_456'
                },
                'message': {
                    'message_id': 'om_test_789',
                    'content': '{"text":"生成3D模型"}'
                }
            }
        }
        
        # 插入供应商配置
        db.execute('''
            INSERT INTO settings (key, value, value_type, category)
            VALUES ('vendor_seed3d', '{"id":"vendor_seed3d","name":"Seed3D","model":"seed3d","is_active":true,"max_images":1,"endpoint":"https://api.test.com"}', 'json', 'vendor')
        ''')
        
        result = await skill_handler._handle_3d_modeling(event, "生成3D模型")
        
        assert result['code'] == 0
        assert 'session_uuid' in result['data']
        assert result['data']['phase'] == 'processing'


class TestMaterialRecordCreation:
    """材料记录创建测试"""
    
    def test_create_material_record(self, db):
        """TC-SKILL-CREATE-002: 创建材料记录"""
        session_mgr = SessionManager(db)
        material_mgr = MaterialManager(db)
        
        # 创建会话
        session_mgr.create(
            session_uuid='sess_mat_test',
            channel_type='feishu',
            channel_user_id='ou_test'
        )
        
        # 创建材料
        material = material_mgr.create(
            material_uuid='mat_test_001',
            session_uuid='sess_mat_test',
            material_type='image',
            source_type='feishu',
            text_content='test',
            image_urls=['https://example.com/1.jpg']
        )
        
        assert material['material_uuid'] == 'mat_test_001'


class TestVendorTaskCreation:
    """供应商任务创建测试"""
    
    def test_create_vendor_tasks_batch(self, db):
        """TC-SKILL-CREATE-003: 批量创建供应商任务"""
        session_mgr = SessionManager(db)
        task_mgr = VendorTaskManager(db)
        
        # 创建会话
        session_mgr.create(
            session_uuid='sess_task_batch',
            channel_type='feishu',
            channel_user_id='ou_test'
        )
        
        # 插入两个供应商配置
        db.execute('''
            INSERT INTO settings (key, value, value_type, category)
            VALUES ('vendor_1', '{"id":"vendor_1","name":"Vendor1","model":"model1","is_active": true,"max_images":1,"endpoint":"https://api1.com"}', 'json', 'vendor')
        ''')
        db.execute('''
            INSERT INTO settings (key, value, value_type, category)
            VALUES ('vendor_2', '{"id":"vendor_2","name":"Vendor2","model":"model2","is_active": true,"max_images":1,"endpoint":"https://api2.com"}', 'json', 'vendor')
        ''')
        
        # 获取活跃供应商
        handler = SkillHandler.__new__(SkillHandler)
        handler.db = db
        vendors = handler._get_active_vendors()
        
        assert len(vendors) == 2
    
    def test_skip_inactive_vendors(self, db):
        """TC-SKILL-CREATE-004: 跳过不活跃供应商"""
        # 插入一个活跃和一个不活跃的供应商
        db.execute('''
            INSERT INTO settings (key, value, value_type, category)
            VALUES ('vendor_active', '{"id":"vendor_active","name":"Active","is_active": true}', 'json', 'vendor')
        ''')
        db.execute('''
            INSERT INTO settings (key, value, value_type, category)
            VALUES ('vendor_inactive', '{"id":"vendor_inactive","name":"Inactive","is_active": false}', 'json', 'vendor')
        ''')
        
        handler = SkillHandler.__new__(SkillHandler)
        handler.db = db
        vendors = handler._get_active_vendors()
        
        assert len(vendors) == 1
        assert vendors[0]['id'] == 'vendor_active'


class TestHelpAndStatus:
    """帮助和状态处理测试"""
    
    def test_help_response(self, skill_handler):
        """TC-SKILL-RESP-001: 返回帮助信息"""
        event = {}
        result = skill_handler._handle_help(event)
        
        assert result['code'] == 0
        assert '帮助' in result['data']['message']
    
    def test_cancel_no_active_session(self, skill_handler):
        """TC-SKILL-RESP-002: 无活跃会话时取消"""
        event = {
            'event': {
                'sender': {
                    'sender_id': {
                        'open_id': 'ou_no_session'
                    }
                }
            }
        }
        
        import asyncio
        result = asyncio.run(skill_handler._handle_cancel(event))
        
        assert result['code'] == 0
        assert '没有找到' in result['data']['message']
    
    def test_status_no_active_session(self, skill_handler):
        """测试：无活跃会话时查询状态"""
        event = {
            'event': {
                'sender': {
                    'sender_id': {
                        'open_id': 'ou_no_session'
                    }
                }
            }
        }
        
        import asyncio
        result = asyncio.run(skill_handler._handle_status(event))
        
        assert result['code'] == 0
        assert '没有找到' in result['data']['message']


class TestCancelAndStatus:
    """取消和状态测试"""
    
    def test_cancel_with_active_session(self, db, skill_handler):
        """测试：取消有活跃会话"""
        session_mgr = SessionManager(db)
        
        # 创建一个活跃会话
        session_mgr.create(
            session_uuid='sess_cancel',
            channel_type='feishu',
            channel_user_id='ou_cancel_user'
        )
        
        event = {
            'event': {
                'sender': {
                    'sender_id': {
                        'open_id': 'ou_cancel_user'
                    }
                }
            }
        }
        
        import asyncio
        result = asyncio.run(skill_handler._handle_cancel(event))
        
        assert result['code'] == 0
        assert '已取消' in result['data']['message']
        
        # 验证会话状态
        session = session_mgr.get('sess_cancel')
        assert session['status'] == 'cancelled'
