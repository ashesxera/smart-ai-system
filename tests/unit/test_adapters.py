"""
AI-3D 建模系统 - 适配器模块单元测试
"""

import pytest
import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ai_3d_modeling.adapters import (
    TemplateRequestBuilder,
    TemplateResponseParser,
    BaseAdapter,
    AdapterFactory
)


class TestTemplateRequestBuilder:
    """TemplateRequestBuilder 测试"""
    
    def test_build_simple_image_request(self, mock_vendor_config, mock_material_single_image):
        """TC-ADAPTER-001: 构建简单图片请求"""
        builder = TemplateRequestBuilder()
        
        # 使用正确的配置
        mock_vendor_config['request_template'] = {
            "model": "${model}",
            "content": "${content}"
        }
        
        result = builder.build(mock_vendor_config, mock_material_single_image)
        
        assert result['model'] == 'test-model'
        assert 'content' in result
    
    def test_build_with_empty_material(self):
        """TC-ADAPTER-004: 空材料处理"""
        builder = TemplateRequestBuilder()
        
        config = {
            "model": "test",
            "request_template": {"prompt": "${text_content}"},
            "content_template": []
        }
        
        material = {"image_urls": [], "text_content": ""}
        result = builder.build(config, material)
        
        assert result['prompt'] == ''
    
    def test_variable_substitution(self):
        """测试变量替换"""
        builder = TemplateRequestBuilder()
        
        config = {
            "model": "my-model",
            "request_template": {"model": "${model}", "text": "${text_content}"},
            "content_template": []
        }
        
        material = {"image_urls": [], "text_content": "hello world"}
        result = builder.build(config, material)
        
        assert result['model'] == 'my-model'
        assert result['text'] == 'hello world'
    
    def test_nested_variable_substitution(self):
        """测试嵌套变量替换"""
        builder = TemplateRequestBuilder()
        
        config = {
            "model": "test",
            "request_template": {"data": {"url": "${image_url_0}"}},
            "content_template": []
        }
        
        material = {"image_urls": ["https://example.com/img.jpg"], "text_content": ""}
        result = builder.build(config, material)
        
        assert result['data']['url'] == 'https://example.com/img.jpg'


class TestTemplateResponseParser:
    """TemplateResponseParser 测试"""
    
    def test_parse_success_response(self, mock_vendor_config, mock_success_response):
        """TC-PARSER-001: 解析成功响应"""
        parser = TemplateResponseParser()
        
        result = parser.parse(mock_vendor_config, mock_success_response)
        
        assert result['task_id'] == 'task_12345'
        assert result['status'] == 'succeeded'
        assert result['file_url'] == 'https://example.com/model.glb'
    
    def test_parse_failure_response(self, mock_vendor_config, mock_failure_response):
        """TC-PARSER-002: 解析失败响应"""
        parser = TemplateResponseParser()
        
        result = parser.parse(mock_vendor_config, mock_failure_response)
        
        assert result['task_id'] == 'task_12345'
        assert result['status'] == 'failed'
    
    def test_status_mapping(self, mock_vendor_config):
        """TC-PARSER-003: 状态映射"""
        parser = TemplateResponseParser()
        
        # 自定义状态映射
        mock_vendor_config['status_map'] = {
            "pending": "queued",
            "completed": "succeeded",
            "failed": "failed"
        }
        
        response = {"id": "task_1", "status": "completed", "file_url": None}
        result = parser.parse(mock_vendor_config, response)
        
        assert result['status'] == 'succeeded'
    
    def test_nested_jsonpath_extraction(self):
        """TC-PARSER-004: 嵌套JSONPath提取"""
        parser = TemplateResponseParser()
        
        config = {
            "response_parser": {
                "task_id": "$.id",
                "file_url": "$.content.file_url",
                "nested_value": "$.data.items[0].name"
            },
            "status_map": {}
        }
        
        response = {
            "id": "task_123",
            "content": {"file_url": "https://example.com/file.glb"},
            "data": {"items": [{"name": "item1"}]}
        }
        
        result = parser.parse(config, response)
        
        assert result['task_id'] == 'task_123'
        assert result['file_url'] == 'https://example.com/file.glb'
    
    def test_missing_path_returns_none(self):
        """测试路径不存在时返回 None"""
        parser = TemplateResponseParser()
        
        config = {
            "response_parser": {"missing": "$.nonexistent"},
            "status_map": {}
        }
        
        response = {"id": "task_1"}
        result = parser.parse(config, response)
        
        assert result['missing'] is None


class TestBaseAdapter:
    """BaseAdapter 测试"""
    
    def test_build_request(self, mock_vendor_config, mock_material_single_image):
        """测试构建请求"""
        adapter = BaseAdapter(mock_vendor_config)
        
        request = adapter.build_request(mock_material_single_image)
        
        assert 'model' in request
    
    def test_parse_response(self, mock_vendor_config, mock_success_response):
        """测试解析响应"""
        adapter = BaseAdapter(mock_vendor_config)
        
        result = adapter.parse_response(mock_success_response)
        
        assert result['status'] == 'succeeded'
    
    def test_get_endpoint(self, mock_vendor_config):
        """测试获取端点"""
        adapter = BaseAdapter(mock_vendor_config)
        
        assert adapter.get_endpoint() == 'https://api.test.com/submit'
    
    def test_get_query_endpoint_with_task_id(self, mock_vendor_config):
        """测试获取查询端点（带任务ID）"""
        adapter = BaseAdapter(mock_vendor_config)
        
        endpoint = adapter.get_query_endpoint('task_12345')
        
        assert 'task_12345' in endpoint


class TestAdapterFactory:
    """AdapterFactory 测试"""
    
    def test_create_default_adapter(self):
        """TC-FACTORY-001: 创建默认适配器实例"""
        config = {"adapter": "generic"}
        
        adapter = AdapterFactory.create(config)
        
        assert isinstance(adapter, BaseAdapter)
    
    def test_create_ark_generic_adapter(self):
        """测试创建 ark_generic 适配器"""
        config = {"adapter": "ark_generic"}
        
        adapter = AdapterFactory.create(config)
        
        assert isinstance(adapter, BaseAdapter)
    
    def test_unknown_adapter_fallback(self):
        """TC-FACTORY-003: 未知适配器回退到默认"""
        config = {"adapter": "unknown_adapter"}
        
        adapter = AdapterFactory.create(config)
        
        assert isinstance(adapter, BaseAdapter)
    
    def test_get_registered_adapters(self):
        """TC-FACTORY: 获取已注册适配器列表"""
        adapters = AdapterFactory.get_registered_adapters()
        
        assert 'ark_generic' in adapters
        assert 'generic' in adapters
