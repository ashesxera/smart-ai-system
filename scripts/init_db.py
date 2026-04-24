#!/usr/bin/env python3
"""
数据库初始化脚本
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai_3d_modeling.db import Database
from ai_3d_modeling.utils import generate_uuid, get_timestamp
import json


def init_database(db_path: str = './data/ai-3d-modeling.db'):
    """初始化数据库"""
    print(f"Initializing database: {db_path}")
    
    # 确保目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # 创建数据库
    db = Database(db_path)
    
    # 初始化表结构
    db.initialize()
    print("✓ Tables created")
    
    # 插入供应商配置
    insert_vendor_configs(db)
    print("✓ Vendor configs inserted")
    
    db.close()
    print(f"\nDatabase initialized successfully: {db_path}")


def insert_vendor_configs(db: Database):
    """插入供应商配置"""
    
    vendors = [
        {
            "key": "vendor_ark_seed3d",
            "name": "豆包Seed3D",
            "model": "doubao-seed3d-2-0-260328",
            "adapter": "ark_generic",
            "endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
            "query_endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/${vendor_task_id}",
            "method": "POST",
            "auth_type": "bearer",
            "timeout_minutes": 30,
            "priority": 10,
            "is_active": True,
            "supported_formats": ["glb"],
            "max_images": 1,
            "max_image_size_mb": 10,
            "request_template": {
                "model": "${model}",
                "content": "${content}"
            },
            "content_template": [
                {"type": "image_url", "image_url": {"url": "${image_url_0}"}}
            ],
            "response_parser": {
                "vendor_task_id": "$.id",
                "status": "$.status",
                "file_url": "$.content.file_url"
            },
            "status_map": {
                "queued": "queued",
                "running": "running",
                "succeeded": "succeeded",
                "failed": "failed"
            }
        },
        {
            "key": "vendor_ark_yingmou",
            "name": "影眸Hyper3D",
            "model": "hyper3d-gen2-260112",
            "adapter": "ark_generic",
            "endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
            "query_endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/${vendor_task_id}",
            "method": "POST",
            "auth_type": "bearer",
            "timeout_minutes": 30,
            "priority": 10,
            "is_active": True,
            "supported_formats": ["glb", "obj", "fbx"],
            "max_images": 4,
            "max_image_size_mb": 10,
            "request_template": {
                "model": "${model}",
                "content": "${content}"
            },
            "content_template": [
                {"type": "text", "text": "${text_content}"},
                {"type": "image_url", "image_url": {"url": "${image_url_0}"}}
            ],
            "response_parser": {
                "vendor_task_id": "$.id",
                "status": "$.status",
                "file_url": "$.content.file_url"
            },
            "status_map": {
                "queued": "queued",
                "running": "running",
                "succeeded": "succeeded",
                "failed": "failed"
            }
        },
        {
            "key": "vendor_ark_shumei",
            "name": "数美Hitem3D",
            "model": "hitem3d-2-0-251223",
            "adapter": "ark_generic",
            "endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks",
            "query_endpoint": "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/${vendor_task_id}",
            "method": "POST",
            "auth_type": "bearer",
            "timeout_minutes": 30,
            "priority": 10,
            "is_active": True,
            "supported_formats": ["obj", "glb", "stl", "fbx", "usdz"],
            "max_images": 4,
            "max_image_size_mb": 10,
            "request_template": {
                "model": "${model}",
                "content": "${content}"
            },
            "content_template": [
                {"type": "image_url", "image_url": {"url": "${image_url_0}"}}
            ],
            "response_parser": {
                "vendor_task_id": "$.id",
                "status": "$.status",
                "file_url": "$.content.file_url"
            },
            "status_map": {
                "queued": "queued",
                "running": "running",
                "succeeded": "succeeded",
                "failed": "failed"
            }
        }
    ]
    
    for vendor in vendors:
        key = vendor["key"]
        name = vendor["name"]

        # 检查是否已存在
        existing = db.execute(
            "SELECT id FROM settings WHERE key = ? AND category = 'vendor'",
            (key,)
        )

        if existing:
            print(f"  - {name}: already exists, skipping")
            continue

        db.execute(
            """INSERT INTO settings (key, value, value_type, description, category)
               VALUES (?, ?, 'json', ?, 'vendor')""",
            (key, json.dumps(vendor), name)
        )
        print(f"  - {name}: inserted")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Initialize AI-3D Modeling database')
    parser.add_argument('--db-path', default='./data/ai-3d-modeling.db',
                       help='Database path')
    args = parser.parse_args()
    
    init_database(args.db_path)
