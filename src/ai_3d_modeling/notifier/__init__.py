"""
AI-3D 建模系统 - 通知模块

结果汇总和飞书通知
"""

import httpx
from typing import Dict, List, Optional
from ai_3d_modeling.db import Database, SessionManager, MaterialManager, VendorTaskManager
from ai_3d_modeling.utils import format_duration, format_timestamp


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
        
        # 计算总耗时
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
        
        # 统计图片数量
        image_count = 0
        preview_url = None
        
        for m in materials:
            image_urls = m.get('image_urls', [])
            if isinstance(image_urls, str):
                try:
                    import json
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
        file_url = task.get('result_file_url', '')
        if file_url:
            if '.glb' in file_url:
                return 'glb'
            elif '.obj' in file_url:
                return 'obj'
            elif '.fbx' in file_url:
                return 'fbx'
            elif '.stl' in file_url:
                return 'stl'
            elif '.usdz' in file_url:
                return 'usdz'
        return 'glb'
    
    def _format_expires(self, timestamp: Optional[int]) -> Optional[str]:
        """格式化过期时间"""
        if timestamp:
            return format_timestamp(timestamp)
        return None


class FeishuNotifier:
    """飞书通知器（通过 Feishu API 直接发送）"""

    FEISHU_API_BASE = "https://open.feishu.cn/open-apis"

    def __init__(self, gateway_url: str = None,
                 feishu_app_id: str = None,
                 feishu_app_secret: str = None):
        """
        初始化通知器

        Args:
            gateway_url: Gateway Webhook URL（已废弃，保留兼容）
            feishu_app_id: Feishu App ID
            feishu_app_secret: Feishu App Secret
        """
        import os
        self.gateway_url = gateway_url or os.getenv('FEISHU_APP_ID', '')
        self.feishu_app_id = feishu_app_id or os.getenv('FEISHU_APP_ID', '')
        self.feishu_app_secret = feishu_app_secret or os.getenv('FEISHU_APP_SECRET', '')
        self._tenant_token = None
        self._token_expires_at = 0

    def _get_tenant_token(self) -> str:
        """获取 tenant access token（带缓存）"""
        import time, json
        # 如果 token 还未过期（提前 60s 缓冲），直接返回
        if self._tenant_token and time.time() < self._token_expires_at - 60:
            return self._tenant_token

        resp = httpx.post(
            f"{self.FEISHU_API_BASE}/auth/v3/tenant_access_token/internal",
            json={
                "app_id": self.feishu_app_id,
                "app_secret": self.feishu_app_secret
            },
            timeout=10
        )
        data = resp.json()
        if data.get('code') != 0:
            raise RuntimeError(f"Feishu auth failed: {data.get('msg')}")
        self._tenant_token = data['tenant_access_token']
        self._token_expires_at = time.time() + data.get('expire', 7200)
        return self._tenant_token

    def _send_via_feishu_api(self, open_id: str, card: Dict) -> bool:
        """通过 Feishu API 发送交互卡片给用户"""
        import json
        token = self._get_tenant_token()
        resp = httpx.post(
            f"{self.FEISHU_API_BASE}/im/v1/messages?receive_id_type=open_id",
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            },
            json={
                'receive_id': open_id,
                'msg_type': 'interactive',
                'content': json.dumps(card)
            },
            timeout=15
        )
        result = resp.json()
        return result.get('code') == 0

    def _parse_open_id(self, session_key: str) -> str:
        """从 session_key 解析 open_id"""
        # 格式: feishu:user:{open_id} 或 feishu:group:{chat_id}
        if ':' in session_key:
            return session_key.split(':', 2)[-1]
        return session_key
    
    def build_card(self, summary: Dict) -> Dict:
        """
        构建飞书消息卡片
        
        Args:
            summary: 汇总报告
        
        Returns:
            飞书卡片格式字典
        """
        # 构建头部
        success_count = summary['summary']['succeeded']
        header_template = 'green' if success_count > 0 else 'red'
        header_title = '🎉 3D建模完成' if success_count > 0 else '😔 3D建模未成功'
        
        # 构建元素
        elements = []
        
        # 摘要行
        elements.append({
            "tag": "div",
            "text": {
                "tag": "plain_text",
                "content": f"成功: {success_count} | 失败: {summary['summary']['failed']}"
            }
        })
        
        # 耗时
        total_time = summary['summary'].get('total_time_seconds', 0)
        if total_time > 0:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "plain_text",
                    "content": f"⏱️ 耗时: {format_duration(total_time)}"
                }
            })
        
        elements.append({"tag": "hr"})
        
        # 结果列表
        for result in summary.get('results', []):
            if result['status'] == 'succeeded':
                line = f"✅ {result['vendor_name']} - {result.get('file_format', 'glb').upper()}"
                elements.append({
                    "tag": "div",
                    "text": {"tag": "plain_text", "content": line}
                })
                
                # 下载链接
                share_url = result.get('share_url')
                if share_url:
                    elements.append({
                        "tag": "div",
                        "text": {
                            "tag": "plain_text",
                            "content": f"📥 下载: {share_url}"
                        }
                    })
            else:
                error_msg = result.get('error_message', '未知错误')
                line = f"❌ {result['vendor_name']} - {error_msg}"
                elements.append({
                    "tag": "div",
                    "text": {"tag": "plain_text", "content": line}
                })
        
        # 构建卡片
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": header_title
                    },
                    "template": header_template
                },
                "elements": elements
            }
        }
        
        return card
    
    async def send(self, session_key: str, card: Dict) -> bool:
        """
        发送卡片消息（通过 Feishu API）

        Args:
            session_key: 会话标识
            card: 卡片内容

        Returns:
            是否发送成功
        """
        try:
            open_id = self._parse_open_id(session_key)
            return self._send_via_feishu_api(open_id, card)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Feishu send failed: {e}")
            return False
    
    async def send_summary(self, session_key: str, summary: Dict) -> bool:
        """
        发送汇总通知
        
        Args:
            session_key: 会话标识
            summary: 汇总报告
        
        Returns:
            是否发送成功
        """
        card = self.build_card(summary)
        return await self.send(session_key, card)
