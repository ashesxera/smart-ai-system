"""
AI-3D 建模系统 - 存储模块

TOS 文件存储管理（本地 mount 方式）

TOS bucket 直接挂载为本地文件系统，文件操作转化为本地读写，
无需 HTTP API 认证。
"""

import os
import shutil
import tempfile
from typing import Optional

from ai_3d_modeling.utils import build_tos_path, sanitize_path


class StorageManager:
    """TOS 存储管理器（本地 mount 实现）"""

    # TOS bucket 本地挂载路径
    MOUNT_BASE = '/root/.openclaw/workspace/4-ark-claw'

    def __init__(self, bucket: str, base_path: str, endpoint: str = None):
        """
        初始化存储管理器

        Args:
            bucket: TOS 存储桶名称
            base_path: 基础路径前缀
            endpoint: TOS 公网访问地址（可选，用于生成分享链接）
        """
        self.bucket = bucket
        self.base_path = base_path
        # 公网访问地址，末尾不带 /
        self.public_base = endpoint or os.environ.get(
            'TOS_PUBLIC_URL',
            f'https://{bucket}.tos-cn-beijing.volces.com'
        ).rstrip('/')

    def build_tos_path(self, session_uuid: str, sub_path: str) -> str:
        """
        构建完整的 TOS 相对路径（不含桶名）

        Args:
            session_uuid: 会话 UUID
            sub_path: 子路径

        Returns:
            完整的相对路径，例：ai-3d-system/sessions/{uuid}/results/file.glb
        """
        return f"{self.base_path}/sessions/{session_uuid}/{sub_path}"

    def _local_path(self, remote_path: str) -> str:
        """
        将 TOS 相对路径转为本地文件系统路径

        Args:
            remote_path: TOS 相对路径

        Returns:
            本地文件系统完整路径
        """
        # remote_path 如 "ai-3d-system/sessions/xxx/results/file.glb"
        # 本地 mount 点是 /root/.openclaw/workspace/4-ark-claw/
        return os.path.join(self.MOUNT_BASE, remote_path)

    def _validate_path(self, path: str) -> bool:
        """验证路径安全性"""
        if '..' in path:
            return False
        if path.startswith('/'):
            return False
        return True

    def upload(self, local_path: str, remote_path: str) -> Optional[str]:
        """
        上传本地文件到 TOS（通过本地 mount 写入）

        Args:
            local_path: 本地文件路径
            remote_path: TOS 相对路径

        Returns:
            TOS 文件路径（成功时），None（失败时）
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        dest = self._local_path(remote_path)
        dest_dir = os.path.dirname(dest)

        try:
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(local_path, dest)
            return remote_path
        except Exception as e:
            print(f"[Storage] upload failed: {e}")
            return None

    def download(self, remote_path: str, local_path: str) -> str:
        """
        从 TOS 下载文件到本地（通过本地 mount 读取）

        Args:
            remote_path: TOS 相对路径
            local_path: 本地保存路径

        Returns:
            本地文件路径
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        src = self._local_path(remote_path)
        shutil.copy2(src, local_path)
        return local_path

    def generate_share_url(self, remote_path: str,
                          expire_seconds: int = 86400) -> Optional[str]:
        """
        生成公网分享链接

        Args:
            remote_path: TOS 相对路径
            expire_seconds: 过期时间（秒）

        Returns:
            公网 URL
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        # 公网 URL: endpoint + 相对路径
        return f"{self.public_base}/{remote_path}"

    async def upload_result(self, vendor_task_uuid: str, file_url: str,
                           session_uuid: str,
                           vendor_name: str = None,
                           model_name: str = None) -> dict:
        """
        下载供应商结果并上传到 TOS

        Args:
            vendor_task_uuid: 供应商任务 UUID
            file_url: 供应商提供的文件 URL
            session_uuid: 会话 UUID
            vendor_name: 供应商名称
            model_name: 模型名称

        Returns:
            包含 tos_path 和 share_url 的字典
        """
        import re
        import urllib.request

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name

            # 1. 下载文件
            urllib.request.urlretrieve(file_url, tmp_path)

            # 2. 生成本地文件名
            file_ext = file_url.split('.')[-1] if '.' in file_url else 'glb'
            if vendor_name and model_name:
                words = re.findall(r'[a-zA-Z0-9]+', vendor_name)
                vendor_slug = words[-1] if words else 'unknown'
                model_slug = '-'.join(
                    p for p in model_name.split('-')
                    if not (p.isdigit() and len(p) == 6)
                )
                result_filename = f"{vendor_slug}-{model_slug}.{file_ext}"
            else:
                result_filename = f"{vendor_task_uuid}.{file_ext}"

            tos_sub_path = f"results/{result_filename}"
            tos_path = self.build_tos_path(session_uuid, tos_sub_path)

            # 3. 上传到 TOS
            self.upload(tmp_path, tos_path)

            # 4. 生成分享链接
            share_url = self.generate_share_url(tos_path)

            return {
                'tos_path': tos_path,
                'share_url': share_url,
                'local_path': None
            }
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
