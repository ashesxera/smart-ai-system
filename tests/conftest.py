"""
AI-3D 建模系统 - pytest 配置

提供测试夹具（fixtures）
"""

import os
import sys
import pytest
import tempfile
import json
from pathlib import Path

# 添加 src 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


@pytest.fixture
def temp_db():
    """创建临时数据库"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # 清理
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def mock_vendor_config():
    """Mock 供应商配置"""
    return {
        "name": "测试供应商",
        "model": "test-model",
        "adapter": "ark_generic",
        "endpoint": "https://api.test.com/submit",
        "query_endpoint": "https://api.test.com/query/${vendor_task_id}",
        "method": "POST",
        "auth_type": "bearer",
        "timeout_minutes": 30,
        "priority": 10,
        "is_active": True,
        "supported_formats": ["glb", "obj"],
        "max_images": 2,
        "max_image_size_mb": 10,
        "request_template": {
            "model": "${model}",
            "content": ${content}
        },
        "content_template": [
            {"type": "image_url", "image_url": {"url": "${image_url_0}"}}
        ],
        "response_parser": {
            "task_id": "$.id",
            "status": "$.status",
            "file_url": "$.file_url"
        },
        "status_map": {
            "queued": "queued",
            "running": "running",
            "succeeded": "succeeded",
            "failed": "failed"
        }
    }


@pytest.fixture
def mock_material_single_image():
    """Mock 材料：单张图片"""
    return {
        "image_urls": ["https://example.com/image.jpg"],
        "text_content": ""
    }


@pytest.fixture
def mock_material_multi_image():
    """Mock 材料：多张图片"""
    return {
        "image_urls": [
            "https://example.com/1.jpg",
            "https://example.com/2.jpg"
        ],
        "text_content": ""
    }


@pytest.fixture
def mock_material_text_only():
    """Mock 材料：纯文字"""
    return {
        "image_urls": [],
        "text_content": "a cute cat"
    }


@pytest.fixture
def mock_success_response():
    """Mock 成功响应"""
    return {
        "id": "task_12345",
        "status": "succeeded",
        "file_url": "https://example.com/model.glb"
    }


@pytest.fixture
def mock_running_response():
    """Mock 运行中响应"""
    return {
        "id": "task_12345",
        "status": "running",
        "progress": 50
    }


@pytest.fixture
def mock_failure_response():
    """Mock 失败响应"""
    return {
        "id": "task_12345",
        "status": "failed",
        "error": {"code": "IMAGE_TOO_SMALL", "message": "图片分辨率过低"}
    }
