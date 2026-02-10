"""
扫描结果缓存管理 - Supabase 后端
"""

from datetime import datetime
from typing import Optional, Dict, Any
from .supabase_client import get_supabase


def save_scan_cache(provider_name: str, username: str, scan_results: Dict[str, Any]) -> bool:
    """保存扫描结果到 Supabase scan_cache 表"""
    try:
        supabase = get_supabase()
        data = {
            'provider_name': provider_name,
            'username': username,
            'scan_results': scan_results,
            'scan_time': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat()
        }
        supabase.table('scan_cache').upsert(
            data,
            on_conflict='provider_name,username'
        ).execute()
        return True
    except Exception as e:
        print(f"保存缓存失败: {str(e)}")
        return False


def load_scan_cache(provider_name: str, username: str) -> Optional[Dict[str, Any]]:
    """加载扫描结果缓存"""
    try:
        supabase = get_supabase()
        result = supabase.table('scan_cache').select('*').eq(
            'provider_name', provider_name
        ).eq('username', username).execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            return {
                'provider_name': row['provider_name'],
                'username': row['username'],
                'scan_time': row['scan_time'],
                'last_updated': row.get('last_updated'),
                'scan_results': row['scan_results']
            }
        return None
    except Exception as e:
        print(f"加载缓存失败: {str(e)}")
        return None


def clear_scan_cache(provider_name: str, username: str) -> bool:
    """清除指定用户的扫描缓存"""
    try:
        supabase = get_supabase()
        supabase.table('scan_cache').delete().eq(
            'provider_name', provider_name
        ).eq('username', username).execute()
        return True
    except Exception as e:
        print(f"清除缓存失败: {str(e)}")
        return False


def invalidate_cache_paths(provider_name: str, username: str, deleted_paths: list) -> bool:
    """从缓存中移除已删除的文件路径"""
    try:
        cache_data = load_scan_cache(provider_name, username)
        if not cache_data:
            return False

        scan_results = cache_data.get('scan_results', {})
        deleted_set = set(deleted_paths)
        updated = False

        # 更新重复文件列表
        if 'duplicate_files' in scan_results:
            new_dup_files = []
            for group in scan_results['duplicate_files']:
                new_files = [f for f in group.get('files', []) if f.get('path') not in deleted_set]
                if len(new_files) > 1:
                    group['files'] = new_files
                    group['count'] = len(new_files)
                    new_dup_files.append(group)
                updated = True
            scan_results['duplicate_files'] = new_dup_files

        # 更新重复文件夹列表
        if 'duplicate_folders' in scan_results:
            new_dup_folders = []
            for group in scan_results['duplicate_folders']:
                new_folders = [f for f in group.get('folders', []) if f.get('path') not in deleted_set]
                if len(new_folders) > 1:
                    group['folders'] = new_folders
                    group['count'] = len(new_folders)
                    new_dup_folders.append(group)
                updated = True
            scan_results['duplicate_folders'] = new_dup_folders

        # 更新大文件列表
        if 'large_files' in scan_results:
            for category in scan_results['large_files']:
                scan_results['large_files'][category] = [
                    f for f in scan_results['large_files'][category]
                    if f.get('path') not in deleted_set
                ]
            updated = True

        # 更新可执行文件列表
        if 'executables' in scan_results:
            scan_results['executables'] = [
                f for f in scan_results['executables']
                if f.get('path') not in deleted_set
            ]
            updated = True

        if updated:
            supabase = get_supabase()
            supabase.table('scan_cache').update({
                'scan_results': scan_results,
                'last_updated': datetime.now().isoformat()
            }).eq('provider_name', provider_name).eq('username', username).execute()

        return True
    except Exception as e:
        print(f"更新缓存失败: {str(e)}")
        return False


def get_cache_info(provider_name: str, username: str) -> Optional[Dict[str, Any]]:
    """获取缓存信息（不加载完整数据）"""
    try:
        supabase = get_supabase()
        result = supabase.table('scan_cache').select(
            'scan_time, last_updated, username'
        ).eq('provider_name', provider_name).eq('username', username).execute()

        if result.data and len(result.data) > 0:
            row = result.data[0]
            return {
                'exists': True,
                'scan_time': row.get('scan_time'),
                'last_updated': row.get('last_updated'),
                'username': row.get('username')
            }
        return None
    except Exception:
        return None
