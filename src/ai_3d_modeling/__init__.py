"""
AI-3D 建模系统

基于 Volcengine Ark 3D API 的多供应商 AI 3D 建模平台

主要模块：
- adapters: 模板驱动的 API 适配器
- db: SQLite 数据库操作
- poller: 批量轮询守护进程
- storage: TOS 存储管理
- notifier: 结果汇总通知
- skill: 飞书 Skill 入口
- utils: 通用工具函数
"""

__version__ = '1.0.0'
__author__ = 'AI Team'
