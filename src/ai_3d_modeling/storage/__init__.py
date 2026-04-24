"""
AI-3D 建模系统 - 存储模块

TOS 文件存储管理
"""

import os
import subprocess
from typing import Optional
from ai_3d_modeling.utils import build_tos_path, sanitize_path


class StorageManager:
    """TOS 存储管理器"""

    def __init__(self, bucket: str, base_path: str):
        """
        初始化存储管理器

        Args:
            bucket: TOS 存储桶名称
            base_path: 基础路径前缀
        """
        self.bucket = bucket
        self.base_path = base_path

    def build_tos_path(self, session_uuid: str, sub_path: str) -> str:
        """
        构建完整的 TOS 路径

        Args:
            session_uuid: 会话 UUID
            sub_path: 子路径

        Returns:
            完整的 TOS 路径
        """
        return f"{self.base_path}/sessions/{session_uuid}/{sub_path}"

    def _validate_path(self, path: str) -> bool:
        """
        验证路径安全性

        Args:
            path: 路径

        Returns:
            是否安全
        """
        # 清理路径
        cleaned = sanitize_path(path)

        # 检查是否包含危险字符
        if '..' in path:
            return False

        # 检查是否绝对路径
        if path.startswith('/'):
            return False

        return True

    def upload(self, local_path: str, remote_path: str) -> str:
        """
        上传文件到 TOS

        Args:
            local_path: 本地文件路径
            remote_path: TOS 远程路径

        Returns:
            TOS 文件路径
        """
        # 验证路径
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        # 构建 tosutil 命令
        tos_path = f"tos://{self.bucket}/{remote_path}"
        cmd = ['tosutil', 'cp', local_path, tos_path]

        # 执行上传
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"TOS upload failed: {result.stderr}")

        return remote_path

    def download(self, remote_path: str, local_path: str) -> str:
        """
        从 TOS 下载文件

        Args:
            remote_path: TOS 远程路径
            local_path: 本地保存路径

        Returns:
            本地文件路径
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        tos_path = f"tos://{self.bucket}/{remote_path}"
        cmd = ['tosutil', 'cp', tos_path, local_path]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"TOS download failed: {result.stderr}")

        return local_path

    def _format_expire(self, seconds: int) -> str:
        """将秒数转换为 tosutil presign 接受的时间格式"""
        if seconds >= 86400 and seconds % 86400 == 0:
            return f"{seconds // 86400}d"
        elif seconds >= 3600 and seconds % 3600 == 0:
            return f"{seconds // 3600}h"
        elif seconds >= 60 and seconds % 60 == 0:
            return f"{seconds // 60}m"
        else:
            return f"{seconds}s"

    def generate_share_url(self, remote_path: str,
                          expire_seconds: int = 86400) -> str:
        """
        生成带过期时间的下载链接

        Args:
            remote_path: TOS 文件路径
            expire_seconds: 过期时间(秒)

        Returns:
            下载 URL
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        tos_path = f"tos://{self.bucket}/{remote_path}"
        expire_str = self._format_expire(expire_seconds)
        cmd = ['tosutil', 'presign', tos_path, '-vp=' + expire_str]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"TOS presign failed: {result.stderr}")

        return result.stdout.strip()

    async def upload_result(self, vendor_task_uuid: str, file_url: str,
                           session_uuid: str,
                           vendor_name: str = None,
                           model_name: str = None) -> dict:
        """
        下载供应商结果并上传到 TOS

        Args:
            vendor_task_uuid: 供应商任务 UUID（用于调试）
            file_url: 供应商提供的文件 URL
            session_uuid: 会话 UUID
            vendor_name: 供应商名称（用于生成可读文件名）
            model_name: 模型名称（用于生成可读文件名）

        Returns:
            包含 tos_path 和 share_url 的字典
        """
        import tempfile
        import urllib.request

        # 1. 下载文件
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            urllib.request.urlretrieve(file_url, tmp_path)
        except Exception as e:
            os.unlink(tmp_path)
            raise RuntimeError(f"Download failed: {e}")

        # 2. 上传到 TOS
        file_ext = file_url.split('.')[-1] if '.' in file_url else 'glb'
        # 生成可读文件名：vendor-model.ext
        # 格式如 Seed3D-doubao-seed3d-2-0.glb
        if vendor_name and model_name:
            import re
            words = re.findall(r'[a-zA-Z0-9]+', vendor_name)
            vendor_slug = words[-1] if words else 'unknown'
            # 去掉 model 名中的日期后缀（如 260328）
            model_slug = '-'.join(
                p for p in model_name.split('-')
                if not (p.isdigit() and len(p) == 6)
            )
            result_filename = f"{vendor_slug}-{model_slug}.{file_ext}"
        else:
            result_filename = f"{vendor_task_uuid}.{file_ext}"
        tos_sub_path = f"results/{result_filename}"
        tos_path = self.build_tos_path(session_uuid, tos_sub_path)

        try:
            self.upload(tmp_path, tos_path)
        except Exception as e:
            os.unlink(tmp_path)
            raise RuntimeError(f"TOS upload failed: {e}")

        # 3. 生成下载链接
        try:
            share_url = self.generate_share_url(tos_path)
        except Exception:
            share_url = None

        # 4. 清理临时文件
        os.unlink(tmp_path)

        return {
            'tos_path': tos_path,
            'share_url': share_url,
            'local_path': None
        }
