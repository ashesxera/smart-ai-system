"""
AI-3D 建模系统 - 工具模块

通用工具函数
"""

import hashlib
import os
import re
import time
import uuid
from datetime import datetime
from typing import Optional


def generate_uuid(prefix: str = '') -> str:
    """
    生成UUID
    
    Args:
        prefix: UUID前缀，如 'sess', 'mat', 'task'
    
    Returns:
        格式为 'prefix-xxxxxxxxxxxx' 的UUID字符串
    """
    uid = str(uuid.uuid4())
    if prefix:
        return f"{prefix}_{uid}"
    return uid


def get_timestamp() -> int:
    """获取当前Unix时间戳（秒）"""
    return int(time.time())


def get_timestamp_ms() -> int:
    """获取当前Unix时间戳（毫秒）"""
    return int(time.time() * 1000)


def format_timestamp(ts: int) -> str:
    """
    格式化时间戳为可读字符串
    
    Args:
        ts: Unix时间戳（秒）
    
    Returns:
        格式: '2026-04-23 12:00:00'
    """
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')


def format_duration(seconds: int) -> str:
    """
    格式化时长为可读字符串
    
    Args:
        seconds: 秒数
    
    Returns:
        如 '2分5秒' 或 '1小时3分'
    """
    if seconds < 60:
        return f"{seconds}秒"
    
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    
    if minutes < 60:
        if remaining_seconds:
            return f"{minutes}分{remaining_seconds}秒"
        return f"{minutes}分"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes:
        return f"{hours}小时{remaining_minutes}分"
    return f"{hours}小时"


def parse_content_type(url: str) -> Optional[str]:
    """
    从URL解析文件扩展名/内容类型
    
    Args:
        url: 文件URL
    
    Returns:
        文件扩展名，如 'glb', 'obj', 'jpg'
    """
    # 尝试从URL路径中提取扩展名
    match = re.search(r'/([^/]+)\.([a-zA-Z0-9]+)(?:\?|$)', url)
    if match:
        return match.group(2).lower()
    
    # 尝试从Content-Disposition头或最后一段路径
    match = re.search(r'\.([a-zA-Z0-9]+)(?:\?|$)', url)
    if match:
        return match.group(1).lower()
    
    return None


def sanitize_path(path: str) -> str:
    """
    清理路径，防止路径遍历攻击
    
    Args:
        path: 用户提供的路径
    
    Returns:
        清理后的安全路径
    """
    # 移除危险字符
    path = path.replace('..', '')
    path = path.replace('//', '/')
    
    # 移除开头的 /
    path = path.lstrip('/')
    
    return path


def compute_file_hash(file_path: str, algorithm: str = 'md5') -> str:
    """
    计算文件哈希值
    
    Args:
        file_path: 文件路径
        algorithm: 哈希算法 ('md5', 'sha256')
    
    Returns:
        十六进制哈希字符串
    """
    if algorithm == 'md5':
        hasher = hashlib.md5()
    elif algorithm == 'sha256':
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    
    return hasher.hexdigest()


def truncate_string(s: str, max_length: int = 100, suffix: str = '...') -> str:
    """
    截断字符串
    
    Args:
        s: 输入字符串
        max_length: 最大长度
        suffix: 截断后缀
    
    Returns:
        截断后的字符串
    """
    if len(s) <= max_length:
        return s
    return s[:max_length - len(suffix)] + suffix


def build_tos_path(session_uuid: str, sub_path: str) -> str:
    """
    构建TOS存储路径
    
    Args:
        session_uuid: 会话UUID
        sub_path: 子路径，如 'materials/file.jpg'
    
    Returns:
        完整的TOS路径
    """
    base = f"ai-3d-system/sessions/{session_uuid}"
    if sub_path:
        return f"{base}/{sub_path}"
    return base


def extract_filename_from_url(url: str) -> str:
    """
    从URL中提取文件名
    
    Args:
        url: 文件URL
    
    Returns:
        文件名
    """
    match = re.search(r'/([^/]+)(?:\?|$)', url)
    if match:
        return match.group(1)
    return 'unknown'


def parse_vendor_config(config_str: str) -> dict:
    """
    解析供应商配置JSON字符串
    
    Args:
        config_str: JSON格式的配置字符串
    
    Returns:
        配置字典
    """
    import json
    try:
        return json.loads(config_str)
    except json.JSONDecodeError:
        return {}
