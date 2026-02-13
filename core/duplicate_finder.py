"""
重复文件和文件夹检测模块
"""

import logging
from typing import List, Dict, Tuple
from collections import defaultdict
import hashlib
from .base_provider import FileInfo, FolderInfo

logger = logging.getLogger(__name__)


class DuplicateFinder:
    """重复文件和文件夹检测器"""

    def __init__(self, files: List[FileInfo]):
        self.files = files
        self.folders = [f for f in files if f.is_dir]
        self.regular_files = [f for f in files if not f.is_dir]
        self._cached_dup_files = None
        self._cached_dup_folders = None

    def find_duplicate_files(self) -> List[Dict]:
        """
        查找重复文件
        返回格式: [
            {
                'hash': 'md5值',
                'size': 文件大小,
                'files': [FileInfo, FileInfo, ...],  # 重复的文件列表
                'count': 重复数量,
                'wasted_space': 浪费的空间（除了保留一份外）
            },
            ...
        ]
        """
        if self._cached_dup_files is not None:
            return self._cached_dup_files

        # 第一步：按文件大小分组（相同大小才可能重复）
        size_groups = defaultdict(list)
        for file in self.regular_files:
            if file.size > 0:  # 忽略空文件
                size_groups[file.size].append(file)

        # 第二步：对相同大小的文件，按MD5分组
        duplicates = []

        for size, files in size_groups.items():
            if len(files) < 2:
                continue

            # 按MD5分组（跳过没有MD5的文件，无法可靠判断是否重复）
            hash_groups = defaultdict(list)
            for file in files:
                if file.md5:
                    hash_groups[file.md5].append(file)
                else:
                    logger.debug(f'跳过无MD5文件: {file.path}')

            # 找出重复的组
            for file_hash, group_files in hash_groups.items():
                if len(group_files) >= 2:
                    duplicates.append({
                        'hash': file_hash,
                        'size': size,
                        'files': group_files,
                        'count': len(group_files),
                        'wasted_space': size * (len(group_files) - 1)
                    })

        # 按浪费空间排序（从大到小）
        duplicates.sort(key=lambda x: x['wasted_space'], reverse=True)

        self._cached_dup_files = duplicates
        return duplicates

    def find_duplicate_folders(self) -> List[Dict]:
        """
        查找重复文件夹
        通过比较文件夹内容的哈希签名来检测
        返回格式: [
            {
                'content_hash': '内容哈希',
                'folders': [FolderInfo, FolderInfo, ...],
                'count': 重复数量,
                'wasted_space': 浪费的空间
            },
            ...
        ]
        """
        if self._cached_dup_folders is not None:
            return self._cached_dup_folders

        # 计算每个文件夹的内容签名
        folder_signatures = {}

        for folder in self.folders:
            signature = self._calculate_folder_signature(folder.path)
            if signature:
                folder_signatures[folder.path] = {
                    'signature': signature,
                    'folder': folder
                }

        # 按签名分组
        signature_groups = defaultdict(list)
        for path, data in folder_signatures.items():
            signature_groups[data['signature']].append(data['folder'])

        # 找出重复的文件夹
        duplicates = []

        for signature, folders in signature_groups.items():
            if len(folders) >= 2:
                # 计算文件夹大小
                total_size = sum(self._get_folder_size(f.path) for f in folders)
                avg_size = total_size // len(folders) if folders else 0

                duplicates.append({
                    'content_hash': signature,
                    'folders': folders,
                    'count': len(folders),
                    'wasted_space': avg_size * (len(folders) - 1),
                    'size': avg_size
                })

        # 按浪费空间排序
        duplicates.sort(key=lambda x: x['wasted_space'], reverse=True)

        self._cached_dup_folders = duplicates
        return duplicates

    def _calculate_folder_signature(self, folder_path: str) -> str:
        """计算文件夹内容签名"""
        # 获取文件夹内的所有文件
        folder_files = []
        for file in self.regular_files:
            if file.path.startswith(folder_path + '/'):
                # 使用相对路径和文件特征生成签名
                relative_path = file.path[len(folder_path) + 1:]
                folder_files.append(f"{relative_path}:{file.size}:{file.md5 or ''}")

        if not folder_files:
            return ''

        # 排序后计算哈希
        folder_files.sort()
        content = '\n'.join(folder_files)
        return hashlib.md5(content.encode()).hexdigest()

    def _get_folder_size(self, folder_path: str) -> int:
        """计算文件夹大小"""
        total_size = 0
        for file in self.regular_files:
            if file.path.startswith(folder_path + '/'):
                total_size += file.size
        return total_size

    def get_total_wasted_space(self) -> int:
        """获取总共可节省的空间（使用缓存结果）"""
        file_duplicates = self.find_duplicate_files()
        folder_duplicates = self.find_duplicate_folders()

        total = sum(d['wasted_space'] for d in file_duplicates)
        total += sum(d['wasted_space'] for d in folder_duplicates)

        return total

    def get_summary(self) -> Dict:
        """获取重复检测摘要（使用缓存结果）"""
        file_duplicates = self.find_duplicate_files()
        folder_duplicates = self.find_duplicate_folders()

        return {
            'duplicate_file_groups': len(file_duplicates),
            'duplicate_files_total': sum(d['count'] for d in file_duplicates),
            'duplicate_folder_groups': len(folder_duplicates),
            'duplicate_folders_total': sum(d['count'] for d in folder_duplicates),
            'total_wasted_space': self.get_total_wasted_space()
        }
