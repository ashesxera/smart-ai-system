"""
AI-3D 建模系统 - 通知模块

通用通知器：通过 OpenClaw Gateway 将通知投递给主会话，由主会话
通过 message tool 投送给用户（飞书/Telegram/WhatsApp 等）。

不直接调用任何平台 API。
"""

import json
import logging
import os
from typing import Dict, List, Optional

import httpx

from ai_3d_modeling.db import Database, SessionManager, MaterialManager, VendorTaskManager
from ai_3d_modeling.utils import format_duration, format_timestamp

logger = logging.getLogger(__name__)


class ResultSummarizer:
    """结果汇总器"""

    def __init__(self, db: Database):
        self.db = db
        self.session_mgr = SessionManager(db)
        self.material_mgr = MaterialManager(db)
        self.task_mgr = VendorTaskManager(db)

    def summarize(self, session_uuid: str) -> Dict:
        """
        汇总会话的所有供应商结果

        Args:
            session_uuid: 会话UUID

        Returns:
            汇总报告字典
        """
        tasks = self.task_mgr.get_by_session(session_uuid)

        summary = {
            "total_vendors": len(tasks),
            "succeeded": sum(1 for t in tasks if t['status'] == 'succeeded'),
            "failed": sum(1 for t in tasks if t['status'] == 'failed'),
        }

        results = []
        for task in tasks:
            result = {
                "vendor_name": task['vendor_name'],
                "vendor_id": task['vendor_id'],
                "status": task['status'],
            }

            if task['status'] == 'succeeded':
                result.update({
                    "file_format": self._extract_format(task),
                    "share_url": task.get('share_url'),
                    "download_expires": self._format_expires(task.get('share_expires_at'))
                })
            else:
                result.update({
                    "error_code": task.get('error_code'),
                    "error_message": task.get('error_message')
                })

            results.append(result)

        total_time = self.calculate_duration(session_uuid)
        summary['total_time_seconds'] = total_time

        return {
            "event": "all_vendors_completed",
            "session_uuid": session_uuid,
            "summary": summary,
            "results": results
        }

    def check_all_done(self, session_uuid: str) -> bool:
        """检查会话的所有任务是否完成"""
        return self.task_mgr.check_all_done(session_uuid)

    def calculate_duration(self, session_uuid: str) -> int:
        """计算总耗时（秒）"""
        session = self.session_mgr.get(session_uuid)
        if not session:
            return 0

        from datetime import datetime
        now = int(datetime.now().timestamp())

        created_at = session.get('created_at', now)
        completed_at = session.get('completed_at', now)

        if completed_at and completed_at > 0:
            return completed_at - created_at

        return now - created_at

    def build_materials_preview(self, session_uuid: str) -> Dict:
        """构建材料预览信息"""
        materials = self.material_mgr.get_by_session(session_uuid)

        if not materials:
            return {"type": "unknown", "count": 0}

        first = materials[0]
        material_type = first.get('material_type', 'unknown')

        image_count = 0
        preview_url = None

        for m in materials:
            image_urls = m.get('image_urls', [])
            if isinstance(image_urls, str):
                try:
                    image_urls = json.loads(image_urls)
                except:
                    image_urls = []
            image_count += len(image_urls)
            if not preview_url and image_urls:
                preview_url = image_urls[0]

        return {
            "type": material_type,
            "count": image_count,
            "preview_url": preview_url
        }

    def _extract_format(self, task: Dict) -> Optional[str]:
        """从任务中提取文件格式"""
        file_url = task.get('result_file_url') or ''
        for ext in ['.glb', '.obj', '.fbx', '.stl', '.usdz']:
            if ext in file_url:
                return ext.lstrip('.')
        return 'glb'

    def _format_expires(self, timestamp: Optional[int]) -> Optional[str]:
        """格式化过期时间"""
        if timestamp:
            return format_timestamp(timestamp)
        return None


# ------------------------------------------------------------------
# 通知消息标准格式
# ------------------------------------------------------------------

NOTIFICATION_KIND = "ai_3d_modeling.notification"


def build_forward_payload(
    channel: str,
    target: str,
    text: str,
    session_uuid: Optional[str] = None,
) -> Dict:
    """
    构建投递给主会话的标准通知消息。

    主会话收到后应解析 kind=='{NOTIFICATION_KIND}' 的消息，
    提取 channel/target/text，然后调用 message tool 发送。

    Args:
        channel:    目标渠道，如 "feishu"
        target:     目标标识，如 open_id 或 chat_id
        text:       通知文本（支持 Markdown）
        session_uuid: 关联的会话 UUID（可选）

    Returns:
        投递给 /hooks/wake 的文本内容（JSON 字符串）
    """
    payload = {
        "kind": NOTIFICATION_KIND,
        "channel": channel,
        "target": target,
        "text": text,
    }
    if session_uuid:
        payload["session_uuid"] = session_uuid
    return payload


# ------------------------------------------------------------------
# 通知器
# ------------------------------------------------------------------

class Notifier:
    """
    通用通知器：将通知通过 OpenClaw Gateway 投递给主会话，
    由主会话调用 message tool 投送给用户。

    不直接调用任何平台 API（飞书/Telegram 等）。
    """

    # OpenClaw Gateway 默认地址
    DEFAULT_GATEWAY_HOST = "http://127.0.0.1:18789"
    DEFAULT_WAKE_PATH = "/hooks/wake"

    def __init__(
        self,
        gateway_host: str = None,
        gateway_token: str = None,
        feishu_app_id: str = None,
        feishu_app_secret: str = None,
    ):
        """
        初始化通知器。

        Args:
            gateway_host:     Gateway 地址，如 http://127.0.0.1:18789
            gateway_token:    Webhook Token（hooks.token 配置值）
            feishu_app_id:    飞书 App ID（用于从 session_key 解析 open_id）
            feishu_app_secret: 飞书 App Secret（保留，不再用于发消息）
        """
        import os
        self.gateway_host = (gateway_host or
                             os.getenv('GATEWAY_HOST', '').rstrip('/') or
                             self.DEFAULT_GATEWAY_HOST)
        self.gateway_token = gateway_token or os.getenv('GATEWAY_TOKEN', '')
        self.feishu_app_id = feishu_app_id or os.getenv('FEISHU_APP_ID', '')

        self._session: Optional[httpx.Client] = None

    @property
    def _client(self) -> httpx.Client:
        """懒创建 HTTP 客户端"""
        if self._session is None:
            self._session = httpx.Client(timeout=15)
        return self._session

    @property
    def _wake_url(self) -> str:
        return f"{self.gateway_host}{self.DEFAULT_WAKE_PATH}"

    def _wake_headers(self) -> Dict[str, str]:
        """构建认证头"""
        headers = {"Content-Type": "application/json"}
        if self.gateway_token:
            headers["Authorization"] = f"Bearer {self.gateway_token}"
        return headers

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    async def send(self, session_key: str, notification_text: str) -> bool:
        """
        发送通知文本到主会话。

        Args:
            session_key:         OpenClaw 会话标识，格式如 "feishu:user:{open_id}"
            notification_text:   通知内容（Markdown 文本）

        Returns:
            是否投递成功
        """
        try:
            channel, target = self._parse_session_key(session_key)
            payload = build_forward_payload(
                channel=channel,
                target=target,
                text=notification_text,
            )
            return self._wake(json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            logger.warning(f"[Notifier] send failed: {e}")
            return False

    async def send_summary(self, session_key: str, summary: Dict) -> bool:
        """
        发送结果汇总通知。

        Args:
            session_key: 会话标识
            summary:     汇总报告（来自 ResultSummarizer）

        Returns:
            是否投递成功
        """
        text = self._render_summary_text(summary)
        return await self.send(session_key, text)

    async def send_acknowledgment(
        self,
        session_key: str,
        session_uuid: str,
        vendor_count: int,
        material_type: str,
    ) -> bool:
        """
        发送任务接收回执。

        Args:
            session_key:    会话标识
            session_uuid:   会话 UUID
            vendor_count:   提交供应商数量
            material_type:  材料类型

        Returns:
            是否投递成功
        """
        text = self._render_acknowledgment_text(
            session_uuid, vendor_count, material_type
        )
        return await self.send(session_key, text)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _parse_session_key(self, session_key: str) -> tuple[str, str]:
        """
        解析 session_key，返回 (channel, target)。

        支持的格式：
            feishu:user:{open_id}   → ("feishu", "{open_id}")
            feishu:group:{chat_id}  → ("feishu", "{chat_id}")
            feishu:{open_id}        → ("feishu", "{open_id}")  # 兼容旧格式
        """
        if not session_key:
            raise ValueError("session_key cannot be empty")

        parts = session_key.split(':')
        if len(parts) >= 3:
            channel = parts[0]
            # session_key 格式: feishu:user:ou_xxx 或 feishu:group:oc_xxx
            target = parts[-1]
        elif len(parts) == 2:
            channel = parts[0]
            target = parts[1]
        else:
            # fallback: 整个作为 target，假设飞书
            channel = "feishu"
            target = session_key

        return channel, target

    def _wake(self, text: str, mode: str = "now") -> bool:
        """
        发送 POST /hooks/wake 唤醒主会话。

        Args:
            text:  投递的文本内容（应为 JSON 字符串）
            mode:  唤醒模式，"now" 或 "next-heartbeat"

        Returns:
            HTTP 是否返回 2xx
        """
        body = {"text": text, "mode": mode}
        try:
            resp = self._client.post(
                self._wake_url,
                headers=self._wake_headers(),
                json=body,
            )
            if resp.status_code >= 400:
                logger.warning(
                    f"[Notifier] wake failed: HTTP {resp.status_code} "
                    f"body={resp.text[:200]}"
                )
                return False
            logger.info(
                f"[Notifier] wake ok: sessionKey={resp.json().get('sessionKey', '?')}"
            )
            return True
        except Exception as e:
            logger.warning(f"[Notifier] wake request failed: {e}")
            return False

    # ------------------------------------------------------------------
    # 文本渲染（生成用户看到的通知内容）
    # ------------------------------------------------------------------

    def _render_summary_text(self, summary: Dict) -> str:
        """将汇总报告渲染为通知文本（Markdown）"""
        total = summary['summary']['total_vendors']
        succeeded = summary['summary']['succeeded']
        failed = summary['summary']['failed']
        total_time = summary['summary'].get('total_time_seconds', 0)
        session_uuid = summary.get('session_uuid', '')

        # 头部
        if succeeded > 0:
            header = f"🎉 **3D建模完成**（成功 {succeeded}/{total}）"
        else:
            header = f"😔 **3D建模未成功**（失败 {failed}/{total}）"

        lines = [
            header,
            "",
            f"📁 会话ID：`{session_uuid}`",
            f"⏱️ 耗时：{format_duration(total_time)}" if total_time > 0 else "",
            "",
            "---",
            "",
        ]

        for result in summary.get('results', []):
            if result['status'] == 'succeeded':
                vendor = result['vendor_name']
                fmt = result.get('file_format', 'glb').upper()
                url = result.get('share_url') or ''
                expires = result.get('download_expires') or ''

                lines.append(f"✅ **{vendor}** — {fmt}")
                if url:
                    lines.append(f"📥 下载：{url}")
                if expires:
                    lines.append(f"⏰ 过期：{expires}")
                lines.append("")
            else:
                vendor = result['vendor_name']
                err = result.get('error_message', '未知错误')
                lines.append(f"❌ **{vendor}** — {err}")
                lines.append("")

        return "\n".join(lines).strip()

    def _render_acknowledgment_text(
        self,
        session_uuid: str,
        vendor_count: int,
        material_type: str,
    ) -> str:
        """渲染任务接收回执文本"""
        type_emoji = "🖼️" if material_type == "image" else "📝"
        type_text = "图片" if material_type == "image" else "文字"

        return (
            f"🎨 **收到3D建模请求**\n\n"
            f"✅ 已提交 **{vendor_count}** 个供应商处理\n"
            f"{type_emoji} 材料类型：{type_text}\n"
            f"🆔 会话ID：`{session_uuid}`\n\n"
            f"⏱️ 处理时间通常需要 1-3 分钟，完成后会自动通知你"
        )

    # ------------------------------------------------------------------
    # 向后兼容性别名（供现有代码迁移）
    # ------------------------------------------------------------------

    async def send_card(self, session_key: str, card: Dict) -> bool:
        """
        兼容旧 FeishuNotifier 接口：接收飞书卡片的 card dict，
        提取 text 字段后发送。

        未来应直接使用 send() 传 Markdown 文本。
        """
        # 从 card 中提取可读文本
        text = self._extract_card_text(card)
        return await self.send(session_key, text)

    def _extract_card_text(self, card: Dict) -> str:
        """从飞书 card dict 中提取纯文本（兼容用）"""
        try:
            elements = (
                card.get('card', {})
                       .get('element', [])
                       .get('elements', [])
            )
            lines = []
            for el in elements:
                if el.get('tag') == 'div':
                    content = el.get('text', {}).get('content', '')
                    if content:
                        lines.append(content)
            return '\n'.join(lines)
        except Exception:
            return "通知消息"

    def close(self):
        """关闭 HTTP 客户端"""
        if self._session:
            self._session.close()
            self._session = None


# ------------------------------------------------------------------
# 向后兼容性别名
# ------------------------------------------------------------------
FeishuNotifier = Notifier
