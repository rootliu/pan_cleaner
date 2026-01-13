"""
百度网盘提供者实现
"""

import requests
import time
import hashlib
from typing import List, Optional
from datetime import datetime
from ..base_provider import BaseProvider, FileInfo, FolderInfo


class BaiduProvider(BaseProvider):
    """百度网盘提供者"""

    # 百度网盘API接口
    API_BASE = 'https://pan.baidu.com'

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.access_token = None
        self.bdstoken = None

    @property
    def provider_name(self) -> str:
        return '百度网盘'

    def login_with_password(self, username: str, password: str) -> dict:
        """
        使用用户名密码登录
        注意：百度网盘的直接密码登录需要处理验证码等复杂逻辑
        这里提供基础框架，实际使用可能需要cookie或OAuth方式
        """
        try:
            # 百度网盘登录较为复杂，涉及多步验证
            # 推荐使用cookie方式或者百度开放平台OAuth
            # 这里预留接口，返回提示信息
            return {
                'success': False,
                'message': '密码登录暂不支持，请使用Cookie登录或手机验证码登录',
                'user_info': None
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'登录失败: {str(e)}',
                'user_info': None
            }

    def login_with_cookie(self, cookie_string: str) -> dict:
        """
        使用Cookie登录（推荐方式）
        用户可以从浏览器获取登录后的Cookie
        """
        try:
            # 解析cookie字符串
            cookies = {}
            for item in cookie_string.split(';'):
                item = item.strip()
                if '=' in item:
                    key, value = item.split('=', 1)
                    cookies[key.strip()] = value.strip()

            # 设置cookie
            for key, value in cookies.items():
                self.session.cookies.set(key, value)

            # 验证登录状态
            response = self.session.get(f'{self.API_BASE}/api/quota')
            if response.status_code == 200:
                data = response.json()
                if data.get('errno') == 0:
                    self.is_logged_in = True

                    # 获取bdstoken（用于删除等操作）
                    self._get_bdstoken()

                    # 获取用户信息
                    user_response = self.session.get(f'{self.API_BASE}/rest/2.0/xpan/nas?method=uinfo')
                    user_data = user_response.json() if user_response.status_code == 200 else {}

                    self.user_info = {
                        'quota_total': data.get('total', 0),
                        'quota_used': data.get('used', 0),
                        'username': user_data.get('baidu_name', '未知用户'),
                        'vip_type': user_data.get('vip_type', 0)
                    }

                    return {
                        'success': True,
                        'message': '登录成功',
                        'user_info': self.user_info
                    }

            return {
                'success': False,
                'message': 'Cookie无效或已过期',
                'user_info': None
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'登录失败: {str(e)}',
                'user_info': None
            }

    def _get_bdstoken(self):
        """获取bdstoken，用于删除等需要验证的操作"""
        try:
            import re
            # 方法1: 从主页获取
            response = self.session.get(f'{self.API_BASE}/disk/home')
            if response.status_code == 200:
                # 尝试从页面中提取bdstoken
                match = re.search(r'"bdstoken"\s*:\s*"([^"]+)"', response.text)
                if match:
                    self.bdstoken = match.group(1)
                    return

                match = re.search(r'bdstoken\s*=\s*["\']([^"\']+)["\']', response.text)
                if match:
                    self.bdstoken = match.group(1)
                    return

            # 方法2: 从API获取
            response = self.session.get(f'{self.API_BASE}/api/gettemplatevariable?fields=[%22bdstoken%22]')
            if response.status_code == 200:
                data = response.json()
                if data.get('errno') == 0 and data.get('result'):
                    self.bdstoken = data['result'].get('bdstoken', '')
        except Exception as e:
            print(f'获取bdstoken失败: {str(e)}')

    def send_sms_code(self, phone: str) -> dict:
        """发送短信验证码"""
        # 百度网盘短信验证需要特殊处理
        return {
            'success': False,
            'message': '短信验证码功能暂未实现，请使用Cookie登录'
        }

    def login_with_sms(self, phone: str, sms_code: str) -> dict:
        """使用手机号和验证码登录"""
        return {
            'success': False,
            'message': '短信验证码登录暂未实现，请使用Cookie登录',
            'user_info': None
        }

    def list_files(self, path: str = '/') -> List[FileInfo]:
        """列出指定目录下的文件"""
        if not self.is_logged_in:
            return []

        try:
            files = []
            page = 1
            has_more = True

            while has_more:
                params = {
                    'dir': path,
                    'order': 'name',
                    'desc': 0,
                    'start': (page - 1) * 1000,
                    'limit': 1000,
                    'web': 1,
                    'folder': 0,
                    'showempty': 1
                }

                response = self.session.get(f'{self.API_BASE}/api/list', params=params)

                if response.status_code != 200:
                    break

                data = response.json()

                if data.get('errno') != 0:
                    break

                file_list = data.get('list', [])

                for item in file_list:
                    file_info = FileInfo(
                        path=item.get('path', ''),
                        name=item.get('server_filename', ''),
                        size=item.get('size', 0),
                        is_dir=item.get('isdir', 0) == 1,
                        md5=item.get('md5', None) if item.get('isdir', 0) == 0 else None,
                        created_time=datetime.fromtimestamp(item.get('server_ctime', 0)) if item.get('server_ctime') else None,
                        modified_time=datetime.fromtimestamp(item.get('server_mtime', 0)) if item.get('server_mtime') else None
                    )
                    files.append(file_info)

                has_more = len(file_list) == 1000
                page += 1

            return files

        except Exception as e:
            print(f'列出文件失败: {str(e)}')
            return []

    def list_all_files(self, path: str = '/', recursive: bool = True) -> List[FileInfo]:
        """递归列出所有文件"""
        all_files = []

        files = self.list_files(path)

        for file in files:
            all_files.append(file)
            if recursive and file.is_dir:
                sub_files = self.list_all_files(file.path, recursive=True)
                all_files.extend(sub_files)

        return all_files

    def get_file_info(self, path: str) -> Optional[FileInfo]:
        """获取单个文件的详细信息"""
        if not self.is_logged_in:
            return None

        try:
            params = {
                'path': path,
                'web': 1
            }

            response = self.session.get(f'{self.API_BASE}/api/filemetas', params=params)

            if response.status_code != 200:
                return None

            data = response.json()

            if data.get('errno') != 0 or not data.get('info'):
                return None

            item = data['info'][0]

            return FileInfo(
                path=item.get('path', ''),
                name=item.get('server_filename', ''),
                size=item.get('size', 0),
                is_dir=item.get('isdir', 0) == 1,
                md5=item.get('md5', None),
                created_time=datetime.fromtimestamp(item.get('server_ctime', 0)) if item.get('server_ctime') else None,
                modified_time=datetime.fromtimestamp(item.get('server_mtime', 0)) if item.get('server_mtime') else None
            )

        except Exception as e:
            print(f'获取文件信息失败: {str(e)}')
            return None

    def delete_files(self, paths: List[str]) -> dict:
        """删除文件或文件夹（分批删除以避免触发反作弊）"""
        if not self.is_logged_in:
            return {
                'success': False,
                'message': '未登录',
                'deleted': [],
                'failed': paths
            }

        # 分批删除，每批最多1个文件，避免触发反作弊
        batch_size = 1
        all_deleted = []
        all_failed = []

        for i in range(0, len(paths), batch_size):
            batch = paths[i:i + batch_size]
            result = self._delete_batch(batch)

            all_deleted.extend(result.get('deleted', []))
            all_failed.extend(result.get('failed', []))

            # 如果遇到反作弊错误，停止继续删除
            if not result.get('success') and '反作弊' in result.get('message', ''):
                all_failed.extend(paths[i + batch_size:])
                return {
                    'success': False,
                    'message': result.get('message'),
                    'deleted': all_deleted,
                    'failed': all_failed
                }

            # 批次之间等待1秒，避免请求过快
            if i + batch_size < len(paths):
                time.sleep(1)

        if all_failed:
            return {
                'success': False,
                'message': f'部分删除失败: 成功{len(all_deleted)}个，失败{len(all_failed)}个',
                'deleted': all_deleted,
                'failed': all_failed
            }

        return {
            'success': True,
            'message': f'删除成功: {len(all_deleted)}个文件',
            'deleted': all_deleted,
            'failed': []
        }

    def _delete_batch(self, paths: List[str]) -> dict:
        """删除一批文件"""
        try:
            import json

            # 确保有bdstoken
            if not self.bdstoken:
                self._get_bdstoken()

            # 构建删除请求
            url = f'{self.API_BASE}/api/filemanager?opera=delete'
            if self.bdstoken:
                url += f'&bdstoken={self.bdstoken}'

            # filelist 需要是正确格式的JSON数组
            filelist_json = json.dumps(paths, ensure_ascii=False)

            # 使用 form data 格式
            # async=2 表示使用异步删除模式，可能更不容易触发反作弊
            data = {
                'filelist': filelist_json,
                'async': '2',
                'channel': 'chunlei',
                'web': '1',
                'app_id': '250528',
                'clienttype': '0',
                'newVerify': '1'
            }

            # 添加必要的请求头
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': f'{self.API_BASE}/disk/home',
                'Origin': self.API_BASE,
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'X-Requested-With': 'XMLHttpRequest'
            }

            response = self.session.post(url, data=data, headers=headers)

            if response.status_code != 200:
                return {
                    'success': False,
                    'message': f'请求失败: HTTP {response.status_code}',
                    'deleted': [],
                    'failed': paths
                }

            result = response.json()
            errno = result.get('errno', -1)

            # 错误码说明
            error_messages = {
                0: '删除成功',
                -1: '参数错误',
                -3: '文件不存在',
                -6: '身份验证失败，请重新登录',
                -7: '文件路径非法或包含特殊字符',
                -8: '目录满了',
                -9: '空间不足',
                -10: '文件夹限制',
                -70: '请求格式错误',
                2: '参数错误',
                12: '批量处理失败',
                -21: '功能暂时不可用',
                111: '有其他用户操作，请稍后重试',
                -32: '文件已存在',
                -33: '文件不存在',
                132: '请求过于频繁或需要验证，请在网页端操作或稍后重试',
                133: '文件被锁定，无法删除',
                31034: '命中反作弊，请在网页端手动删除',
                31045: '操作太频繁，请稍后重试',
            }

            # 打印调试信息
            print(f'删除API响应: errno={errno}, errmsg={result.get("errmsg", "")}, result={result}')

            if errno == 0:
                return {
                    'success': True,
                    'message': '删除成功',
                    'deleted': paths,
                    'failed': []
                }
            else:
                error_msg = result.get('errmsg') or error_messages.get(errno, f'未知错误(errno={errno})')
                return {
                    'success': False,
                    'message': f'删除失败: {error_msg}',
                    'deleted': [],
                    'failed': paths
                }

        except Exception as e:
            return {
                'success': False,
                'message': f'删除失败: {str(e)}',
                'deleted': [],
                'failed': paths
            }

    def get_quota(self) -> dict:
        """获取网盘容量信息"""
        if not self.is_logged_in:
            return {'total': 0, 'used': 0, 'free': 0}

        try:
            response = self.session.get(f'{self.API_BASE}/api/quota')

            if response.status_code != 200:
                return {'total': 0, 'used': 0, 'free': 0}

            data = response.json()

            if data.get('errno') == 0:
                total = data.get('total', 0)
                used = data.get('used', 0)
                return {
                    'total': total,
                    'used': used,
                    'free': total - used
                }

            return {'total': 0, 'used': 0, 'free': 0}

        except Exception as e:
            print(f'获取容量信息失败: {str(e)}')
            return {'total': 0, 'used': 0, 'free': 0}
