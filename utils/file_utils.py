"""
文件工具函数
"""


def format_size(size_bytes: int) -> str:
    """格式化文件大小显示"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def format_count(count: int) -> str:
    """格式化数量显示"""
    if count < 1000:
        return str(count)
    elif count < 1000000:
        return f"{count / 1000:.1f}K"
    else:
        return f"{count / 1000000:.1f}M"


def get_file_icon(extension: str) -> str:
    """根据扩展名返回图标类名"""
    ext = extension.lower() if extension else ''

    icons = {
        # 视频
        'mp4': 'fa-file-video',
        'mkv': 'fa-file-video',
        'avi': 'fa-file-video',
        'mov': 'fa-file-video',
        'wmv': 'fa-file-video',
        'flv': 'fa-file-video',
        # 图片
        'jpg': 'fa-file-image',
        'jpeg': 'fa-file-image',
        'png': 'fa-file-image',
        'gif': 'fa-file-image',
        'bmp': 'fa-file-image',
        'webp': 'fa-file-image',
        # 音频
        'mp3': 'fa-file-audio',
        'wav': 'fa-file-audio',
        'flac': 'fa-file-audio',
        'aac': 'fa-file-audio',
        # 文档
        'pdf': 'fa-file-pdf',
        'doc': 'fa-file-word',
        'docx': 'fa-file-word',
        'xls': 'fa-file-excel',
        'xlsx': 'fa-file-excel',
        'ppt': 'fa-file-powerpoint',
        'pptx': 'fa-file-powerpoint',
        'txt': 'fa-file-alt',
        # 压缩包
        'zip': 'fa-file-archive',
        'rar': 'fa-file-archive',
        '7z': 'fa-file-archive',
        'tar': 'fa-file-archive',
        'gz': 'fa-file-archive',
        # 可执行文件
        'exe': 'fa-cog',
        'msi': 'fa-cog',
        'apk': 'fa-android',
        'ipa': 'fa-apple',
        'dmg': 'fa-apple',
        'deb': 'fa-linux',
        'rpm': 'fa-linux',
    }

    return icons.get(ext, 'fa-file')


def truncate_path(path: str, max_length: int = 50) -> str:
    """截断过长的路径"""
    if len(path) <= max_length:
        return path

    # 保留开头和结尾
    start_len = max_length // 3
    end_len = max_length - start_len - 3

    return path[:start_len] + '...' + path[-end_len:]
