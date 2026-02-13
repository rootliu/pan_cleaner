"""
文件分析统计模块
"""

from typing import List, Dict
from collections import defaultdict
from .base_provider import FileInfo
from config import FILE_CATEGORIES, LARGE_FILE_THRESHOLD, EXECUTABLE_EXTENSIONS, CATEGORY_NAMES


class FileAnalyzer:
    """文件分析器"""

    def __init__(self, files: List[FileInfo]):
        self.files = files
        self.regular_files = [f for f in files if not f.is_dir]

    def get_category(self, extension: str) -> str:
        """获取文件类型分类"""
        ext = extension.lower() if extension else ''
        for category, extensions in FILE_CATEGORIES.items():
            if ext in extensions:
                return category
        return 'other'

    def analyze_by_category(self) -> Dict:
        """
        按文件类型分类统计
        返回: {
            'video': {'count': 10, 'size': 1024000, 'files': [...]},
            'image': {'count': 20, 'size': 512000, 'files': [...]},
            ...
        }
        """
        categories = defaultdict(lambda: {'count': 0, 'size': 0, 'files': []})

        for file in self.regular_files:
            category = self.get_category(file.extension)
            categories[category]['count'] += 1
            categories[category]['size'] += file.size
            categories[category]['files'].append(file)

        # 转换为普通字典并添加中文名称
        result = {}
        for cat, data in categories.items():
            result[cat] = {
                'name': CATEGORY_NAMES.get(cat, cat),
                'count': data['count'],
                'size': data['size'],
                'files': data['files']
            }

        return result

    def find_large_files(self, threshold: int = LARGE_FILE_THRESHOLD) -> Dict:
        """
        查找大文件，按类型分组
        返回: {
            'video': [FileInfo, FileInfo, ...],
            'archive': [...],
            'disk_image': [...],
            'other': [...]
        }
        """
        large_files = defaultdict(list)

        for file in self.regular_files:
            if file.size >= threshold:
                category = self.get_category(file.extension)
                large_files[category].append(file)

        # 每个分类内按大小排序
        for category in large_files:
            large_files[category].sort(key=lambda x: x.size, reverse=True)

        return dict(large_files)

    def find_executable_files(self) -> List[FileInfo]:
        """
        查找可执行文件
        """
        executables = []

        for file in self.regular_files:
            ext = file.extension.lower() if file.extension else ''
            if ext in EXECUTABLE_EXTENSIONS:
                executables.append(file)

        # 按大小排序
        executables.sort(key=lambda x: x.size, reverse=True)

        return executables

    def get_top_largest_files(self, n: int = 50) -> List[FileInfo]:
        """获取最大的N个文件"""
        sorted_files = sorted(self.regular_files, key=lambda x: x.size, reverse=True)
        return sorted_files[:n]

    def get_statistics(self) -> Dict:
        """
        获取整体统计信息
        """
        total_size = sum(f.size for f in self.regular_files)
        total_files = len(self.regular_files)
        total_folders = len([f for f in self.files if f.is_dir])

        category_stats = self.analyze_by_category()
        large_files = self.find_large_files()
        executables = self.find_executable_files()

        # 计算大文件统计
        large_file_count = sum(len(files) for files in large_files.values())
        large_file_size = sum(sum(f.size for f in files) for files in large_files.values())

        return {
            'total_files': total_files,
            'total_folders': total_folders,
            'total_size': total_size,
            'category_stats': {
                cat: {
                    'name': data['name'],
                    'count': data['count'],
                    'size': data['size']
                } for cat, data in category_stats.items()
            },
            'large_files': {
                'count': large_file_count,
                'size': large_file_size,
                'by_category': {
                    cat: {
                        'count': len(files),
                        'size': sum(f.size for f in files)
                    } for cat, files in large_files.items()
                }
            },
            'executables': {
                'count': len(executables),
                'size': sum(f.size for f in executables)
            }
        }
