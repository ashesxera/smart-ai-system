"""
AI-3D 建模系统 - 存储模块

TOS 文件存储管理（ve-tos-python-sdk 实现）

使用 Volcengine 官方 TOS SDK 直接操作对象存储。
文档: https://github.com/volcengine/ve-tos-python-sdk
"""

import io
import os
import shutil
import tempfile
from typing import Optional

import tos
from tos.exceptions import TosServerError
from tos import HttpMethodType

from ai_3d_modeling.utils import build_tos_path


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
        result = []
        for c in name:
            if ord(c) > 127:
                result.append('x')
            else:
                result.append(c)
        return ''.join(result).lstrip('-').rstrip('-')


class StorageManager:
    """
    TOS 存储管理器（ve-tos-python-sdk 实现）

    Args:
        bucket: TOS 存储桶名称，例 arkclaw-tos-2123782374-cn-beijing
        base_path: 基础路径前缀，例 ai-3d-system
        endpoint: TOS 访问端点，默认 tos-cn-beijing.volces.com
        region: TOS 区域，默认 cn-beijing
    """

    def __init__(self, bucket: str, base_path: str,
                 endpoint: str = 'tos-cn-beijing.volces.com',
                 region: str = 'cn-beijing'):
        self.bucket = bucket
        self.base_path = base_path
        self.endpoint = endpoint
        self.region = region

        # 从环境变量读取凭证
        self.access_key = os.environ.get('TOS_ACCESS_KEY', '')
        self.secret_key = os.environ.get('TOS_SECRET_ACCESS_KEY', '')

        # 延迟初始化 client
        self._client = None

    def _get_client(self):
        """获取或创建 TOS client（延迟初始化）"""
        if self._client is None:
            self._client = tos.TosClientV2(
                ak=self.access_key,
                sk=self.secret_key,
                endpoint=self.endpoint,
                region=self.region,
            )
        return self._client

    def _validate_path(self, path: str) -> bool:
        """验证路径安全性"""
        if '..' in path:
            return False
        if path.startswith('/'):
            return False
        return True

    def build_tos_path(self, session_uuid: str, sub_path: str) -> str:
        """
        构建完整的 TOS 相对路径（不含桶名）

        Args:
            session_uuid: 会话 UUID
            sub_path: 子路径，例 results/file.glb

        Returns:
            完整的相对路径，例：ai-3d-system/sessions/{uuid}/results/file.glb
        """
        return f"{self.base_path}/sessions/{session_uuid}/{sub_path}"

    def upload(self, local_path: str, remote_path: str) -> Optional[str]:
        """
        上传本地文件到 TOS（通过 put_object + 本地文件流）

        Args:
            local_path: 本地文件路径
            remote_path: TOS 相对路径

        Returns:
            TOS 文件路径（成功时），None（失败时）
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        try:
            client = self._get_client()
            with open(local_path, 'rb') as f:
                content = f.read()
            client.put_object(bucket=self.bucket, key=remote_path, content=content)
            return remote_path
        except TosServerError as e:
            print(f"[Storage] upload failed: [{e.status_code}] {e.code}")
            return None
        except Exception as e:
            print(f"[Storage] upload failed: {type(e).__name__}: {e}")
            return None

    def download(self, remote_path: str, local_path: str) -> str:
        """
        从 TOS 下载文件到本地（通过 get_object + 写入文件）

        Args:
            remote_path: TOS 相对路径
            local_path: 本地保存路径

        Returns:
            本地保存路径（成功时）
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        client = self._get_client()
        os.makedirs(os.path.dirname(local_path) or '.', exist_ok=True)
        resp = client.get_object(bucket=self.bucket, key=remote_path)
        data = resp.read()
        with open(local_path, 'wb') as f:
            f.write(data)
        return local_path

    def generate_share_url(self, remote_path: str,
                          expire_seconds: int = 86400) -> Optional[str]:
        """
        生成公网可下载的 presign URL（24小时有效期）

        Args:
            remote_path: TOS 相对路径
            expire_seconds: 过期时间（秒），默认 24 小时

        Returns:
            presign URL 或 None
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        try:
            client = self._get_client()
            resp = client.pre_signed_url(
                bucket=self.bucket,
                key=remote_path,
                expires=expire_seconds,
                http_method=HttpMethodType.Http_Method_Get,
            )
            return resp.signed_url
        except Exception as e:
            print(f"[Storage] generate_share_url failed: {e}")
            return None

    def exists(self, remote_path: str) -> bool:
        """检查 TOS 文件是否存在"""
        if not self._validate_path(remote_path):
            return False
        try:
            client = self._get_client()
            client.head_object(bucket=self.bucket, key=remote_path)
            return True
        except TosServerError:
            return False
        except Exception:
            return False

    def delete(self, remote_path: str) -> bool:
        """删除 TOS 文件"""
        if not self._validate_path(remote_path):
            return False
        try:
            client = self._get_client()
            client.delete_object(bucket=self.bucket, key=remote_path)
            return True
        except Exception as e:
            print(f"[Storage] delete failed: {e}")
            return False

    def list_objects(self, prefix: str, max_keys: int = 100) -> list:
        """
        列出 TOS 前缀下的对象

        Args:
            prefix: 对象前缀
            max_keys: 最大返回数量

        Returns:
            对象 Key 列表
        """
        try:
            client = self._get_client()
            resp = client.list_objects(
                bucket=self.bucket,
                prefix=prefix,
                max_keys=max_keys,
            )
            return [obj.key for obj in resp.contents]
        except TosServerError as e:
            print(f"[Storage] list_objects: [{e.status_code}] {e.code}")
            return []
        except Exception as e:
            print(f"[Storage] list_objects failed: {e}")
            return []

    def read_content(self, remote_path: str) -> bytes:
        """
        直接读取 TOS 文件内容（适合小文件）

        Args:
            remote_path: TOS 相对路径

        Returns:
            文件内容 bytes
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")
        client = self._get_client()
        resp = client.get_object(bucket=self.bucket, key=remote_path)
        return resp.read()

    def write_content(self, remote_path: str, content: bytes) -> bool:
        """
        直接写入内容到 TOS（适合小文件）

        Args:
            remote_path: TOS 相对路径
            content: 文件内容 bytes

        Returns:
            True 成功，False 失败
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")
        try:
            client = self._get_client()
            client.put_object(bucket=self.bucket, key=remote_path, content=content)
            return True
        except Exception as e:
            print(f"[Storage] write_content failed: {e}")
            return False

    def transliterate_path(self, name: str) -> str:
        """将包含中文的名称转为拼音 slug，用于文件路径"""
        slug = _to_pinyin_slug(name)
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
            uploaded = self.upload(tmp_path, tos_path)
            if not uploaded:
                raise RuntimeError(f"TOS upload failed for {tos_path}")

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