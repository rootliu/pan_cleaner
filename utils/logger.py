"""
操作日志记录模块 - Supabase 后端
"""

from datetime import datetime
from typing import List, Dict, Any
from .supabase_client import get_supabase


def log_delete_operation(provider_name: str, username: str, paths: List[str],
                         deleted: List[str], failed: List[str],
                         message: str = ''):
    """
    记录删除操作日志到 Supabase delete_logs 表

    Args:
        provider_name: 网盘类型名称
        username: 用户名
        paths: 请求删除的路径列表
        deleted: 成功删除的路径列表
        failed: 删除失败的路径列表
        message: 操作结果消息
    """
    try:
        supabase = get_supabase()
        data = {
            'provider_name': provider_name,
            'username': username,
            'paths': paths,
            'deleted': deleted,
            'failed': failed,
            'message': message,
            'created_at': datetime.now().isoformat()
        }
        supabase.table('delete_logs').insert(data).execute()
    except Exception as e:
        print(f'写入日志失败: {str(e)}')


def get_operation_logs(provider_name: str, username: str,
                       limit: int = 50) -> List[Dict[str, Any]]:
    """
    获取操作日志（最近N条记录）

    Args:
        provider_name: 网盘类型名称
        username: 用户名
        limit: 返回的最大条数

    Returns:
        日志记录列表
    """
    try:
        supabase = get_supabase()
        result = supabase.table('delete_logs').select('*').eq(
            'provider_name', provider_name
        ).eq('username', username).order(
            'created_at', desc=True
        ).limit(limit).execute()

        return result.data if result.data else []
    except Exception as e:
        print(f'读取日志失败: {str(e)}')
        return []
