"""
扫描结果缓存管理
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any

# 缓存目录
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')


def get_cache_key(provider_name: str, username: str) -> str:
    """生成缓存键（基于网盘类型和用户名）"""
    key_string = f"{provider_name}_{username}"
    return hashlib.md5(key_string.encode()).hexdigest()


def get_cache_path(cache_key: str) -> str:
    """获取缓存文件路径"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    return os.path.join(CACHE_DIR, f"{cache_key}.json")


def save_scan_cache(provider_name: str, username: str, scan_results: Dict[str, Any]) -> bool:
    """
    保存扫描结果到缓存

    Args:
        provider_name: 网盘类型名称
        username: 用户名
        scan_results: 扫描结果数据

    Returns:
        是否保存成功
    """
    try:
        cache_key = get_cache_key(provider_name, username)
        cache_path = get_cache_path(cache_key)

        cache_data = {
            'provider_name': provider_name,
            'username': username,
            'scan_time': datetime.now().isoformat(),
            'scan_results': scan_results
        }

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)

        print(f"扫描结果已缓存: {cache_path}")
        return True
    except Exception as e:
        print(f"保存缓存失败: {str(e)}")
        return False


def load_scan_cache(provider_name: str, username: str) -> Optional[Dict[str, Any]]:
    """
    加载扫描结果缓存

    Args:
        provider_name: 网盘类型名称
        username: 用户名

    Returns:
        缓存数据（包含 scan_time 和 scan_results），如果不存在则返回 None
    """
    try:
        cache_key = get_cache_key(provider_name, username)
        cache_path = get_cache_path(cache_key)

        if not os.path.exists(cache_path):
            return None

        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        # 验证缓存数据的用户名是否匹配
        if cache_data.get('username') != username:
            print(f"缓存用户名不匹配，将重新扫描")
            return None

        print(f"加载缓存成功: {cache_path}, 扫描时间: {cache_data.get('scan_time')}")
        return cache_data
    except Exception as e:
        print(f"加载缓存失败: {str(e)}")
        return None


def clear_scan_cache(provider_name: str, username: str) -> bool:
    """
    清除指定用户的扫描缓存

    Args:
        provider_name: 网盘类型名称
        username: 用户名

    Returns:
        是否清除成功
    """
    try:
        cache_key = get_cache_key(provider_name, username)
        cache_path = get_cache_path(cache_key)

        if os.path.exists(cache_path):
            os.remove(cache_path)
            print(f"缓存已清除: {cache_path}")
        return True
    except Exception as e:
        print(f"清除缓存失败: {str(e)}")
        return False


def invalidate_cache_paths(provider_name: str, username: str, deleted_paths: list) -> bool:
    """
    从缓存中移除已删除的文件路径

    Args:
        provider_name: 网盘类型名称
        username: 用户名
        deleted_paths: 已删除的文件路径列表

    Returns:
        是否更新成功
    """
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
            cache_data['scan_results'] = scan_results
            cache_data['last_updated'] = datetime.now().isoformat()

            cache_key = get_cache_key(provider_name, username)
            cache_path = get_cache_path(cache_key)

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2, default=str)

            print(f"缓存已更新，移除了 {len(deleted_paths)} 个已删除路径")

        return True
    except Exception as e:
        print(f"更新缓存失败: {str(e)}")
        return False


def get_cache_info(provider_name: str, username: str) -> Optional[Dict[str, Any]]:
    """
    获取缓存信息（不加载完整数据）

    Returns:
        缓存信息（扫描时间等），如果不存在则返回 None
    """
    try:
        cache_key = get_cache_key(provider_name, username)
        cache_path = get_cache_path(cache_key)

        if not os.path.exists(cache_path):
            return None

        with open(cache_path, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        return {
            'exists': True,
            'scan_time': cache_data.get('scan_time'),
            'last_updated': cache_data.get('last_updated'),
            'username': cache_data.get('username')
        }
    except Exception:
        return None
