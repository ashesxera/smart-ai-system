"""
db/__main__.py - 数据库模块入口

支持通过 python -m ai_3d_modeling.db 调用

用法：
    python -m ai_3d_modeling.db                              # 初始化数据库
    python -m ai_3d_modeling.db --help                       # 显示帮助
    python -m ai_3d_modeling.db --db-path ./data/test.db   # 指定数据库路径
"""

import argparse
import os
import sys
import json

# 确保 src 目录在 path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_PROJECT_ROOT, 'src'))

from ai_3d_modeling.db import Database


def init_database(db_path: str, insert_vendors: bool = True):
    """初始化数据库"""
    db_dir = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(db_dir, exist_ok=True)

    db = Database(db_path)
    db.initialize()
    print("✓ Tables created")

    if insert_vendors:
        _insert_vendor_configs(db)
        print("✓ Vendor configs inserted")

    db.close()
    print(f"\n✅ Database initialized: {db_path}")


def _insert_vendor_configs(db: Database):
    """插入默认供应商配置"""
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
            "request_template": {"model": "${model}", "content": "${content}"},
            "content_template": [{"type": "image_url", "image_url": {"url": "${image_url_0}"}}],
            "response_parser": {"vendor_task_id": "$.id", "status": "$.status", "file_url": "$.content.file_url"},
            "status_map": {"queued": "queued", "running": "running", "succeeded": "succeeded", "failed": "failed"}
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
            "request_template": {"model": "${model}", "content": "${content}"},
            "content_template": [
                {"type": "text", "text": "${text_content}"},
                {"type": "image_url", "image_url": {"url": "${image_url_0}"}}
            ],
            "response_parser": {"vendor_task_id": "$.id", "status": "$.status", "file_url": "$.content.file_url"},
            "status_map": {"queued": "queued", "running": "running", "succeeded": "succeeded", "failed": "failed"}
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
            "request_template": {"model": "${model}", "content": "${content}"},
            "content_template": [{"type": "image_url", "image_url": {"url": "${image_url_0}"}}],
            "response_parser": {"vendor_task_id": "$.id", "status": "$.status", "file_url": "$.content.file_url"},
            "status_map": {"queued": "queued", "running": "running", "succeeded": "succeeded", "failed": "failed"}
        },
    ]

    for vendor in vendors:
        key = vendor["key"]
        name = vendor["name"]
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
    parser = argparse.ArgumentParser(description='AI-3D Modeling 数据库管理')
    parser.add_argument('--db-path', default='./data/ai-3d-modeling.db',
                       help='数据库路径 (默认: ./data/ai-3d-modeling.db)')
    parser.add_argument('--no-vendors', action='store_true',
                       help='跳过供应商配置初始化')
    args = parser.parse_args()

    init_database(args.db_path, insert_vendors=not args.no_vendors)
