"""
阿里云盘提供者实现
支持 Refresh Token 登录和扫码登录
"""

import base64
import json
import logging
import time
import requests
from typing import List, Optional, Callable
from datetime import datetime, timedelta
from ..base_provider import BaseProvider, FileInfo

logger = logging.getLogger(__name__)


class AliyunProvider(BaseProvider):
    """阿里云盘提供者"""

    # API 域名
    API_HOST = 'https://api.alipan.com'
    AUTH_HOST = 'https://auth.aliyundrive.com'
    PASSPORT_HOST = 'https://passport.aliyundrive.com'

    # 内置 client id
    CLIENT_ID = '25dzX3vbYqktVxyX'

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'Origin': 'https://www.alipan.com',
            'Referer': 'https://www.alipan.com/',
        })
        self.access_token = None
        self.refresh_token = None
        self.drive_id = None
        self.token_expires_at = None
        # token 刷新回调（用于 serverless 持久化）
        self.on_token_refreshed: Optional[Callable] = None

    @property
    def provider_name(self) -> str:
        return '阿里云盘'

    # ─── Token 管理 ────────────────────────────────────────

    def _set_auth_header(self):
        """设置 Authorization 请求头"""
        if self.access_token:
            self.session.headers['Authorization'] = f'Bearer {self.access_token}'

    def _ensure_token(self):
        """确保 access_token 有效，过期则自动刷新"""
        if not self.access_token or not self.refresh_token:
            return False

        # 检查是否过期（提前 5 分钟刷新）
        if self.token_expires_at:
            if isinstance(self.token_expires_at, str):
                try:
                    parsed = datetime.fromisoformat(
                        self.token_expires_at.replace('Z', '+00:00')
                    )
                    # 统一转为 naive datetime（去掉时区信息），避免 naive vs aware 比较错误
                    self.token_expires_at = parsed.replace(tzinfo=None)
                except (ValueError, TypeError):
                    self.token_expires_at = None
            elif hasattr(self.token_expires_at, 'tzinfo') and self.token_expires_at.tzinfo is not None:
                self.token_expires_at = self.token_expires_at.replace(tzinfo=None)

            if self.token_expires_at and datetime.now() < self.token_expires_at - timedelta(minutes=5):
                self._set_auth_header()
                return True

        # 需要刷新
        return self._refresh_access_token()

    def _refresh_access_token(self) -> bool:
        """用 refresh_token 刷新 access_token"""
        if not self.refresh_token:
            return False

        try:
            resp = requests.post(
                f'{self.AUTH_HOST}/v2/account/token',
                json={
                    'grant_type': 'refresh_token',
                    'refresh_token': self.refresh_token,
                },
                headers={'Content-Type': 'application/json'},
                timeout=10,
            )

            if resp.status_code != 200:
                logger.error(f'Token 刷新失败: HTTP {resp.status_code}')
                return False

            data = resp.json()

            if 'access_token' not in data:
                logger.error(f'Token 刷新响应无 access_token: {data}')
                return False

            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']
            self.drive_id = data.get('default_drive_id', self.drive_id)

            expires_in = data.get('expires_in', 7200)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            self._set_auth_header()

            # 通知持久化
            if self.on_token_refreshed:
                self.on_token_refreshed(
                    self.refresh_token,
                    self.access_token,
                    self.token_expires_at.isoformat(),
                )

            logger.debug(f'Token 刷新成功，expires_in={expires_in}s')
            return True

        except Exception as e:
            logger.error(f'Token 刷新异常: {str(e)}')
            return False

    # ─── 登录方法 ──────────────────────────────────────────

    def login_with_refresh_token(self, token: str) -> dict:
        """使用 refresh_token 登录"""
        self.refresh_token = token.strip()

        if not self._refresh_access_token():
            return {
                'success': False,
                'message': 'Refresh Token 无效或已过期，请重新获取',
                'user_info': None,
            }

        # 获取用户信息
        try:
            user_resp = self.session.post(
                f'{self.API_HOST}/v2/user/get', json={}, timeout=10
            )
            user_data = user_resp.json() if user_resp.status_code == 200 else {}

            drive_resp = self.session.post(
                f'{self.API_HOST}/v2/drive/get',
                json={'drive_id': self.drive_id},
                timeout=10,
            )
            drive_data = drive_resp.json() if drive_resp.status_code == 200 else {}

            self.is_logged_in = True
            self.user_info = {
                'username': user_data.get('nick_name') or user_data.get('user_name', '未知用户'),
                'user_id': user_data.get('user_id', ''),
                'avatar': user_data.get('avatar', ''),
                'phone': user_data.get('phone', ''),
                'quota_total': drive_data.get('total_size', 0),
                'quota_used': drive_data.get('used_size', 0),
            }

            return {
                'success': True,
                'message': '登录成功',
                'user_info': self.user_info,
                'refresh_token': self.refresh_token,
                'access_token': self.access_token,
                'drive_id': self.drive_id,
                'token_expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None,
            }

        except Exception as e:
            logger.error(f'获取用户信息失败: {str(e)}')
            self.is_logged_in = True
            self.user_info = {'username': '阿里云盘用户'}
            return {
                'success': True,
                'message': '登录成功（获取用户信息失败）',
                'user_info': self.user_info,
                'refresh_token': self.refresh_token,
                'access_token': self.access_token,
                'drive_id': self.drive_id,
                'token_expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None,
            }

    def login_with_password(self, username: str, password: str) -> dict:
        return {
            'success': False,
            'message': '阿里云盘不支持密码登录，请使用 Refresh Token 或扫码登录',
            'user_info': None,
        }

    def send_sms_code(self, phone: str) -> dict:
        return {
            'success': False,
            'message': '阿里云盘不支持短信验证码登录，请使用 Refresh Token 或扫码登录',
        }

    def login_with_sms(self, phone: str, sms_code: str) -> dict:
        return {
            'success': False,
            'message': '阿里云盘不支持短信验证码登录，请使用 Refresh Token 或扫码登录',
            'user_info': None,
        }

    # ─── 扫码登录 ──────────────────────────────────────────

    def generate_qr_code(self) -> dict:
        """生成扫码登录二维码"""
        try:
            resp = requests.get(
                f'{self.PASSPORT_HOST}/newlogin/qrcode/generate.do',
                params={
                    'appName': 'aliyun_drive',
                    'fromSite': '52',
                    'appEntrance': 'web_default',
                    '_bx-v': '2.5.2',
                },
                timeout=10,
            )

            if resp.status_code != 200:
                return {'success': False, 'message': f'生成二维码失败: HTTP {resp.status_code}'}

            data = resp.json()
            content = data.get('content', {}).get('data', {})

            if not content.get('codeContent'):
                return {'success': False, 'message': '生成二维码失败: 无内容'}

            return {
                'success': True,
                'qr_url': content['codeContent'],
                'ck': content.get('ck', ''),
                't': content.get('t', ''),
            }

        except Exception as e:
            return {'success': False, 'message': f'生成二维码失败: {str(e)}'}

    def check_qr_status(self, ck: str, t: str) -> dict:
        """检查扫码状态"""
        try:
            resp = requests.post(
                f'{self.PASSPORT_HOST}/newlogin/qrcode/query.do',
                data={
                    't': t,
                    'ck': ck,
                    'appName': 'aliyun_drive',
                    'appEntrance': 'web_default',
                    'fromSite': '52',
                    'navlanguage': 'zh-CN',
                    'navPlatform': 'Win32',
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=10,
            )

            if resp.status_code != 200:
                return {'success': False, 'status': 'ERROR', 'message': f'HTTP {resp.status_code}'}

            data = resp.json()
            logger.debug(f'QR query 原始响应: {json.dumps(data, ensure_ascii=False)[:500]}')
            content = data.get('content', {}).get('data', {})
            qr_code_status = content.get('qrCodeStatus', '')

            if qr_code_status == 'NEW':
                return {'success': True, 'status': 'NEW', 'message': '等待扫码'}
            elif qr_code_status == 'SCANED':
                return {'success': True, 'status': 'SCANED', 'message': '已扫码，请在手机上确认'}
            elif qr_code_status == 'CONFIRMED':
                # 提取 refresh_token
                biz_ext = content.get('bizExt', '')
                logger.debug(f'CONFIRMED content keys: {list(content.keys())}')
                logger.debug(f'bizExt 长度: {len(biz_ext) if biz_ext else 0}')
                if biz_ext:
                    try:
                        decoded = base64.b64decode(biz_ext).decode('utf-8')
                        logger.debug(f'bizExt 解码: {decoded[:300]}')
                        biz_data = json.loads(decoded)
                        logger.debug(f'bizExt JSON keys: {list(biz_data.keys())}')
                        pds_login = biz_data.get('pds_login_result', {})
                        if not pds_login:
                            logger.debug(f'pds_login_result 不存在, 尝试其他 key')
                            # 尝试其他可能的 key
                            for key in biz_data:
                                if 'login' in key.lower() or 'token' in key.lower():
                                    logger.debug(f'找到候选 key: {key}')
                                    pds_login = biz_data[key] if isinstance(biz_data[key], dict) else {}
                        refresh_token = pds_login.get('refreshToken', '') or pds_login.get('refresh_token', '')

                        if refresh_token:
                            return {
                                'success': True,
                                'status': 'CONFIRMED',
                                'message': '扫码成功',
                                'refresh_token': refresh_token,
                            }
                        else:
                            logger.debug(f'pds_login keys: {list(pds_login.keys()) if pds_login else "empty"}')
                    except Exception as e:
                        logger.exception(f'解析 bizExt 失败: {str(e)}')

                return {'success': False, 'status': 'CONFIRMED', 'message': '扫码成功但无法获取 token'}
            elif qr_code_status == 'EXPIRED':
                return {'success': True, 'status': 'EXPIRED', 'message': '二维码已过期，请重新生成'}
            else:
                return {'success': True, 'status': qr_code_status, 'message': f'未知状态: {qr_code_status}'}

        except Exception as e:
            return {'success': False, 'status': 'ERROR', 'message': f'查询失败: {str(e)}'}

    # ─── Session 恢复 ─────────────────────────────────────

    def restore_session(self, refresh_token: str = None, access_token: str = None,
                        drive_id: str = None, user_info: dict = None,
                        token_expires_at=None, **kwargs):
        """
        从保存的凭据恢复会话（轻量级，不调用 API）
        用于 Vercel serverless 每次请求重建 Provider
        """
        self.refresh_token = refresh_token
        self.access_token = access_token
        self.drive_id = drive_id
        self.user_info = user_info or {}
        self.token_expires_at = token_expires_at
        self.is_logged_in = True
        self._set_auth_header()

    # ─── 文件操作 ──────────────────────────────────────────

    def list_files(self, path: str = 'root') -> List[FileInfo]:
        """
        列出指定目录下的文件
        path 参数实际是 parent_file_id（'root' 表示根目录）
        """
        if not self.is_logged_in:
            return []

        if not self._ensure_token():
            return []

        parent_file_id = path if path and path != '/' else 'root'
        files = []
        marker = ''

        try:
            while True:
                body = {
                    'drive_id': self.drive_id,
                    'parent_file_id': parent_file_id,
                    'limit': 200,
                    'order_by': 'name',
                    'order_direction': 'ASC',
                    'fields': '*',
                }
                if marker:
                    body['marker'] = marker

                resp = self.session.post(
                    f'{self.API_HOST}/adrive/v3/file/list',
                    json=body,
                    timeout=15,
                )

                if resp.status_code != 200:
                    logger.error(f'列出文件失败: HTTP {resp.status_code}')
                    break

                data = resp.json()
                items = data.get('items', [])

                for item in items:
                    is_dir = item.get('type') == 'folder'
                    file_info = FileInfo(
                        path=item.get('file_id', ''),
                        name=item.get('name', ''),
                        size=item.get('size', 0) if not is_dir else 0,
                        is_dir=is_dir,
                        md5=item.get('content_hash') if not is_dir else None,
                        created_time=self._parse_time(item.get('created_at')),
                        modified_time=self._parse_time(item.get('updated_at')),
                    )
                    files.append(file_info)

                marker = data.get('next_marker', '')
                if not marker:
                    break

            return files

        except Exception as e:
            logger.error(f'列出文件异常: {str(e)}')
            return files

    def list_all_files(self, path: str = 'root', recursive: bool = True) -> List[FileInfo]:
        """递归列出所有文件"""
        parent_file_id = path if path and path != '/' else 'root'
        all_files = []

        files = self.list_files(parent_file_id)

        for file in files:
            all_files.append(file)
            if recursive and file.is_dir:
                # file.path 存的是 file_id
                sub_files = self.list_all_files(file.path, recursive=True)
                all_files.extend(sub_files)

        return all_files

    def get_file_info(self, path: str) -> Optional[FileInfo]:
        """获取单个文件信息（path 参数实际是 file_id）"""
        if not self.is_logged_in or not self._ensure_token():
            return None

        try:
            resp = self.session.post(
                f'{self.API_HOST}/v2/file/get',
                json={
                    'drive_id': self.drive_id,
                    'file_id': path,
                },
                timeout=10,
            )

            if resp.status_code != 200:
                return None

            item = resp.json()
            is_dir = item.get('type') == 'folder'

            return FileInfo(
                path=item.get('file_id', ''),
                name=item.get('name', ''),
                size=item.get('size', 0) if not is_dir else 0,
                is_dir=is_dir,
                md5=item.get('content_hash') if not is_dir else None,
                created_time=self._parse_time(item.get('created_at')),
                modified_time=self._parse_time(item.get('updated_at')),
            )

        except Exception as e:
            logger.error(f'获取文件信息失败: {str(e)}')
            return None

    def delete_files(self, paths: List[str]) -> dict:
        """
        删除文件（移入回收站）
        paths 参数实际是 file_id 列表
        """
        if not self.is_logged_in or not self._ensure_token():
            return {
                'success': False,
                'message': '未登录或 Token 已失效',
                'deleted': [],
                'failed': paths,
            }

        deleted = []
        failed = []
        last_error = ''

        for file_id in paths:
            try:
                resp = self.session.post(
                    f'{self.API_HOST}/v2/recyclebin/trash',
                    json={
                        'drive_id': self.drive_id,
                        'file_id': file_id,
                    },
                    timeout=10,
                )

                if resp.status_code in (200, 202, 204):
                    deleted.append(file_id)
                else:
                    error_data = resp.json() if resp.text else {}
                    error_msg = error_data.get('message', f'HTTP {resp.status_code}')
                    last_error = error_msg
                    failed.append(file_id)
                    logger.error(f'删除 {file_id} 失败: {error_msg}')

                # 避免请求过快
                if len(paths) > 1:
                    time.sleep(0.5)

            except Exception as e:
                last_error = str(e)
                failed.append(file_id)
                logger.error(f'删除 {file_id} 异常: {str(e)}')

        if failed:
            return {
                'success': False,
                'message': f'成功 {len(deleted)} 个，失败 {len(failed)} 个。{last_error}',
                'deleted': deleted,
                'failed': failed,
            }

        return {
            'success': True,
            'message': f'已移入回收站: {len(deleted)} 个文件',
            'deleted': deleted,
            'failed': [],
        }

    def get_quota(self) -> dict:
        """获取网盘容量信息"""
        if not self.is_logged_in or not self._ensure_token():
            return {'total': 0, 'used': 0, 'free': 0}

        try:
            resp = self.session.post(
                f'{self.API_HOST}/v2/drive/get',
                json={'drive_id': self.drive_id},
                timeout=10,
            )

            if resp.status_code != 200:
                return {'total': 0, 'used': 0, 'free': 0}

            data = resp.json()
            total = data.get('total_size', 0)
            used = data.get('used_size', 0)

            return {
                'total': total,
                'used': used,
                'free': total - used,
            }

        except Exception as e:
            logger.error(f'获取容量信息失败: {str(e)}')
            return {'total': 0, 'used': 0, 'free': 0}

    # ─── 工具方法 ──────────────────────────────────────────

    @staticmethod
    def _parse_time(time_str: Optional[str]) -> Optional[datetime]:
        """解析 ISO 8601 时间字符串"""
        if not time_str:
            return None
        try:
            parsed = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            return parsed.replace(tzinfo=None)
        except (ValueError, TypeError):
            return None
