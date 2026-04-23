"""
AI-3D 建模系统 - 工具模块单元测试
"""

import pytest
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from ai_3d_modeling.utils import (
    generate_uuid,
    get_timestamp,
    get_timestamp_ms,
    format_timestamp,
    format_duration,
    parse_content_type,
    sanitize_path,
    truncate_string,
    build_tos_path,
    extract_filename_from_url
)


class TestGenerateUuid:
    """UUID 生成测试"""
    
    def test_generate_uuid_no_prefix(self):
        """TC-UTIL-001: 生成UUID（无前缀）"""
        uid = generate_uuid()
        
        assert len(uid) == 36  # xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        assert '-' in uid
    
    def test_generate_uuid_with_prefix(self):
        """TC-UTIL-001: 生成UUID（带前缀）"""
        uid = generate_uuid('sess')
        
        assert uid.startswith('sess_')
        assert len(uid) == 40  # sess_ + 36 chars
    
    def test_generate_uuid_uniqueness(self):
        """测试：UUID 唯一性"""
        uids = [generate_uuid() for _ in range(100)]
        
        assert len(set(uids)) == 100


class TestTimestamp:
    """时间戳测试"""
    
    def test_get_timestamp(self):
        """TC-UTIL-002: 获取Unix时间戳（秒）"""
        ts = get_timestamp()
        
        assert isinstance(ts, int)
        assert ts > 0
    
    def test_get_timestamp_ms(self):
        """TC-UTIL-002: 获取Unix时间戳（毫秒）"""
        ts_ms = get_timestamp_ms()
        
        assert isinstance(ts_ms, int)
        assert ts_ms > get_timestamp() * 1000
    
    def test_format_timestamp(self):
        """测试：格式化时间戳"""
        ts = 1704067200  # 2024-01-01 00:00:00 UTC
        
        formatted = format_timestamp(ts)
        
        assert '2024' in formatted
        assert '01' in formatted
        assert '01' in formatted


class TestFormatDuration:
    """时长格式化测试"""
    
    def test_seconds_only(self):
        """TC-UTIL-003: 仅秒"""
        assert format_duration(30) == "30秒"
        assert format_duration(59) == "59秒"
    
    def test_minutes_and_seconds(self):
        """TC-UTIL-003: 分和秒"""
        assert format_duration(65) == "1分5秒"
        assert format_duration(120) == "2分"
        assert format_duration(125) == "2分5秒"
    
    def test_hours_minutes(self):
        """TC-UTIL-003: 小时和分"""
        assert format_duration(3660) == "1小时1分"
        assert format_duration(7200) == "2小时"
    
    def test_large_duration(self):
        """测试：长时间"""
        assert format_duration(36000) == "10小时"


class TestParseContentType:
    """内容类型解析测试"""
    
    def test_parse_glb(self):
        """TC-UTIL-004: 解析 GLB 文件"""
        url = "https://example.com/model.glb"
        assert parse_content_type(url) == 'glb'
    
    def test_parse_obj(self):
        """TC-UTIL-004: 解析 OBJ 文件"""
        url = "https://example.com/model.obj"
        assert parse_content_type(url) == 'obj'
    
    def test_parse_with_query_params(self):
        """TC-UTIL-004: 解析带参数的URL"""
        url = "https://example.com/model.glb?token=abc"
        assert parse_content_type(url) == 'glb'
    
    def test_parse_jpg(self):
        """TC-UTIL-004: 解析 JPG 图片"""
        url = "https://example.com/photo.jpg"
        assert parse_content_type(url) == 'jpg'
    
    def test_parse_png(self):
        """TC-UTIL-004: 解析 PNG 图片"""
        url = "https://example.com/photo.png"
        assert parse_content_type(url) == 'png'
    
    def test_parse_unknown(self):
        """测试：未知类型"""
        url = "https://example.com/file"
        result = parse_content_type(url)
        assert result is None or result == ''


class TestSanitizePath:
    """路径清理测试"""
    
    def test_normal_path(self):
        """TC-STORAGE-003: 正常路径"""
        path = "sessions/uuid/materials/file.jpg"
        assert sanitize_path(path) == path
    
    def test_path_traversal_blocked(self):
        """TC-STORAGE-003: 路径遍历攻击防护"""
        dangerous = "../../../etc/passwd"
        result = sanitize_path(dangerous)
        
        assert '..' not in result
        assert 'etc' not in result
    
    def test_double_slash(self):
        """测试：双斜杠处理"""
        path = "sessions//uuid//file.jpg"
        result = sanitize_path(path)
        
        assert '//' not in result
    
    def test_leading_slash(self):
        """测试：移除开头斜杠"""
        path = "/etc/passwd"
        result = sanitize_path(path)
        
        assert not result.startswith('/')


class TestTruncateString:
    """字符串截断测试"""
    
    def test_no_truncate(self):
        """测试：不需要截断"""
        text = "short"
        assert truncate_string(text, max_length=10) == "short"
    
    def test_truncate_with_suffix(self):
        """测试：截断并添加后缀"""
        text = "this is a very long text"
        result = truncate_string(text, max_length=10)
        
        assert len(result) <= 13  # 10 + 3 for '...'
        assert result.endswith('...')
    
    def test_truncate_no_suffix(self):
        """测试：截断无后缀"""
        text = "this is a very long text"
        result = truncate_string(text, max_length=10, suffix='')
        
        assert len(result) == 10


class TestBuildTosPath:
    """TOS 路径构建测试"""
    
    def test_build_basic_path(self):
        """TC-STORAGE-001: 构建基础路径"""
        result = build_tos_path('sess_123', 'materials/file.jpg')
        
        assert result == 'ai-3d-system/sessions/sess_123/materials/file.jpg'
    
    def test_build_path_without_subpath(self):
        """测试：无子路径"""
        result = build_tos_path('sess_123', '')
        
        assert result == 'ai-3d-system/sessions/sess_123'
    
    def test_build_result_path(self):
        """测试：构建结果路径"""
        result = build_tos_path('sess_123', 'results/model.glb')
        
        assert 'results' in result
        assert 'model.glb' in result


class TestExtractFilenameFromUrl:
    """URL 文件名提取测试"""
    
    def test_extract_basic_filename(self):
        """测试：提取基本文件名"""
        url = "https://example.com/path/to/file.jpg"
        
        assert extract_filename_from_url(url) == "file.jpg"
    
    def test_extract_with_query(self):
        """测试：提取带查询参数"""
        url = "https://example.com/file.jpg?token=abc"
        
        assert extract_filename_from_url(url) == "file.jpg"
    
    def test_extract_no_path(self):
        """测试：无路径情况"""
        url = "https://example.com"
        
        result = extract_filename_from_url(url)
        assert result == "unknown"


# 边界条件测试
class TestEdgeCases:
    """边界条件测试"""
    
    def test_empty_prefix(self):
        """TC-EDGE: 空前缀"""
        uid = generate_uuid('')
        assert '-' in uid
    
    def test_special_chars_in_path(self):
        """TC-EDGE: 路径特殊字符"""
        path = "sessions/uuid/file with spaces.jpg"
        result = sanitize_path(path)
        
        assert 'file with spaces.jpg' in result
    
    def test_zero_duration(self):
        """TC-EDGE: 零时长"""
        assert format_duration(0) == "0秒"
    
    def test_empty_url(self):
        """TC-EDGE: 空URL"""
        assert parse_content_type('') is None
