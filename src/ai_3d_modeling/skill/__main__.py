"""skill/__main__.py -- Skill HTTP 服务入口

【已弃用】请使用 skill/standalone.py

此模块提供 HTTP 服务来接收飞书 webhook 事件。

【弃用原因】
OpenClaw 的 Skill 机制是基于对话的，AI 直接调用 Python 函数处理请求，
不需要独立的 HTTP 服务接收外部事件。

OpenClaw 通过内部机制触发 Skill：
- 飞书消息由 OpenClaw 的 channel 插件接收（openclaw 进程）
- 消息被转换为内部事件，注入到 AI 对话中
- AI 根据 SKILL.md 的指引，直接调用 skill 模块的函数

轮询任务结果由独立的 poller 进程处理，无需服务端推送。

【请使用】
skill/standalone.py 提供了直接被 OpenClaw AI 调用的接口。

---

历史：
- 2026-04-23: 创建 HTTP 服务版本
- 2026-04-23: 重构为 standalone.py，直接被 OpenClaw 调用
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from typing import Dict

from aiohttp import web

from ai_3d_modeling.skill import SkillHandler
from ai_3d_modeling.db import Database
from ai_3d_modeling.notifier import FeishuNotifier

logger = logging.getLogger(__name__)


def load_config() -> Dict:
    """
    加载配置
    
    从环境变量和配置文件读取配置
    """
    config = {
        'db_path': os.getenv('DB_PATH', './data/ai-3d-modeling.db'),
        'gateway_url': os.getenv('GATEWAY_URL', 'http://127.0.0.1:18789/webhook/notify'),
        'feishu_app_id': os.getenv('FEISHU_APP_ID', ''),
        'feishu_app_secret': os.getenv('FEISHU_APP_SECRET', ''),
        'port': int(os.getenv('SKILL_PORT', '8000')),
    }
    return config


async def handle_webhook(request: web.Request) -> web.Response:
    """
    处理飞书 webhook 请求
    
    Args:
        request: aiohttp 请求对象
    
    Returns:
        JSON 响应
    """
    try:
        # 解析请求体
        event = await request.json()
        logger.info(f"Received event: {json.dumps(event, ensure_ascii=False)[:200]}")
        
        # 获取 handler 实例
        handler = request.app['skill_handler']
        
        # 处理事件
        result = await handler.handle_event(event)
        
        logger.info(f"Handler result: {json.dumps(result, ensure_ascii=False)[:200]}")
        
        return web.json_response(result)
    
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return web.json_response({
            'code': 50001,
            'msg': f'服务器内部错误: {str(e)}',
            'data': None
        }, status=500)


async def handle_health(request: web.Request) -> web.Response:
    """健康检查端点"""
    return web.json_response({'status': 'ok', 'service': 'ai-3d-modeling-skill', 'deprecated': True})


async def handle_session_message(request: web.Request) -> web.Response:
    """
    处理会话消息（通过 OpenClaw Session API）
    
    这是一个可选的接口，允许通过 session key 发送消息
    """
    try:
        data = await request.json()
        session_key = data.get('session_key')
        message = data.get('message')
        
        if not session_key or not message:
            return web.json_response({
                'code': 40001,
                'msg': '缺少 session_key 或 message',
                'data': None
            }, status=400)
        
        # 通过 notifier 发送消息
        handler = request.app['skill_handler']
        notifier = handler.notifier
        
        # 构建消息卡片
        summary = {'message': message}
        card = notifier.build_card(summary)
        
        # 发送消息
        success = await notifier.send_to_session(session_key, card)
        
        return web.json_response({
            'code': 0 if success else 50001,
            'msg': 'success' if success else '发送失败',
            'data': {'sent': success}
        })
    
    except Exception as e:
        logger.error(f"Error sending session message: {e}")
        return web.json_response({
            'code': 50001,
            'msg': f'服务器内部错误: {str(e)}',
            'data': None
        }, status=500)


def create_app(config: Dict) -> web.Application:
    """
    创建 aiohttp 应用
    
    Args:
        config: 配置字典
    
    Returns:
        web.Application
    """
    # 初始化组件
    db = Database(config['db_path'])
    notifier = FeishuNotifier(config['gateway_url'])
    handler = SkillHandler(db, notifier)
    
    # 创建应用
    app = web.Application()
    
    # 存储 handler 以便在路由中使用
    app['skill_handler'] = handler
    app['config'] = config
    
    # 注册路由
    app.router.add_post('/webhook/feishu', handle_webhook)
    app.router.add_post('/api/session/message', handle_session_message)
    app.router.add_get('/health', handle_health)
    
    return app


def run_server(config: Dict):
    """
    运行 HTTP 服务器
    
    Args:
        config: 配置字典
    """
    app = create_app(config)
    
    host = config.get('host', '0.0.0.0')
    port = config.get('port', 8000)
    
    logger.info(f"Starting AI-3D-Modeling Skill server on {host}:{port}")
    logger.warning("【已弃用】请使用 skill/standalone.py")
    
    web.run_app(app, host=host, port=port, access_log=logger)


def main():
    """主入口"""
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 解析参数
    parser = argparse.ArgumentParser(description='AI-3D Modeling Skill HTTP Server (已弃用)')
    parser.add_argument('--host', default='0.0.0.0', help='监听地址 (默认: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8000, help='监听端口 (默认: 8000)')
    parser.add_argument('--db-path', default='./data/ai-3d-modeling.db', help='数据库路径')
    parser.add_argument('--gateway-url', default='http://127.0.0.1:18789/webhook/notify', help='Gateway URL')
    args = parser.parse_args()
    
    # 构建配置
    config = {
        'host': args.host,
        'port': args.port,
        'db_path': args.db_path,
        'gateway_url': args.gateway_url,
    }
    
    # 从环境变量覆盖
    config['db_path'] = os.getenv('DB_PATH', config['db_path'])
    config['gateway_url'] = os.getenv('GATEWAY_URL', config['gateway_url'])
    
    print("=" * 60)
    print("【警告】HTTP 服务模式已弃用！")
    print("请使用 skill/standalone.py，直接被 OpenClaw 调用")
    print("=" * 60)
    
    try:
        run_server(config)
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == '__main__':
    main()
