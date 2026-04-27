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


def _to_pinyin_slug(name: str) -> str:
    """
    将包含中文的字符串转为拼音 slug（ASCII）

    尝试使用 unidecode 库（如已安装），否则将非 ASCII 字符替换为 'x'。
    例: '豆包Seed3D-Mock' -> 'Dou-Bao-Seed3D-Mock'
    """
    try:
        import unidecode
        return unidecode.unidecode(name).replace(' ', '-')
    except ImportError:
        # 降级: 将非 ASCII 字符替换为 x
        result = []
        for c in name:
            if ord(c) > 127:
                result.append('x')
            else:
                result.append(c)
        return ''.join(result).lstrip('-').rstrip('-')


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
        self.public_base = endpoint or os.environ.get(
            'TOS_PUBLIC_URL',
            f'https://{bucket}.tos-cn-beijing.volces.com'
        ).rstrip('/')

        # TOS 凭证（用于生成 presign URL）
        self.access_key = os.environ.get('TOS_ACCESS_KEY', '')
        self.secret_key = os.environ.get('TOS_SECRET_ACCESS_KEY', '')

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
        """
        return os.path.join(self.MOUNT_BASE, remote_path)

    def _validate_path(self, path: str) -> bool:
        """验证路径安全性"""
        if '..' in path:
            return False
        if path.startswith('/'):
            return False
        return True

    def _make_presign_url(self, object_path: str, expire_seconds: int = 86400) -> Optional[str]:
        """
        使用 Volcengine SDK 生成 presign URL

        Returns:
            完整的 presign URL，失败时返回 None
        """
        if not self.access_key or not self.secret_key:
            return None

        try:
            import sys
            sys.path.insert(0, '/usr/local/lib/python3.12/dist-packages')
            from volcengine.auth.SignerV4 import SignerV4
            from volcengine.base.Request import Request

            class Cred:
                ak = self.access_key
                sk = self.secret_key
                service = 'tos'
                region = 'cn-beijing'
                session_token = ''

            req = Request()
            req.method = 'GET'
            req.path = '/' + object_path
            req.headers = {'Host': '4-ark-claw.tos-cn-beijing.volces.com'}
            req.query = {}
            req.body = b''

            SignerV4.sign_url(req, Cred())

            qs = '&'.join(
                f"{k}={v}" for k, v in req.query.items()
            )
            return f"https://4-ark-claw.tos-cn-beijing.volces.com/{object_path}?{qs}"
        except Exception as e:
            print(f"[Storage] Presign failed: {e}")
            return None

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
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        src = self._local_path(remote_path)
        shutil.copy2(src, local_path)
        return local_path

    def generate_share_url(self, remote_path: str,
                          expire_seconds: int = 86400) -> Optional[str]:
        """
        生成公网可下载的 presign URL

        优先使用 Volcengine SDK 生成带签名的临时下载链接，
        如签名失败则降级返回原始公网 URL。

        Args:
            remote_path: TOS 相对路径
            expire_seconds: 过期时间（秒）

        Returns:
            presign URL 或 None
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        presign = self._make_presign_url(remote_path, expire_seconds)
        if presign:
            return presign
        # 降级: 返回原始 URL（可能不可公开访问）
        return f"{self.public_base}/{remote_path}"

    def transliterate_path(self, name: str) -> str:
        """将包含中文的名称转为拼音 slug，用于文件路径"""
        slug = _to_pinyin_slug(name)
        # 清理多余横杠
        while '--' in slug:
            slug = slug.replace('--', '-')
        return slug.strip('-')

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
            vendor_name: 供应商名称（用于生成可读文件名）
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

            # 2. 生成本地文件名（使用拼音 slug）
            file_ext = file_url.split('.')[-1] if '.' in file_url else 'glb'
            if vendor_name and model_name:
                vendor_slug = self.transliterate_path(vendor_name)
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

            # 4. 生成 presign URL
            share_url = self.generate_share_url(tos_path)

            return {
                'tos_path': tos_path,
                'share_url': share_url,
                'local_path': None
            }
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
