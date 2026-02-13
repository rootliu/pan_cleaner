"""
网盘文件清理工具 - Flask 主应用
"""

import logging
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response
from config import Config, PROVIDER_TYPES

logger = logging.getLogger(__name__)

# 导入核心模块
from core.providers.baidu import BaiduProvider
from core.providers.aliyun import AliyunProvider
from core.providers.quark import QuarkProvider
from core.duplicate_finder import DuplicateFinder
from core.analyzer import FileAnalyzer
from core.cleaner import FileCleaner
from utils.file_utils import format_size
from utils.report import generate_html_report
from utils.cache import (
    save_scan_cache, load_scan_cache, clear_scan_cache,
    invalidate_cache_paths, get_cache_info
)
from utils.logger import log_delete_operation
from utils.supabase_client import get_supabase

app = Flask(__name__)
app.config.from_object(Config)

# 本地开发内存 Provider 缓存（serverless 环境下不生效）
_provider_store: dict = {}

def _is_supabase_configured() -> bool:
    """检查 Supabase 是否已配置"""
    import os
    return bool(os.environ.get('SUPABASE_URL') and os.environ.get('SUPABASE_KEY'))


def get_session_id() -> str:
    """从 Flask session cookie 获取或创建会话 ID"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']


def save_provider(sid: str, provider):
    """保存 provider 到内存缓存（本地开发用）"""
    _provider_store[sid] = provider


def get_or_create_provider():
    """
    恢复 Provider 实例
    - 本地开发：从内存缓存获取
    - Serverless (Vercel)：从 Supabase user_sessions 重建
    """
    sid = get_session_id()
    provider_type = session.get('provider_type', 'baidu')

    # 优先从内存缓存获取（本地开发模式）
    if sid in _provider_store:
        provider = _provider_store[sid]
        if provider and provider.is_logged_in:
            return provider

    # 尝试从 Supabase 恢复（serverless 模式）
    if not _is_supabase_configured():
        return None

    try:
        supabase = get_supabase()
        result = supabase.table('user_sessions').select('*').eq(
            'session_id', sid
        ).execute()

        if not result.data or len(result.data) == 0:
            return None

        row = result.data[0]
        user_info = row.get('user_info', {})

        provider = _create_provider(provider_type)
        if not provider:
            return None

        if provider_type == 'aliyun':
            refresh_token = row.get('refresh_token', '')
            access_token = row.get('access_token', '')
            drive_id = row.get('drive_id', '')
            token_expires_at = row.get('token_expires_at')

            if not refresh_token:
                return None

            provider.restore_session(
                refresh_token=refresh_token,
                access_token=access_token,
                drive_id=drive_id,
                user_info=user_info,
                token_expires_at=token_expires_at,
            )

            # 设置 token 刷新回调（持久化新 token 到 Supabase）
            def on_token_refreshed(new_refresh, new_access, new_expires):
                try:
                    get_supabase().table('user_sessions').update({
                        'refresh_token': new_refresh,
                        'access_token': new_access,
                        'token_expires_at': new_expires,
                        'last_accessed': datetime.now().isoformat(),
                    }).eq('session_id', sid).execute()
                except Exception as e:
                    logger.error(f'持久化 token 失败: {str(e)}')

            provider.on_token_refreshed = on_token_refreshed
        else:
            # 百度等基于 cookie 的 provider
            cookie_string = row.get('cookie_string', '')
            bdstoken = row.get('bdstoken')

            if not cookie_string:
                return None

            provider.restore_session(cookie_string, bdstoken, user_info)

        # 更新最后访问时间
        supabase.table('user_sessions').update({
            'last_accessed': datetime.now().isoformat()
        }).eq('session_id', sid).execute()

        # 同时放入内存缓存
        save_provider(sid, provider)

        return provider
    except Exception as e:
        logger.error(f'恢复 Provider 失败: {str(e)}')
        return None


def _create_provider(provider_type: str):
    """创建网盘提供者实例"""
    if provider_type == 'baidu':
        return BaiduProvider()
    elif provider_type == 'aliyun':
        return AliyunProvider()
    elif provider_type == 'quark':
        return QuarkProvider()
    return None


@app.route('/')
def index():
    """首页 - 重定向到登录或主页"""
    if 'logged_in' in session and session['logged_in']:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'GET':
        return render_template('login.html', providers=PROVIDER_TYPES)

    # POST 处理登录请求
    data = request.get_json()
    provider_type = data.get('provider_type', 'baidu')
    login_method = data.get('login_method', 'cookie')

    provider = _create_provider(provider_type)
    if not provider:
        return jsonify({'success': False, 'message': '不支持的网盘类型'})

    result = {'success': False, 'message': '登录失败'}

    cookie_string = ''
    if login_method == 'cookie':
        cookie_string = data.get('cookie', '')
        if hasattr(provider, 'login_with_cookie'):
            result = provider.login_with_cookie(cookie_string)
    elif login_method == 'refresh_token':
        token = data.get('refresh_token', '')
        if hasattr(provider, 'login_with_refresh_token'):
            result = provider.login_with_refresh_token(token)
    elif login_method == 'password':
        username = data.get('username', '')
        password = data.get('password', '')
        result = provider.login_with_password(username, password)
    elif login_method == 'sms':
        phone = data.get('phone', '')
        sms_code = data.get('sms_code', '')
        result = provider.login_with_sms(phone, sms_code)

    if result.get('success'):
        sid = get_session_id()
        session['logged_in'] = True
        session['provider_type'] = provider_type
        session['user_info'] = result.get('user_info', {})

        # 保存 provider 到内存缓存（本地开发可直接复用）
        save_provider(sid, provider)

        # 将凭据保存到 Supabase user_sessions（serverless 持久化）
        if _is_supabase_configured():
            try:
                supabase = get_supabase()
                session_data = {
                    'session_id': sid,
                    'provider_type': provider_type,
                    'cookie_string': cookie_string,
                    'user_info': result.get('user_info', {}),
                    'created_at': datetime.now().isoformat(),
                    'last_accessed': datetime.now().isoformat(),
                }

                if provider_type == 'aliyun':
                    session_data['refresh_token'] = result.get('refresh_token', '')
                    session_data['access_token'] = result.get('access_token', '')
                    session_data['drive_id'] = result.get('drive_id', '')
                    session_data['token_expires_at'] = result.get('token_expires_at')
                    session_data['bdstoken'] = ''
                else:
                    session_data['bdstoken'] = getattr(provider, 'bdstoken', '') or ''

                supabase.table('user_sessions').upsert(
                    session_data,
                    on_conflict='session_id'
                ).execute()
            except Exception as e:
                logger.error(f'保存会话失败: {str(e)}')

    return jsonify(result)


@app.route('/logout')
def logout():
    """登出"""
    sid = session.get('session_id')
    if sid:
        # 清理内存缓存
        _provider_store.pop(sid, None)
        # 清理 Supabase 中的会话记录
        if _is_supabase_configured():
            try:
                supabase = get_supabase()
                supabase.table('user_sessions').delete().eq(
                    'session_id', sid
                ).execute()
            except Exception:
                pass

    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    """主控制面板"""
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))

    provider_type = session.get('provider_type', 'baidu')
    user_info = session.get('user_info', {})
    provider_name = PROVIDER_TYPES.get(provider_type, '网盘')
    username = user_info.get('username', '未知用户')

    # 检查是否有缓存
    cache_info = get_cache_info(provider_name, username)

    return render_template('index.html',
                           provider_name=provider_name,
                           provider_type=provider_type,
                           user_info=user_info,
                           cache_info=cache_info)


@app.route('/api/cache/check')
def check_cache():
    """检查是否有缓存的扫描结果"""
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': '未登录'})

    provider_type = session.get('provider_type', 'baidu')
    user_info = session.get('user_info', {})
    provider_name = PROVIDER_TYPES.get(provider_type, '网盘')
    username = user_info.get('username', '未知用户')

    cache_info = get_cache_info(provider_name, username)

    if cache_info and cache_info.get('exists'):
        return jsonify({
            'success': True,
            'has_cache': True,
            'scan_time': cache_info.get('scan_time'),
            'last_updated': cache_info.get('last_updated')
        })

    return jsonify({
        'success': True,
        'has_cache': False
    })


@app.route('/api/cache/load', methods=['POST'])
def load_cache():
    """加载缓存的扫描结果"""
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': '未登录'})

    provider_type = session.get('provider_type', 'baidu')
    user_info = session.get('user_info', {})
    provider_name = PROVIDER_TYPES.get(provider_type, '网盘')
    username = user_info.get('username', '未知用户')

    cache_data = load_scan_cache(provider_name, username)

    if not cache_data:
        return jsonify({'success': False, 'message': '没有找到缓存数据'})

    cached_results = cache_data.get('scan_results', {})

    # 返回摘要
    statistics = cached_results.get('statistics', {})
    duplicate_files = cached_results.get('duplicate_files', [])
    duplicate_folders = cached_results.get('duplicate_folders', [])
    large_files = cached_results.get('large_files', {})
    executables = cached_results.get('executables', [])

    # 计算浪费空间
    wasted_space = sum(d.get('wasted_space', 0) for d in duplicate_files)
    wasted_space += sum(d.get('wasted_space', 0) for d in duplicate_folders)

    return jsonify({
        'success': True,
        'message': f'已加载缓存（扫描时间: {cache_data.get("scan_time", "未知")}）',
        'from_cache': True,
        'scan_time': cache_data.get('scan_time'),
        'summary': {
            'total_files': statistics.get('total_files', 0),
            'total_folders': statistics.get('total_folders', 0),
            'total_size': statistics.get('total_size', 0),
            'total_size_formatted': format_size(statistics.get('total_size', 0)),
            'duplicate_file_groups': len(duplicate_files),
            'duplicate_folder_groups': len(duplicate_folders),
            'large_file_count': sum(len(f) for f in large_files.values()) if isinstance(large_files, dict) else 0,
            'executable_count': len(executables),
            'wasted_space': wasted_space,
            'wasted_space_formatted': format_size(wasted_space)
        }
    })


@app.route('/api/cache/clear', methods=['POST'])
def clear_cache_route():
    """清除缓存"""
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': '未登录'})

    provider_type = session.get('provider_type', 'baidu')
    user_info = session.get('user_info', {})
    provider_name = PROVIDER_TYPES.get(provider_type, '网盘')
    username = user_info.get('username', '未知用户')

    clear_scan_cache(provider_name, username)

    return jsonify({'success': True, 'message': '缓存已清除'})


@app.route('/api/scan', methods=['POST'])
def scan():
    """扫描网盘文件"""
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': '未登录'})

    provider = get_or_create_provider()

    if not provider or not provider.is_logged_in:
        return jsonify({'success': False, 'message': '登录已过期，请重新登录'})

    data = request.get_json() or {}
    scan_path = data.get('path', '/')
    force_rescan = data.get('force_rescan', False)

    provider_type = session.get('provider_type', 'baidu')
    user_info = session.get('user_info', {})
    provider_name = PROVIDER_TYPES.get(provider_type, '网盘')
    username = user_info.get('username', '未知用户')

    # 如果不是强制重新扫描，尝试加载缓存
    if not force_rescan:
        cache_data = load_scan_cache(provider_name, username)
        if cache_data:
            cached_results = cache_data.get('scan_results', {})

            statistics = cached_results.get('statistics', {})
            duplicate_files = cached_results.get('duplicate_files', [])
            duplicate_folders = cached_results.get('duplicate_folders', [])
            large_files = cached_results.get('large_files', {})
            executables = cached_results.get('executables', [])

            wasted_space = sum(d.get('wasted_space', 0) for d in duplicate_files)
            wasted_space += sum(d.get('wasted_space', 0) for d in duplicate_folders)

            return jsonify({
                'success': True,
                'message': f'已加载缓存结果（扫描时间: {cache_data.get("scan_time", "未知")}）',
                'from_cache': True,
                'scan_time': cache_data.get('scan_time'),
                'summary': {
                    'total_files': statistics.get('total_files', 0),
                    'total_folders': statistics.get('total_folders', 0),
                    'total_size': statistics.get('total_size', 0),
                    'total_size_formatted': format_size(statistics.get('total_size', 0)),
                    'duplicate_file_groups': len(duplicate_files),
                    'duplicate_folder_groups': len(duplicate_folders),
                    'large_file_count': sum(len(f) for f in large_files.values()) if isinstance(large_files, dict) else 0,
                    'executable_count': len(executables),
                    'wasted_space': wasted_space,
                    'wasted_space_formatted': format_size(wasted_space)
                }
            })

    try:
        # 获取所有文件
        files = provider.list_all_files(scan_path, recursive=True)

        if not files:
            return jsonify({'success': False, 'message': '未找到文件或获取文件列表失败'})

        # 分析文件
        analyzer = FileAnalyzer(files)
        duplicate_finder = DuplicateFinder(files)

        # 获取各类分析结果
        statistics = analyzer.get_statistics()
        duplicate_files = duplicate_finder.find_duplicate_files()
        duplicate_folders = duplicate_finder.find_duplicate_folders()
        large_files = analyzer.find_large_files()
        executables = analyzer.find_executable_files()

        # 计算浪费空间
        wasted_space = duplicate_finder.get_total_wasted_space()

        # 转换为可缓存的格式并保存到 Supabase
        cacheable_results = {
            'statistics': statistics,
            'duplicate_files': [
                {
                    'hash': d['hash'],
                    'size': d['size'],
                    'count': d['count'],
                    'wasted_space': d['wasted_space'],
                    'files': [{'path': f.path, 'name': f.name, 'size': f.size} for f in d['files']]
                } for d in duplicate_files
            ],
            'duplicate_folders': [
                {
                    'content_hash': d['content_hash'],
                    'count': d['count'],
                    'size': d.get('size', 0),
                    'wasted_space': d['wasted_space'],
                    'folders': [{'path': f.path, 'name': f.name} for f in d['folders']]
                } for d in duplicate_folders
            ],
            'large_files': {
                category: [
                    {'path': f.path, 'name': f.name, 'size': f.size, 'extension': f.extension}
                    for f in files_list
                ] for category, files_list in large_files.items()
            },
            'executables': [
                {'path': f.path, 'name': f.name, 'size': f.size, 'extension': f.extension}
                for f in executables
            ]
        }

        # 保存到 Supabase 缓存
        save_scan_cache(provider_name, username, cacheable_results)

        # 返回摘要
        return jsonify({
            'success': True,
            'message': '扫描完成',
            'from_cache': False,
            'summary': {
                'total_files': statistics['total_files'],
                'total_folders': statistics['total_folders'],
                'total_size': statistics['total_size'],
                'total_size_formatted': format_size(statistics['total_size']),
                'duplicate_file_groups': len(duplicate_files),
                'duplicate_folder_groups': len(duplicate_folders),
                'large_file_count': sum(len(f) for f in large_files.values()),
                'executable_count': len(executables),
                'wasted_space': wasted_space,
                'wasted_space_formatted': format_size(wasted_space)
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'扫描失败: {str(e)}'})


def get_file_attr(f, attr, default=None):
    """安全获取文件属性（支持对象和字典两种格式）"""
    if hasattr(f, attr):
        return getattr(f, attr)
    elif isinstance(f, dict):
        return f.get(attr, default)
    return default


@app.route('/api/results/<result_type>')
def get_results(result_type):
    """获取详细结果（从 Supabase 缓存加载）"""
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': '未登录'})

    provider_type = session.get('provider_type', 'baidu')
    user_info = session.get('user_info', {})
    provider_name = PROVIDER_TYPES.get(provider_type, '网盘')
    username = user_info.get('username', '未知用户')

    # 从 Supabase 缓存加载结果
    cache_data = load_scan_cache(provider_name, username)
    if not cache_data:
        return jsonify({'success': False, 'message': '请先进行扫描'})

    results = cache_data.get('scan_results', {})

    if result_type == 'statistics':
        return jsonify({'success': True, 'data': results.get('statistics', {})})

    elif result_type == 'duplicate_files':
        data = []
        for dup in results.get('duplicate_files', []):
            files_data = []
            for f in dup.get('files', []):
                files_data.append({
                    'path': get_file_attr(f, 'path'),
                    'name': get_file_attr(f, 'name'),
                    'size': get_file_attr(f, 'size', 0)
                })
            data.append({
                'hash': dup.get('hash', ''),
                'size': dup.get('size', 0),
                'size_formatted': format_size(dup.get('size', 0)),
                'count': dup.get('count', 0),
                'wasted_space': dup.get('wasted_space', 0),
                'wasted_space_formatted': format_size(dup.get('wasted_space', 0)),
                'files': files_data
            })
        return jsonify({'success': True, 'data': data})

    elif result_type == 'duplicate_folders':
        data = []
        for dup in results.get('duplicate_folders', []):
            folders_data = []
            for f in dup.get('folders', []):
                folders_data.append({
                    'path': get_file_attr(f, 'path'),
                    'name': get_file_attr(f, 'name')
                })
            data.append({
                'content_hash': dup.get('content_hash', ''),
                'count': dup.get('count', 0),
                'size': dup.get('size', 0),
                'size_formatted': format_size(dup.get('size', 0)),
                'wasted_space': dup.get('wasted_space', 0),
                'wasted_space_formatted': format_size(dup.get('wasted_space', 0)),
                'folders': folders_data
            })
        return jsonify({'success': True, 'data': data})

    elif result_type == 'large_files':
        data = {}
        for category, files in results.get('large_files', {}).items():
            data[category] = [{
                'path': get_file_attr(f, 'path'),
                'name': get_file_attr(f, 'name'),
                'size': get_file_attr(f, 'size', 0),
                'size_formatted': format_size(get_file_attr(f, 'size', 0)),
                'extension': get_file_attr(f, 'extension', '')
            } for f in files]
        return jsonify({'success': True, 'data': data})

    elif result_type == 'executables':
        data = [{
            'path': get_file_attr(f, 'path'),
            'name': get_file_attr(f, 'name'),
            'size': get_file_attr(f, 'size', 0),
            'size_formatted': format_size(get_file_attr(f, 'size', 0)),
            'extension': get_file_attr(f, 'extension', '')
        } for f in results.get('executables', [])]
        return jsonify({'success': True, 'data': data})

    return jsonify({'success': False, 'message': '无效的结果类型'})


@app.route('/api/delete', methods=['POST'])
def delete_files():
    """删除选中的文件"""
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': '未登录'})

    provider = get_or_create_provider()

    if not provider or not provider.is_logged_in:
        return jsonify({'success': False, 'message': '登录已过期'})

    data = request.get_json()
    paths = data.get('paths', [])

    if not paths:
        return jsonify({'success': False, 'message': '未选择要删除的文件'})

    cleaner = FileCleaner(provider)
    result = cleaner.delete_files(paths)

    provider_type = session.get('provider_type', 'baidu')
    user_info = session.get('user_info', {})
    provider_name = PROVIDER_TYPES.get(provider_type, '网盘')
    username = user_info.get('username', '未知用户')

    # 记录删除操作日志
    log_delete_operation(
        provider_name=provider_name,
        username=username,
        paths=paths,
        deleted=result.get('deleted', []),
        failed=result.get('failed', []),
        message=result.get('message', '')
    )

    # 如果有删除成功的文件，更新缓存
    if result.get('deleted'):
        invalidate_cache_paths(provider_name, username, result['deleted'])

    return jsonify(result)


@app.route('/api/report')
def generate_report():
    """生成HTML报告（直接返回HTML，不写文件）"""
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': '未登录'})

    provider_type = session.get('provider_type', 'baidu')
    user_info = session.get('user_info', {})
    provider_name = PROVIDER_TYPES.get(provider_type, '网盘')
    username = user_info.get('username', '未知用户')

    # 从 Supabase 缓存加载结果
    cache_data = load_scan_cache(provider_name, username)
    if not cache_data:
        return jsonify({'success': False, 'message': '请先进行扫描'})

    results = cache_data.get('scan_results', {})

    html = generate_html_report(
        statistics=results.get('statistics', {}),
        duplicate_files=results.get('duplicate_files', []),
        duplicate_folders=results.get('duplicate_folders', []),
        large_files=results.get('large_files', {}),
        executables=results.get('executables', []),
        provider_name=provider_name
    )

    # 直接返回 HTML（serverless 无文件系统）
    report_filename = f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
    response = make_response(html)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="{report_filename}"'
    return response


@app.route('/api/aliyun/qr/generate')
def aliyun_qr_generate():
    """生成阿里云盘扫码登录二维码"""
    provider = AliyunProvider()
    result = provider.generate_qr_code()
    return jsonify(result)


@app.route('/api/aliyun/qr/check', methods=['POST'])
def aliyun_qr_check():
    """检查阿里云盘扫码状态"""
    data = request.get_json()
    ck = data.get('ck', '')
    t = data.get('t', '')

    if not ck or not t:
        return jsonify({'success': False, 'status': 'ERROR', 'message': '参数缺失'})

    provider = AliyunProvider()
    qr_result = provider.check_qr_status(ck, t)

    # 如果扫码确认，自动完成登录
    if qr_result.get('status') == 'CONFIRMED' and qr_result.get('refresh_token'):
        login_result = provider.login_with_refresh_token(qr_result['refresh_token'])

        if login_result.get('success'):
            sid = get_session_id()
            session['logged_in'] = True
            session['provider_type'] = 'aliyun'
            session['user_info'] = login_result.get('user_info', {})

            # 保存 provider 到内存缓存
            save_provider(sid, provider)

            # 持久化到 Supabase（serverless 环境）
            if _is_supabase_configured():
                try:
                    supabase = get_supabase()
                    session_data = {
                        'session_id': sid,
                        'provider_type': 'aliyun',
                        'cookie_string': '',
                        'bdstoken': '',
                        'refresh_token': login_result.get('refresh_token', ''),
                        'access_token': login_result.get('access_token', ''),
                        'drive_id': login_result.get('drive_id', ''),
                        'token_expires_at': login_result.get('token_expires_at'),
                        'user_info': login_result.get('user_info', {}),
                        'created_at': datetime.now().isoformat(),
                        'last_accessed': datetime.now().isoformat(),
                    }
                    supabase.table('user_sessions').upsert(
                        session_data, on_conflict='session_id'
                    ).execute()
                except Exception as e:
                    logger.error(f'保存阿里云盘会话失败: {str(e)}')

            qr_result['logged_in'] = True
            qr_result['user_info'] = login_result.get('user_info', {})

    return jsonify(qr_result)


@app.route('/results')
def results_page():
    """结果展示页面"""
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login'))

    return render_template('results.html')


# 模板过滤器
@app.template_filter('format_size')
def format_size_filter(size):
    return format_size(size)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
