"""
AI-3D 建模系统 - 适配器模块

模板驱动的 API 适配器，负责构建请求、解析响应
"""

import json
import re
from typing import Any, Dict, List, Optional


class TemplateRequestBuilder:
    """请求构建器 - 根据供应商配置和材料构建API请求体"""
    
    def build(self, vendor_config: Dict, material: Dict) -> Dict:
        """
        根据供应商配置和材料构建API请求体
        
        Args:
            vendor_config: 供应商配置字典
            material: 材料字典，包含 image_urls, text_content
        
        Returns:
            构建好的请求体字典
        """
        # 1. 构建 content 数组
        content = self._build_content(vendor_config, material)
        
        # 2. 准备变量
        variables = {
            'model': vendor_config.get('model', ''),
            'content': json.dumps(content),
            'text_content': material.get('text_content', ''),
            **{f'image_url_{i}': url 
               for i, url in enumerate(material.get('image_urls', []))},
        }
        
        # 3. 递归替换模板中的变量
        request_template = vendor_config.get('request_template', {})
        return self._substitute(request_template, variables)
    
    def _build_content(self, vendor_config: Dict, material: Dict) -> List[Dict]:
        """构建 content 数组"""
        content_template = vendor_config.get('content_template', [])
        content = []
        
        for item in content_template:
            if item.get('type') == 'image_url':
                for url in material.get('image_urls', []):
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": url}
                    })
            elif item.get('type') == 'text':
                if material.get('text_content'):
                    content.append({
                        "type": "text",
                        "text": material['text_content']
                    })
        
        return content
    
    def _substitute(self, obj: Any, variables: Dict) -> Any:
        """递归替换模板中的变量"""
        if isinstance(obj, str):
            for key, value in variables.items():
                # 支持 ${key} 和 ${key:N} 格式
                pattern = rf'\${{\s*{key}\s*}}'
                obj = re.sub(pattern, str(value), obj)
            return obj
        elif isinstance(obj, dict):
            return {k: self._substitute(v, variables) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute(item, variables) for item in obj]
        return obj


class TemplateResponseParser:
    """响应解析器 - 解析供应商API响应"""
    
    def parse(self, vendor_config: Dict, response: Dict) -> Dict:
        """
        解析供应商API响应
        
        Args:
            vendor_config: 供应商配置字典
            response: API响应字典
        
        Returns:
            解析后的字典，包含 task_id, status, file_url
        """
        parser_config = vendor_config.get('response_parser', {})
        
        result = {}
        for field, path in parser_config.items():
            result[field] = self._extract(response, path)
        
        # 映射状态
        raw_status = result.get('status')
        status_map = vendor_config.get('status_map', {})
        result['status'] = status_map.get(raw_status, raw_status)
        
        return result
    
    def _extract(self, data: Dict, path: str) -> Any:
        """
        从字典中提取指定路径的值
        
        Args:
            data: 数据字典
            path: JSONPath 风格的路径，如 "$.id" 或 "$.content.file_url"
        
        Returns:
            提取的值，如果路径不存在返回 None
        """
        if path.startswith('$.'):
            keys = path[2:].split('.')
            try:
                for key in keys:
                    data = data[key]
                return data
            except (KeyError, TypeError):
                return None
        return data.get(path)


class BaseAdapter:
    """适配器基类"""
    
    def __init__(self, vendor_config: Dict, api_key: str = None):
        self.config = vendor_config
        self.request_builder = TemplateRequestBuilder()
        self.response_parser = TemplateResponseParser()
        self._api_key = api_key
    
    def build_request(self, material: Dict) -> Dict:
        """构建API请求体"""
        return self.request_builder.build(self.config, material)
    
    def parse_response(self, response: Dict) -> Dict:
        """解析API响应"""
        return self.response_parser.parse(self.config, response)
    
    def get_auth_headers(self) -> Dict:
        """获取认证头"""
        auth_type = self.config.get('auth_type', 'bearer')
        if auth_type == 'bearer':
            api_key = self._get_api_key()
            return {'Authorization': f"Bearer {api_key}"}
        elif auth_type == 'api_key':
            api_key = self._get_api_key()
            header_name = self.config.get('auth_header', 'X-API-Key')
            return {header_name: api_key}
        return {}
    
    def _get_api_key(self) -> str:
        """获取API密钥"""
        if self._api_key:
            return self._api_key
        import os
        return os.environ.get('ARK_API_KEY', '')
    
    def get_endpoint(self) -> str:
        """获取提交任务的API端点"""
        return self.config.get('endpoint', '')
    
    def get_query_endpoint(self, vendor_task_id: str = '') -> str:
        """获取查询任务状态的API端点"""
        endpoint = self.config.get('query_endpoint', self.get_endpoint())
        return endpoint.replace('${vendor_task_id}', vendor_task_id)
    
    def get_timeout(self) -> int:
        """获取超时时间（分钟）"""
        return self.config.get('timeout_minutes', 30)
    
    async def submit(self, request_body: Dict) -> Dict:
        """
        提交任务到供应商API
        
        Args:
            request_body: 请求体字典
        
        Returns:
            API 响应字典
        """
        import httpx
        
        headers = self.get_auth_headers()
        headers['Content-Type'] = 'application/json'
        
        timeout = self.get_timeout()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.get_endpoint(),
                json=request_body,
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
    
    async def query_status(self, vendor_task_id: str) -> Dict:
        """
        查询任务状态
        
        Args:
            vendor_task_id: 供应商任务ID
        
        Returns:
            状态响应字典
        """
        import httpx
        
        headers = self.get_auth_headers()
        
        query_endpoint = self.get_query_endpoint(vendor_task_id)
        timeout = self.get_timeout()
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                query_endpoint,
                headers=headers,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()


class AdapterFactory:
    """适配器工厂"""
    
    _adapters: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, adapter_class: type):
        """注册适配器"""
        cls._adapters[name] = adapter_class
    
    @classmethod
    def create(cls, vendor_config: Dict, api_key: str = None) -> BaseAdapter:
        """
        创建适配器实例
        
        Args:
            vendor_config: 供应商配置字典
            api_key: API密钥（可选）
        
        Returns:
            适配器实例
        """
        adapter_name = vendor_config.get('adapter', 'generic')
        adapter_class = cls._adapters.get(adapter_name, BaseAdapter)
        
        # 创建实例并注入API密钥
        instance = adapter_class(vendor_config, api_key)
        
        return instance
    
    @classmethod
    def get_registered_adapters(cls) -> List[str]:
        """获取已注册的适配器名称列表"""
        return list(cls._adapters.keys())


# 注册默认适配器
AdapterFactory.register('ark_generic', BaseAdapter)
AdapterFactory.register('generic', BaseAdapter)
