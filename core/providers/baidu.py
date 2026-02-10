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

    # 删除操作必需的Cookie字段
    REQUIRED_COOKIES_FOR_DELETE = ['BDUSS', 'STOKEN']
    # 建议包含的Cookie字段（提高成功率）
    RECOMMENDED_COOKIES = ['BDUSS', 'STOKEN', 'BDCLND', 'BAIDUID', 'PANWEB', 'BDUSS_BFESS', 'STOKEN_BFESS']

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

            # 检查关键Cookie字段
            missing_required = [k for k in self.REQUIRED_COOKIES_FOR_DELETE if k not in cookies]
            missing_recommended = [k for k in self.RECOMMENDED_COOKIES if k not in cookies]

            if missing_required:
                print(f'[WARNING] Cookie缺少删除操作必需字段: {missing_required}')
            if missing_recommended:
                print(f'[INFO] Cookie缺少建议字段: {missing_recommended}')

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

                    # 构建登录消息，包含Cookie完整性提示
                    message = '登录成功'
                    if missing_required:
                        message += f'（警告: Cookie缺少 {", ".join(missing_required)}，删除功能可能不可用。请在浏览器中重新复制完整Cookie）'

                    return {
                        'success': True,
                        'message': message,
                        'user_info': self.user_info,
                        'cookie_warning': bool(missing_required),
                        'missing_cookies': missing_required
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

            # 方法1: 从API直接获取（最可靠）
            try:
                response = self.session.get(f'{self.API_BASE}/api/gettemplatevariable?fields=[%22bdstoken%22]')
                if response.status_code == 200:
                    data = response.json()
                    print(f'[DEBUG] gettemplatevariable响应: {data}')
                    if data.get('errno') == 0 and data.get('result'):
                        token = data['result'].get('bdstoken', '')
                        if token:
                            self.bdstoken = token
                            print(f'[DEBUG] 从API获取bdstoken成功: {self.bdstoken[:8]}...')
                            return
            except Exception as e:
                print(f'[DEBUG] API获取bdstoken失败: {e}')

            # 方法2: 从主页获取
            response = self.session.get(f'{self.API_BASE}/disk/home')
            if response.status_code == 200:
                # 尝试多种正则模式
                patterns = [
                    r'"bdstoken"\s*:\s*"([a-f0-9]{32})"',
                    r"'bdstoken'\s*:\s*'([a-f0-9]{32})'",
                    r'bdstoken\s*=\s*["\']([a-f0-9]{32})["\']',
                    r'bdstoken&quot;:&quot;([a-f0-9]{32})&quot;',
                    r'"bdstoken":"([a-f0-9]{32})"',
                ]

                for pattern in patterns:
                    match = re.search(pattern, response.text)
                    if match:
                        self.bdstoken = match.group(1)
                        print(f'[DEBUG] 从页面获取bdstoken成功(pattern={pattern[:20]}...): {self.bdstoken[:8]}...')
                        return

                print(f'[DEBUG] 页面中未找到bdstoken，页面长度: {len(response.text)}')

            # 方法3: 从disk/main页面获取
            try:
                response = self.session.get(f'{self.API_BASE}/disk/main')
                if response.status_code == 200:
                    match = re.search(r'"bdstoken"\s*:\s*"([a-f0-9]{32})"', response.text)
                    if match:
                        self.bdstoken = match.group(1)
                        print(f'[DEBUG] 从main页面获取bdstoken成功: {self.bdstoken[:8]}...')
                        return
            except Exception as e:
                print(f'[DEBUG] main页面获取bdstoken失败: {e}')

            print(f'[WARNING] 所有方法都未能获取bdstoken')

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
        last_error_message = ''

        for i in range(0, len(paths), batch_size):
            batch = paths[i:i + batch_size]
            result = self._delete_batch(batch)

            all_deleted.extend(result.get('deleted', []))
            all_failed.extend(result.get('failed', []))

            if not result.get('success'):
                last_error_message = result.get('message', '')

            # 批次之间等待1秒，避免请求过快
            if i + batch_size < len(paths):
                time.sleep(1)

        if all_failed:
            return {
                'success': False,
                'message': f'成功{len(all_deleted)}个，失败{len(all_failed)}个。{last_error_message}',
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

            print(f'[DEBUG] 删除文件: {paths}')
            print(f'[DEBUG] bdstoken: {self.bdstoken[:8] if self.bdstoken else "None"}...')

            # 收集所有方法的错误信息
            errors = []

            # 尝试方法1: 标准API删除
            result = self._try_delete_method1(paths)
            if result.get('success'):
                return result
            errors.append(f"方法1(errno={result.get('errno', '?')})")

            print(f'[DEBUG] 方法1失败，尝试方法2')

            # 尝试方法2: 不同的API端点
            result = self._try_delete_method2(paths)
            if result.get('success'):
                return result
            errors.append(f"方法2(errno={result.get('errno', '?')})")

            print(f'[DEBUG] 方法2失败，尝试方法3')

            # 尝试方法3: xpan接口
            result = self._try_delete_method3(paths)
            if result.get('success'):
                return result
            errors.append(f"方法3(errno={result.get('errno', '?')})")

            # 所有方法都失败，返回详细错误
            result['message'] = f"删除失败 - {', '.join(errors)}。{result.get('message', '')}"
            return result

        except Exception as e:
            import traceback
            print(f'[ERROR] 删除异常: {str(e)}')
            print(traceback.format_exc())
            return {
                'success': False,
                'message': f'删除失败: {str(e)}',
                'deleted': [],
                'failed': paths
            }

    def _try_delete_method1(self, paths: List[str]) -> dict:
        """方法1: 标准filemanager API"""
        import json

        url = f'{self.API_BASE}/api/filemanager?opera=delete'
        if self.bdstoken:
            url += f'&bdstoken={self.bdstoken}'

        filelist_json = json.dumps(paths, ensure_ascii=False)

        data = {
            'filelist': filelist_json,
            'async': '0',  # 同步删除
            'channel': 'chunlei',
            'web': '1',
            'app_id': '250528',
            'clienttype': '0',
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': f'{self.API_BASE}/disk/home',
            'Origin': self.API_BASE,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        }

        response = self.session.post(url, data=data, headers=headers)
        return self._parse_delete_response(response, paths, "方法1")

    def _try_delete_method2(self, paths: List[str]) -> dict:
        """方法2: 带有更多参数的filemanager API"""
        import json

        url = f'{self.API_BASE}/api/filemanager'

        params = {
            'opera': 'delete',
            'async': '2',
            'onnest': 'fail',
            'channel': 'chunlei',
            'web': '1',
            'app_id': '250528',
            'bdstoken': self.bdstoken or '',
            'clienttype': '0',
        }

        filelist_json = json.dumps(paths, ensure_ascii=False)

        data = {
            'filelist': filelist_json,
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': f'{self.API_BASE}/disk/home',
            'Origin': self.API_BASE,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        }

        response = self.session.post(url, params=params, data=data, headers=headers)
        return self._parse_delete_response(response, paths, "方法2")

    def _try_delete_method3(self, paths: List[str]) -> dict:
        """方法3: xpan/file接口（REST API风格）"""
        import json

        url = f'{self.API_BASE}/rest/2.0/xpan/file'

        params = {
            'method': 'filemanager',
            'opera': 'delete',
        }

        filelist_json = json.dumps(paths, ensure_ascii=False)

        data = {
            'async': '0',
            'filelist': filelist_json,
            'ondup': 'fail',
        }

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Referer': f'{self.API_BASE}/disk/home',
            'Origin': self.API_BASE,
        }

        response = self.session.post(url, params=params, data=data, headers=headers)
        return self._parse_delete_response(response, paths, "方法3")

    def _parse_delete_response(self, response, paths: List[str], method_name: str) -> dict:
        """解析删除API响应"""
        if response.status_code != 200:
            print(f'[DEBUG] {method_name} HTTP错误: {response.status_code}')
            return {
                'success': False,
                'message': f'请求失败: HTTP {response.status_code}',
                'deleted': [],
                'failed': paths
            }

        try:
            result = response.json()
        except:
            print(f'[DEBUG] {method_name} 响应不是JSON: {response.text[:200]}')
            return {
                'success': False,
                'message': '响应格式错误',
                'deleted': [],
                'failed': paths
            }

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
            132: '该账号需要人机验证。请先在浏览器中打开百度网盘(pan.baidu.com)，手动删除任意一个文件，完成弹出的验证框后，回到本工具即可正常删除',
            133: '文件被锁定，无法删除',
            31034: '命中反作弊，请在网页端手动删除',
            31045: '操作太频繁，请稍后重试',
            31066: '文件不存在或已被删除',
            31362: '该功能需要登录',
            9019: '需要验证身份',
        }

        print(f'[DEBUG] {method_name} 响应: errno={errno}, result={result}')

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
                'failed': paths,
                'errno': errno
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
