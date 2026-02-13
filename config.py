"""
网盘文件清理工具 - 配置文件
"""

import logging
import os

# 大文件阈值（100MB）
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024

# 文件类型分类
FILE_CATEGORIES = {
    'video': ['mp4', 'mkv', 'avi', 'mov', 'wmv', 'flv', 'webm', 'rm', 'rmvb', 'm4v', '3gp'],
    'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'ico', 'tiff', 'psd', 'raw'],
    'audio': ['mp3', 'wav', 'flac', 'aac', 'm4a', 'ogg', 'wma', 'ape', 'alac'],
    'document': ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'md', 'rtf', 'odt', 'ods', 'odp'],
    'archive': ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'xz', 'cab'],
    'executable': ['exe', 'msi', 'apk', 'ipa', 'dmg', 'deb', 'rpm', 'pkg', 'bat', 'cmd', 'sh', 'app'],
    'disk_image': ['iso', 'img', 'vmdk', 'vdi', 'vhd', 'bin', 'cue'],
}

# 可执行文件扩展名（单独列出）
EXECUTABLE_EXTENSIONS = ['exe', 'msi', 'apk', 'ipa', 'dmg', 'deb', 'rpm', 'pkg', 'bat', 'cmd', 'sh', 'app']

# 文件类型中文名称
CATEGORY_NAMES = {
    'video': '视频',
    'image': '图片',
    'audio': '音频',
    'document': '文档',
    'archive': '压缩包',
    'executable': '可执行文件',
    'disk_image': '磁盘镜像',
    'other': '其他',
}

# 网盘提供者类型
PROVIDER_TYPES = {
    'baidu': '百度网盘',
    'aliyun': '阿里云盘',
    'quark': '夸克网盘',
}

# Flask 配置
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or (
        'pan-cleaner-dev-key-change-me'
        if not os.environ.get('VERCEL')
        else None
    )
    if SECRET_KEY is None:
        raise RuntimeError('生产环境必须设置 SECRET_KEY 环境变量')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('VERCEL', '') != ''


# 配置日志
logging.basicConfig(
    level=logging.DEBUG if not os.environ.get('VERCEL') else logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
