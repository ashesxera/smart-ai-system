"""
AI-3D 建模系统 - 数据库模块

SQLite 数据库操作封装
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path


class Database:
    """数据库连接和操作类"""
    
    _local = threading.local()
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_db_directory()
    
    def _ensure_db_directory(self):
        """确保数据库目录存在"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接（线程本地）"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            # 启用外键约束
            self._local.conn.execute('PRAGMA foreign_keys = ON')
        return self._local.conn
    
    @contextmanager
    def get_cursor(self):
        """获取数据库游标的上下文管理器"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def execute(self, sql: str, params: tuple = None) -> List[Dict]:
        """执行SQL查询并返回结果"""
        with self.get_cursor() as cursor:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            # SELECT 查询返回结果
            if sql.strip().upper().startswith('SELECT'):
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            return []
    
    def initialize(self):
        """初始化数据库表结构"""
        # 创建 sessions 表
        self.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_uuid TEXT NOT NULL UNIQUE,
                channel_type TEXT NOT NULL DEFAULT 'feishu',
                channel_user_id TEXT NOT NULL,
                channel_user_name TEXT,
                group_id TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                phase TEXT NOT NULL DEFAULT 'pending',
                material_summary TEXT,
                user_input TEXT,
                source_message_id TEXT,
                source_session_key TEXT,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                completed_at INTEGER
            )
        ''')
        
        # 创建 materials 表
        self.execute('''
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material_uuid TEXT NOT NULL UNIQUE,
                session_uuid TEXT NOT NULL,
                material_type TEXT NOT NULL,
                source_type TEXT NOT NULL,
                text_content TEXT,
                image_urls TEXT,
                file_name TEXT,
                file_size INTEGER,
                file_mime_type TEXT,
                local_path TEXT,
                tos_path TEXT,
                generation_params TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (session_uuid) REFERENCES sessions(session_uuid) ON DELETE CASCADE
            )
        ''')
        
        # 创建 vendor_tasks 表
        self.execute('''
            CREATE TABLE IF NOT EXISTS vendor_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vendor_task_uuid TEXT NOT NULL UNIQUE,
                session_uuid TEXT NOT NULL,
                material_uuid TEXT NOT NULL,
                vendor_id TEXT NOT NULL,
                vendor_name TEXT NOT NULL,
                model_name TEXT NOT NULL,
                vendor_task_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                status_message TEXT,
                api_endpoint TEXT,
                api_request_body TEXT,
                api_response TEXT,
                error_code TEXT,
                error_message TEXT,
                result_file_url TEXT,
                result_file_size INTEGER,
                local_result_path TEXT,
                tos_result_path TEXT,
                share_url TEXT,
                share_expires_at INTEGER,
                poll_count INTEGER DEFAULT 0,
                last_poll_at INTEGER,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                submitted_at INTEGER,
                completed_at INTEGER,
                FOREIGN KEY (session_uuid) REFERENCES sessions(session_uuid) ON DELETE CASCADE,
                FOREIGN KEY (material_uuid) REFERENCES materials(material_uuid) ON DELETE CASCADE
            )
        ''')
        
        # 创建 results 表
        self.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_uuid TEXT NOT NULL UNIQUE,
                vendor_task_uuid TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER,
                file_format TEXT,
                tos_bucket TEXT NOT NULL DEFAULT '4-ark-claw',
                tos_path TEXT NOT NULL,
                share_url TEXT,
                share_expires_at INTEGER,
                polygon_count INTEGER,
                texture_resolution TEXT,
                has_alpha INTEGER DEFAULT 0,
                is_selected INTEGER DEFAULT 0,
                selected_at INTEGER,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                FOREIGN KEY (vendor_task_uuid) REFERENCES vendor_tasks(vendor_task_uuid) ON DELETE CASCADE
            )
        ''')
        
        # 创建 ops_log 表
        self.execute('''
            CREATE TABLE IF NOT EXISTS ops_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_uuid TEXT,
                vendor_task_uuid TEXT,
                action TEXT NOT NULL,
                actor TEXT NOT NULL DEFAULT 'system',
                detail TEXT,
                status TEXT NOT NULL DEFAULT 'success',
                duration_ms INTEGER,
                error_message TEXT,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        # 创建 settings 表
        self.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL,
                value_type TEXT DEFAULT 'string',
                description TEXT,
                category TEXT,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        # 创建索引
        self.execute('CREATE INDEX IF NOT EXISTS idx_sessions_uuid ON sessions(session_uuid)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(channel_type, channel_user_id)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status, phase)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_materials_uuid ON materials(material_uuid)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_materials_session ON materials(session_uuid)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_vendor_tasks_uuid ON vendor_tasks(vendor_task_uuid)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_vendor_tasks_session ON vendor_tasks(session_uuid)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_vendor_tasks_status ON vendor_tasks(status)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_results_uuid ON results(result_uuid)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_results_task ON results(vendor_task_uuid)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_ops_log_session ON ops_log(session_uuid)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_ops_log_task ON ops_log(vendor_task_uuid)')
        self.execute('CREATE INDEX IF NOT EXISTS idx_settings_category ON settings(category)')
    
    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


class SessionManager:
    """会话管理"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, session_uuid: str, channel_type: str, channel_user_id: str,
               channel_user_name: str = None, group_id: str = None,
               user_input: str = None, source_message_id: str = None,
               source_session_key: str = None) -> Dict:
        """创建新会话"""
        self.db.execute('''
            INSERT INTO sessions 
            (session_uuid, channel_type, channel_user_id, channel_user_name, group_id, 
             user_input, source_message_id, source_session_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_uuid, channel_type, channel_user_id, channel_user_name,
              group_id, user_input, source_message_id, source_session_key))
        
        return self.get(session_uuid)
    
    def get(self, session_uuid: str) -> Optional[Dict]:
        """获取会话"""
        results = self.db.execute(
            'SELECT * FROM sessions WHERE session_uuid = ?', (session_uuid,))
        return results[0] if results else None
    
    def update_phase(self, session_uuid: str, phase: str):
        """更新会话阶段"""
        self.db.execute('''
            UPDATE sessions SET phase = ?, updated_at = strftime('%s', 'now')
            WHERE session_uuid = ?
        ''', (phase, session_uuid))
    
    def update_status(self, session_uuid: str, status: str):
        """更新会话状态"""
        completed_at = int(datetime.now().timestamp()) if status in ('completed', 'cancelled') else None
        self.db.execute('''
            UPDATE sessions 
            SET status = ?, updated_at = strftime('%s', 'now'), completed_at = ?
            WHERE session_uuid = ?
        ''', (status, completed_at, session_uuid))
    
    def get_active_sessions(self) -> List[Dict]:
        """获取所有活跃会话"""
        return self.db.execute(
            "SELECT * FROM sessions WHERE status = 'active'"
        )


class MaterialManager:
    """材料管理"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, material_uuid: str, session_uuid: str, material_type: str,
               source_type: str, text_content: str = None, image_urls: List[str] = None,
               file_name: str = None, file_size: int = None,
               file_mime_type: str = None) -> Dict:
        """创建材料记录"""
        image_urls_json = json.dumps(image_urls) if image_urls else None
        
        self.db.execute('''
            INSERT INTO materials
            (material_uuid, session_uuid, material_type, source_type, text_content,
             image_urls, file_name, file_size, file_mime_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (material_uuid, session_uuid, material_type, source_type, text_content,
              image_urls_json, file_name, file_size, file_mime_type))
        
        return self.get(material_uuid)
    
    def get(self, material_uuid: str) -> Optional[Dict]:
        """获取材料"""
        results = self.db.execute(
            'SELECT * FROM materials WHERE material_uuid = ?', (material_uuid,))
        if results:
            material = results[0]
            if material.get('image_urls'):
                try:
                    material['image_urls'] = json.loads(material['image_urls'])
                except:
                    material['image_urls'] = []
            return material
        return None
    
    def get_by_session(self, session_uuid: str) -> List[Dict]:
        """获取会话的所有材料"""
        materials = self.db.execute(
            'SELECT * FROM materials WHERE session_uuid = ?', (session_uuid,))
        
        for material in materials:
            if material.get('image_urls'):
                try:
                    material['image_urls'] = json.loads(material['image_urls'])
                except:
                    material['image_urls'] = []
        
        return materials
    
    def update_status(self, material_uuid: str, status: str):
        """更新材料状态"""
        self.db.execute('''
            UPDATE materials SET status = ?, updated_at = strftime('%s', 'now')
            WHERE material_uuid = ?
        ''', (status, material_uuid))


class VendorTaskManager:
    """供应商任务管理"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, vendor_task_uuid: str, session_uuid: str, material_uuid: str,
               vendor_id: str, vendor_name: str, model_name: str,
               api_endpoint: str = None, api_request_body: str = None) -> Dict:
        """创建供应商任务"""
        self.db.execute('''
            INSERT INTO vendor_tasks
            (vendor_task_uuid, session_uuid, material_uuid, vendor_id, vendor_name,
             model_name, api_endpoint, api_request_body)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (vendor_task_uuid, session_uuid, material_uuid, vendor_id, vendor_name,
              model_name, api_endpoint, api_request_body))
        
        return self.get(vendor_task_uuid)
    
    def get(self, vendor_task_uuid: str) -> Optional[Dict]:
        """获取任务"""
        results = self.db.execute(
            'SELECT * FROM vendor_tasks WHERE vendor_task_uuid = ?', (vendor_task_uuid,))
        return results[0] if results else None
    
    def get_by_session(self, session_uuid: str) -> List[Dict]:
        """获取会话的所有任务"""
        return self.db.execute(
            'SELECT * FROM vendor_tasks WHERE session_uuid = ?', (session_uuid,))
    
    def get_running(self) -> List[Dict]:
        """获取所有运行中的任务"""
        return self.db.execute('''
            SELECT vt.*, s.value as config
            FROM vendor_tasks vt
            LEFT JOIN settings s ON vt.vendor_id = s.key
            WHERE vt.status IN ('queued', 'running')
            AND s.category = 'vendor'
            AND s.value LIKE '%"is_active": true%'
        ''')
    
    def update_status(self, vendor_task_uuid: str, status: str,
                      status_message: str = None, api_response: str = None,
                      error_code: str = None, error_message: str = None,
                      result_file_url: str = None):
        """更新任务状态"""
        completed_at = int(datetime.now().timestamp()) if status in ('succeeded', 'failed', 'cancelled', 'timeout') else None
        
        self.db.execute(f'''
            UPDATE vendor_tasks 
            SET status = ?, status_message = ?, api_response = ?,
                error_code = ?, error_message = ?, result_file_url = ?,
                updated_at = strftime('%s', 'now'), completed_at = ?
            WHERE vendor_task_uuid = ?
        ''', (status, status_message, api_response, error_code, error_message,
              result_file_url, completed_at, vendor_task_uuid))
    
    def set_vendor_task_id(self, vendor_task_uuid: str, vendor_task_id: str,
                           api_response: str = None):
        """设置供应商返回的任务ID"""
        self.db.execute('''
            UPDATE vendor_tasks 
            SET vendor_task_id = ?, api_response = ?, 
                status = 'queued', submitted_at = strftime('%s', 'now'),
                updated_at = strftime('%s', 'now')
            WHERE vendor_task_uuid = ?
        ''', (vendor_task_id, api_response, vendor_task_uuid))
    
    def increment_poll_count(self, vendor_task_uuid: str):
        """增加轮询计数"""
        self.db.execute('''
            UPDATE vendor_tasks 
            SET poll_count = poll_count + 1, 
                last_poll_at = strftime('%s', 'now'),
                status = CASE WHEN status = 'queued' THEN 'running' ELSE status END
            WHERE vendor_task_uuid = ?
        ''', (vendor_task_uuid,))
    
    def check_all_done(self, session_uuid: str) -> bool:
        """检查会话的所有任务是否完成"""
        results = self.db.execute('''
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN status IN ('succeeded', 'failed', 'cancelled', 'timeout') THEN 1 ELSE 0 END) as done
            FROM vendor_tasks
            WHERE session_uuid = ?
        ''', (session_uuid,))
        
        if results:
            r = results[0]
            return r['total'] > 0 and r['total'] == r['done']
        return False


class ResultManager:
    """结果管理"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, result_uuid: str, vendor_task_uuid: str, file_name: str,
               file_size: int = None, file_format: str = None,
               tos_bucket: str = '4-ark-claw', tos_path: str = None,
               share_url: str = None, share_expires_at: int = None) -> Dict:
        """创建结果记录"""
        self.db.execute('''
            INSERT INTO results
            (result_uuid, vendor_task_uuid, file_name, file_size, file_format,
             tos_bucket, tos_path, share_url, share_expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (result_uuid, vendor_task_uuid, file_name, file_size, file_format,
              tos_bucket, tos_path, share_url, share_expires_at))
        
        return self.get(result_uuid)
    
    def get(self, result_uuid: str) -> Optional[Dict]:
        """获取结果"""
        results = self.db.execute(
            'SELECT * FROM results WHERE result_uuid = ?', (result_uuid,))
        return results[0] if results else None
    
    def get_by_task(self, vendor_task_uuid: str) -> List[Dict]:
        """获取任务的所有结果"""
        return self.db.execute(
            'SELECT * FROM results WHERE vendor_task_uuid = ?', (vendor_task_uuid,))


class OpsLogManager:
    """操作日志管理"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def log(self, action: str, session_uuid: str = None,
            vendor_task_uuid: str = None, detail: str = None,
            status: str = 'success', duration_ms: int = None,
            error_message: str = None, actor: str = 'system'):
        """记录操作日志"""
        self.db.execute('''
            INSERT INTO ops_log
            (session_uuid, vendor_task_uuid, action, actor, detail, status, duration_ms, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_uuid, vendor_task_uuid, action, actor, detail, status, duration_ms, error_message))
