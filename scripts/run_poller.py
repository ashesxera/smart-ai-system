#!/usr/bin/env python3
"""
scripts/run_poller.py - Poller 守护进程启动脚本

用法:
    python scripts/run_poller.py
    python scripts/run_poller.py --interval 30
    python scripts/run_poller.py --help

环境变量:
    DB_PATH: 数据库路径 (默认: ./data/ai-3d-modeling.db)
    TOS_BUCKET: TOS Bucket 名称
    TOS_BASE_PATH: TOS 基础路径
    GATEWAY_URL: Gateway URL
    ARK_API_KEY: Ark API 密钥
    LOG_LEVEL: 日志级别 (DEBUG/INFO/WARNING/ERROR)
"""

import argparse
import asyncio
import logging
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ai_3d_modeling.poller import run_poller


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='AI-3D Modeling Poller 守护进程',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/run_poller.py
    python scripts/run_poller.py --interval 30
    python scripts/run_poller.py --db-path ./data/ai-3d-modeling.db
    python scripts/run_poller.py --log-level DEBUG
        """
    )
    
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=60,
        help='轮询间隔（秒），默认: 60'
    )
    
    parser.add_argument(
        '--db-path',
        type=str,
        default=os.getenv('DB_PATH', './data/ai-3d-modeling.db'),
        help='数据库路径，默认: ./data/ai-3d-modeling.db'
    )
    
    parser.add_argument(
        '--tos-bucket',
        type=str,
        default=os.getenv('TOS_BUCKET', '4-ark-claw'),
        help='TOS Bucket 名称'
    )
    
    parser.add_argument(
        '--tos-base-path',
        type=str,
        default=os.getenv('TOS_BASE_PATH', 'ai-3d-system'),
        help='TOS 基础路径'
    )
    
    parser.add_argument(
        '--gateway-url',
        type=str,
        default=os.getenv('GATEWAY_URL', 'http://127.0.0.1:18789/webhook/notify'),
        help='Gateway URL'
    )
    
    parser.add_argument(
        '--ark-api-key',
        type=str,
        default=os.getenv('ARK_API_KEY', ''),
        help='Ark API 密钥'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        default=os.getenv('LOG_LEVEL', 'INFO'),
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='日志级别，默认: INFO'
    )
    
    return parser.parse_args()


def setup_logging(log_level: str):
    """配置日志"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main():
    """主入口"""
    args = parse_args()
    
    # 配置日志
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # 构建配置
    config = {
        'db_path': args.db_path,
        'tos_bucket': args.tos_bucket,
        'tos_base_path': args.tos_base_path,
        'gateway_url': args.gateway_url,
        'polling_interval': args.interval,
        'api_key': args.ark_api_key,
    }
    
    logger.info('=' * 50)
    logger.info('AI-3D Modeling Poller 启动')
    logger.info('=' * 50)
    logger.info(f'轮询间隔: {args.interval}s')
    logger.info(f'数据库: {args.db_path}')
    logger.info(f'TOS Bucket: {args.tos_bucket}')
    logger.info(f'Gateway: {args.gateway_url}')
    logger.info(f'日志级别: {args.log_level}')
    logger.info('=' * 50)
    
    try:
        # 直接调用 run_poller，它内部会处理 asyncio.run()
        asyncio.run(run_poller(config))
    except KeyboardInterrupt:
        logger.info('Poller 已停止')
    except Exception as e:
        logger.error(f'Poller 异常退出: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
