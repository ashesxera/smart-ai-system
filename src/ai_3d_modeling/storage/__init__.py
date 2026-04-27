"""
AI-3D 建模系统 - 存储模块

TOS 文件存储管理（使用原生 HTTP API + AWS SigV4 签名）
"""

import os
import json
import hashlib
import datetime
import urllib.parse
import urllib.request
import hmac
import tempfile
from typing import Optional

from ai_3d_modeling.utils import build_tos_path, sanitize_path


def get_tos_credentials() -> tuple:
    """从环境变量获取 TOS 凭证"""
    access_key = os.environ.get('TOS_ACCESS_KEY', '')
    secret_key = os.environ.get('TOS_SECRET_ACCESS_KEY', '')
    return access_key, secret_key


def get_tos_endpoint() -> str:
    """从环境变量获取 TOS endpoint"""
    # 默认使用北京区域
    region = os.environ.get('TOS_REGION', 'cn-beijing')
    return f"https://tos.{region}.volces.com"


class StorageManager:
    """TOS 存储管理器"""

    def __init__(self, bucket: str, base_path: str, endpoint: str = None):
        """
        初始化存储管理器

        Args:
            bucket: TOS 存储桶名称
            base_path: 基础路径前缀
            endpoint: TOS 服务端点（可选，从环境变量读取）
        """
        self.bucket = bucket
        self.base_path = base_path
        self.endpoint = endpoint or get_tos_endpoint()
        self.access_key, self.secret_key = get_tos_credentials()

    def build_tos_path(self, session_uuid: str, sub_path: str) -> str:
        """
        构建完整的 TOS 路径（相对路径，不含桶名）

        Args:
            session_uuid: 会话 UUID
            sub_path: 子路径

        Returns:
            完整的相对路径
        """
        return f"{self.base_path}/sessions/{session_uuid}/{sub_path}"

    def _validate_path(self, path: str) -> bool:
        """验证路径安全性"""
        if '..' in path:
            return False
        if path.startswith('/'):
            return False
        return True

    def _sign(self, method: str, path: str, headers: dict,
              query: dict = None) -> str:
        """
        AWS Signature Version 4 签名（简化版）

        Returns authorization header value
        """
        region = 'cn-beijing'
        service = 'tos'

        now = datetime.datetime.utcnow()
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = now.strftime('%Y%m%d')

        # Task 1: Canonical Request
        canonical_uri = '/' + path.lstrip('/')
        canonical_querystring = ''
        if query:
            canonical_querystring = '&'.join(
                f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
                for k, v in sorted(query.items())
            )

        payload_hash = hashlib.sha256(headers.get('x-amz-content-sha256', '').encode()).hexdigest()
        canonical_headers = '\n'.join(
            f"{k.lower()}:{v}" for k, v in sorted(headers.items())
        ) + '\n'
        signed_headers = ';'.join(k.lower() for k in sorted(headers.keys()))

        canonical_request = '\n'.join([
            method,
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            payload_hash
        ])
        hashed_canonical_request = hashlib.sha256(canonical_request.encode()).hexdigest()

        # Task 2: String to Sign
        algorithm = 'AWS4-HMAC-SHA256'
        credential_scope = f"{date_stamp}/{region}/{service}/aws4_request"
        string_to_sign = '\n'.join([
            algorithm,
            amz_date,
            credential_scope,
            hashed_canonical_request
        ])

        # Task 3: Calculate signature
        k_date = hmac.new(
            f"AWS4{self.secret_key}".encode(),
            date_stamp.encode(), hashlib.sha256
        ).digest()
        k_region = hmac.new(k_date, region.encode(), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service.encode(), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b'aws4_request', hashlib.sha256).digest()
        signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

        # Task 4: Assemble authorization header
        authorization = (
            f"{algorithm} "
            f"Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )
        return authorization

    def _make_request(self, method: str, path: str, data: bytes = None,
                      query: dict = None, headers: dict = None) -> tuple:
        """
        发送 TOS HTTP 请求（带 SigV4 签名）

        Returns: (status_code, response_body_bytes)
        """
        if headers is None:
            headers = {}
        if query:
            qs = '&'.join(
                f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
                for k, v in sorted(query.items())
            )
            url = f"{self.endpoint}/{path}?{qs}"
        else:
            url = f"{self.endpoint}/{path}"

        # 添加 SigV4 必要头
        now = datetime.datetime.utcnow()
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = now.strftime('%Y%m%d')

        headers['x-amz-date'] = amz_date
        headers['x-amz-content-sha256'] = hashlib.sha256(data or b'').hexdigest()
        headers['Host'] = urllib.parse.urlparse(self.endpoint).netloc

        authorization = self._sign(method, path, headers, query)
        headers['Authorization'] = authorization

        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def upload(self, local_path: str, remote_path: str) -> str:
        """
        上传文件到 TOS（网络不可达时跳过）

        Args:
            local_path: 本地文件路径
            remote_path: TOS 相对路径

        Returns:
            TOS 文件路径（网络失败时返回 None）
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        object_path = f"{self.bucket}/{remote_path}"

        with open(local_path, 'rb') as f:
            data = f.read()

        content_type = 'application/octet-stream'
        if local_path.endswith('.json'):
            content_type = 'application/json'
        elif local_path.endswith('.glb'):
            content_type = 'model/gltf-binary'
        elif local_path.endswith('.txt'):
            content_type = 'text/plain'

        headers = {
            'Content-Type': content_type,
            'Content-Length': str(len(data)),
        }

        try:
            code, body = self._make_request('PUT', object_path, data, headers=headers)
            if code not in (200, 201):
                print(f"[Storage] TOS upload HTTP {code}: {body.decode(errors='replace')}")
                return None
            return remote_path
        except Exception as e:
            print(f"[Storage] TOS upload skipped (network unavailable): {e}")
            return None

    def download(self, remote_path: str, local_path: str) -> str:
        """
        从 TOS 下载文件

        Args:
            remote_path: TOS 相对路径
            local_path: 本地保存路径

        Returns:
            本地文件路径
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        object_path = f"{self.bucket}/{remote_path}"

        code, body = self._make_request('GET', object_path)
        if code != 200:
            raise RuntimeError(f"TOS download failed: HTTP {code}")

        with open(local_path, 'wb') as f:
            f.write(body)

        return local_path

    def generate_share_url(self, remote_path: str,
                          expire_seconds: int = 86400) -> str:
        """
        生成预签名下载链接（网络不可达时返回 None）

        Args:
            remote_path: TOS 文件相对路径
            expire_seconds: 过期时间(秒)

        Returns:
            预签名 URL 或 None
        """
        if not self._validate_path(remote_path):
            raise ValueError(f"Invalid remote path: {remote_path}")

        object_path = f"{self.bucket}/{remote_path}"
        expire = datetime.datetime.utcnow() + datetime.timedelta(seconds=expire_seconds)
        amz_date = expire.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = expire.strftime('%Y%m%d')

        # Expires query param
        query = {
            'X-Amz-Algorithm': 'AWS4-HMAC-SHA256',
            'X-Amz-Credential': f"{self.access_key}/{date_stamp}/cn-beijing/tos/aws4_request",
            'X-Amz-Date': amz_date,
            'X-Amz-Expires': str(expire_seconds),
            'X-Amz-SignedHeaders': 'host',
        }

        # String to sign
        canonical_uri = '/' + object_path.lstrip('/')
        canonical_querystring = '&'.join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
            for k, v in sorted(query.items())
        )
        host = urllib.parse.urlparse(self.endpoint).netloc
        canonical_headers = f"host:{host}\n"
        signed_headers = 'host'
        payload_hash = 'UNSIGNED-PAYLOAD'
        canonical_request = '\n'.join([
            'GET', canonical_uri, canonical_querystring,
            canonical_headers, signed_headers, payload_hash
        ])
        hashed_canonical_request = hashlib.sha256(canonical_request.encode()).hexdigest()
        string_to_sign = '\n'.join([
            'AWS4-HMAC-SHA256',
            amz_date,
            f"{date_stamp}/cn-beijing/tos/aws4_request",
            hashed_canonical_request
        ])
        k_date = hmac.new(
            f"AWS4{self.secret_key}".encode(), date_stamp.encode(), hashlib.sha256
        ).digest()
        k_region = hmac.new(k_date, 'cn-beijing'.encode(), hashlib.sha256).digest()
        k_service = hmac.new(k_region, 'tos'.encode(), hashlib.sha256).digest()
        k_signing = hmac.new(k_service, b'aws4_request', hashlib.sha256).digest()
        signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()

        query['X-Amz-Signature'] = signature

        qs = '&'.join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
            for k, v in sorted(query.items())
        )

        url = f"{self.endpoint}/{object_path}?{qs}"
        return url

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

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp_path = tmp.name

            urllib.request.urlretrieve(file_url, tmp_path)

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

            self.upload(tmp_path, tos_path)

            try:
                share_url = self.generate_share_url(tos_path)
            except Exception:
                share_url = None

            return {
                'tos_path': tos_path,
                'share_url': share_url,
                'local_path': None
            }
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
