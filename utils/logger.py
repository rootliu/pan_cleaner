"""
操作日志记录模块
"""

import os
import json
from datetime import datetime
from typing import List, Optional

# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')


def _ensure_log_dir():
    """确保日志目录存在"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)


def _get_log_path(provider_name: str, username: str) -> str:
    """获取日志文件路径（按用户区分）"""
    _ensure_log_dir()
    safe_name = f"{provider_name}_{username}".replace('/', '_').replace('\\', '_')
    return os.path.join(LOG_DIR, f"{safe_name}.log")


def log_delete_operation(provider_name: str, username: str, paths: List[str],
                         deleted: List[str], failed: List[str],
                         message: str = ''):
    """
    记录删除操作日志

    Args:
        provider_name: 网盘类型名称
        username: 用户名
        paths: 请求删除的路径列表
        deleted: 成功删除的路径列表
        failed: 删除失败的路径列表
        message: 操作结果消息
    """
    try:
        log_path = _get_log_path(provider_name, username)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        lines = []
        lines.append(f'[{timestamp}] 删除操作 - {message}')
        lines.append(f'  请求删除: {len(paths)} 个文件')
        lines.append(f'  成功: {len(deleted)} 个, 失败: {len(failed)} 个')

        if deleted:
            lines.append('  已删除:')
            for p in deleted:
                lines.append(f'    + {p}')

        if failed:
            lines.append('  失败:')
            for p in failed:
                lines.append(f'    - {p}')

        lines.append('')  # 空行分隔

        with open(log_path, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')

    except Exception as e:
        print(f'写入日志失败: {str(e)}')


def get_operation_logs(provider_name: str, username: str,
                       limit: int = 50) -> List[str]:
    """
    获取操作日志（最近N条记录）

    Args:
        provider_name: 网盘类型名称
        username: 用户名
        limit: 返回的最大行数

    Returns:
        日志行列表
    """
    try:
        log_path = _get_log_path(provider_name, username)

        if not os.path.exists(log_path):
            return []

        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 返回最后limit行
        return [line.rstrip('\n') for line in lines[-limit:]]

    except Exception as e:
        print(f'读取日志失败: {str(e)}')
        return []
