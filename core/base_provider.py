"""
网盘提供者抽象基类
定义所有网盘提供者必须实现的接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class FileInfo:
    """文件信息"""
    path: str                    # 文件完整路径
    name: str                    # 文件名
    size: int                    # 文件大小（字节）
    is_dir: bool                 # 是否是目录
    md5: Optional[str] = None    # 文件MD5（网盘通常提供）
    created_time: Optional[datetime] = None   # 创建时间
    modified_time: Optional[datetime] = None  # 修改时间
    extension: Optional[str] = None           # 文件扩展名

    def __post_init__(self):
        if not self.is_dir and self.extension is None:
            # 自动提取扩展名
            if '.' in self.name:
                self.extension = self.name.rsplit('.', 1)[-1].lower()
            else:
                self.extension = ''


@dataclass
class FolderInfo:
    """文件夹信息"""
    path: str                    # 文件夹路径
    name: str                    # 文件夹名
    total_size: int              # 总大小
    file_count: int              # 文件数量
    content_hash: Optional[str] = None  # 内容哈希（用于检测重复文件夹）


@dataclass
class LoginCredentials:
    """登录凭证"""
    provider_type: str           # 网盘类型: baidu, aliyun, quark
    username: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    sms_code: Optional[str] = None


class BaseProvider(ABC):
    """网盘提供者抽象基类"""

    def __init__(self):
        self.is_logged_in = False
        self.user_info = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """返回提供者名称"""
        pass

    @abstractmethod
    def login_with_password(self, username: str, password: str) -> dict:
        """
        使用用户名密码登录
        返回: {'success': bool, 'message': str, 'user_info': dict}
        """
        pass

    @abstractmethod
    def send_sms_code(self, phone: str) -> dict:
        """
        发送短信验证码
        返回: {'success': bool, 'message': str}
        """
        pass

    @abstractmethod
    def login_with_sms(self, phone: str, sms_code: str) -> dict:
        """
        使用手机号和验证码登录
        返回: {'success': bool, 'message': str, 'user_info': dict}
        """
        pass

    @abstractmethod
    def list_files(self, path: str = '/') -> List[FileInfo]:
        """
        列出指定目录下的所有文件和文件夹
        """
        pass

    @abstractmethod
    def list_all_files(self, path: str = '/', recursive: bool = True) -> List[FileInfo]:
        """
        递归列出所有文件
        """
        pass

    @abstractmethod
    def get_file_info(self, path: str) -> Optional[FileInfo]:
        """
        获取单个文件的详细信息
        """
        pass

    @abstractmethod
    def delete_files(self, paths: List[str]) -> dict:
        """
        删除文件或文件夹
        返回: {'success': bool, 'message': str, 'deleted': List[str], 'failed': List[str]}
        """
        pass

    @abstractmethod
    def get_quota(self) -> dict:
        """
        获取网盘容量信息
        返回: {'total': int, 'used': int, 'free': int}
        """
        pass

    def logout(self):
        """登出"""
        self.is_logged_in = False
        self.user_info = None
