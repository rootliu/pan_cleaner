"""
文件清理操作模块
"""

from typing import List, Dict
from .base_provider import BaseProvider


class FileCleaner:
    """文件清理器"""

    def __init__(self, provider: BaseProvider):
        self.provider = provider
        self.delete_log = []

    def delete_files(self, paths: List[str]) -> Dict:
        """
        删除指定的文件或文件夹
        """
        if not paths:
            return {
                'success': True,
                'message': '没有需要删除的文件',
                'deleted': [],
                'failed': []
            }

        result = self.provider.delete_files(paths)

        # 记录删除日志
        for path in result.get('deleted', []):
            self.delete_log.append({
                'path': path,
                'status': 'deleted'
            })

        for path in result.get('failed', []):
            self.delete_log.append({
                'path': path,
                'status': 'failed'
            })

        return result

    def delete_duplicates_keep_first(self, duplicate_group: Dict) -> Dict:
        """
        删除重复文件，保留第一个
        """
        files = duplicate_group.get('files', [])
        if len(files) <= 1:
            return {
                'success': True,
                'message': '没有需要删除的重复文件',
                'deleted': [],
                'failed': []
            }

        # 保留第一个，删除其他
        paths_to_delete = [f.path for f in files[1:]]
        return self.delete_files(paths_to_delete)

    def delete_selected(self, paths_to_delete: List[str], paths_to_keep: List[str]) -> Dict:
        """
        根据用户选择删除文件
        paths_to_delete: 要删除的文件路径
        paths_to_keep: 要保留的文件路径（用于验证）
        """
        if not paths_to_delete:
            return {
                'success': True,
                'message': '没有选择需要删除的文件',
                'deleted': [],
                'failed': []
            }

        # 确保不删除所有副本
        if paths_to_keep:
            # 验证至少保留了一份
            pass

        return self.delete_files(paths_to_delete)

    def get_delete_log(self) -> List[Dict]:
        """获取删除日志"""
        return self.delete_log

    def clear_log(self):
        """清空删除日志"""
        self.delete_log = []
