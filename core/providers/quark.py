"""
夸克网盘提供者实现（预留）
"""

from typing import List, Optional
from ..base_provider import BaseProvider, FileInfo


class QuarkProvider(BaseProvider):
    """夸克网盘提供者（预留实现）"""

    def __init__(self):
        super().__init__()

    @property
    def provider_name(self) -> str:
        return '夸克网盘'

    def login_with_password(self, username: str, password: str) -> dict:
        return {
            'success': False,
            'message': '夸克网盘支持即将推出',
            'user_info': None
        }

    def send_sms_code(self, phone: str) -> dict:
        return {
            'success': False,
            'message': '夸克网盘支持即将推出'
        }

    def login_with_sms(self, phone: str, sms_code: str) -> dict:
        return {
            'success': False,
            'message': '夸克网盘支持即将推出',
            'user_info': None
        }

    def list_files(self, path: str = '/') -> List[FileInfo]:
        return []

    def list_all_files(self, path: str = '/', recursive: bool = True) -> List[FileInfo]:
        return []

    def get_file_info(self, path: str) -> Optional[FileInfo]:
        return None

    def delete_files(self, paths: List[str]) -> dict:
        return {
            'success': False,
            'message': '夸克网盘支持即将推出',
            'deleted': [],
            'failed': paths
        }

    def get_quota(self) -> dict:
        return {'total': 0, 'used': 0, 'free': 0}
