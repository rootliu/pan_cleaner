"""
Supabase 客户端 - 使用 postgrest 直接访问数据库
避免完整 supabase SDK 的重量级依赖 (storage3/pyiceberg)
"""

import os
from postgrest import SyncPostgrestClient


class SupabaseDB:
    """轻量级 Supabase 数据库客户端，仅封装 PostgREST"""

    def __init__(self, url: str, key: str):
        rest_url = f"{url.rstrip('/')}/rest/v1"
        self._postgrest = SyncPostgrestClient(
            rest_url,
            headers={
                'apikey': key,
                'Authorization': f'Bearer {key}'
            }
        )

    def table(self, table_name: str):
        return self._postgrest.from_(table_name)


_client: SupabaseDB = None


def get_supabase() -> SupabaseDB:
    """
    获取 Supabase 数据库客户端实例
    单例模式，warm start 时复用连接
    """
    global _client
    if _client is None:
        url = os.environ.get('SUPABASE_URL')
        key = os.environ.get('SUPABASE_KEY')
        if not url or not key:
            raise RuntimeError(
                'SUPABASE_URL 和 SUPABASE_KEY 环境变量未设置'
            )
        _client = SupabaseDB(url, key)
    return _client
