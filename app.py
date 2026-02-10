"""
网盘文件清理工具 - Flask 主应用
"""

import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from config import Config, PROVIDER_TYPES

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

app = Flask(__name__)
app.config.from_object(Config)

# 全局存储（实际生产环境应使用Redis等）
providers = {}
scan_results = {}


def get_provider(provider_type: str):
    """获取网盘提供者实例"""
    if provider_type == 'baidu':
        return BaiduProvider()
    elif provider_type == 'aliyun':
        return AliyunProvider()
    elif provider_type == 'quark':
        return QuarkProvider()
    else:
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

    provider = get_provider(provider_type)
    if not provider:
        return jsonify({'success': False, 'message': '不支持的网盘类型'})

    result = {'success': False, 'message': '登录失败'}

    if login_method == 'cookie':
        cookie = data.get('cookie', '')
        if hasattr(provider, 'login_with_cookie'):
            result = provider.login_with_cookie(cookie)
    elif login_method == 'password':
        username = data.get('username', '')
        password = data.get('password', '')
        result = provider.login_with_password(username, password)
    elif login_method == 'sms':
        phone = data.get('phone', '')
        sms_code = data.get('sms_code', '')
        result = provider.login_with_sms(phone, sms_code)

    if result.get('success'):
        session['logged_in'] = True
        session['provider_type'] = provider_type
        session['user_info'] = result.get('user_info', {})
        # 存储provider实例
        session_id = session.sid if hasattr(session, 'sid') else 'default'
        providers[session_id] = provider

    return jsonify(result)


@app.route('/logout')
def logout():
    """登出"""
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

    session_id = session.sid if hasattr(session, 'sid') else 'default'
    cached_results = cache_data.get('scan_results', {})

    # 将缓存数据加载到内存
    scan_results[session_id] = cached_results

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

    session_id = session.sid if hasattr(session, 'sid') else 'default'
    provider = providers.get(session_id)

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
            scan_results[session_id] = cached_results

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

        # 存储结果到内存
        scan_results[session_id] = {
            'statistics': statistics,
            'duplicate_files': duplicate_files,
            'duplicate_folders': duplicate_folders,
            'large_files': large_files,
            'executables': executables,
            'scan_time': datetime.now().isoformat()
        }

        # 转换为可缓存的格式并保存
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

        # 保存到缓存
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
    """获取详细结果"""
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': '未登录'})

    session_id = session.sid if hasattr(session, 'sid') else 'default'
    results = scan_results.get(session_id)

    if not results:
        return jsonify({'success': False, 'message': '请先进行扫描'})

    if result_type == 'statistics':
        return jsonify({'success': True, 'data': results['statistics']})

    elif result_type == 'duplicate_files':
        # 转换为可序列化格式（支持对象和字典两种格式）
        data = []
        for dup in results['duplicate_files']:
            files_data = []
            for f in dup['files']:
                files_data.append({
                    'path': get_file_attr(f, 'path'),
                    'name': get_file_attr(f, 'name'),
                    'size': get_file_attr(f, 'size', 0)
                })
            data.append({
                'hash': dup['hash'],
                'size': dup['size'],
                'size_formatted': format_size(dup['size']),
                'count': dup['count'],
                'wasted_space': dup['wasted_space'],
                'wasted_space_formatted': format_size(dup['wasted_space']),
                'files': files_data
            })
        return jsonify({'success': True, 'data': data})

    elif result_type == 'duplicate_folders':
        data = []
        for dup in results['duplicate_folders']:
            folders_data = []
            for f in dup['folders']:
                folders_data.append({
                    'path': get_file_attr(f, 'path'),
                    'name': get_file_attr(f, 'name')
                })
            data.append({
                'content_hash': dup['content_hash'],
                'count': dup['count'],
                'size': dup.get('size', 0),
                'size_formatted': format_size(dup.get('size', 0)),
                'wasted_space': dup['wasted_space'],
                'wasted_space_formatted': format_size(dup['wasted_space']),
                'folders': folders_data
            })
        return jsonify({'success': True, 'data': data})

    elif result_type == 'large_files':
        data = {}
        for category, files in results['large_files'].items():
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
        } for f in results['executables']]
        return jsonify({'success': True, 'data': data})

    return jsonify({'success': False, 'message': '无效的结果类型'})


@app.route('/api/delete', methods=['POST'])
def delete_files():
    """删除选中的文件"""
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': '未登录'})

    session_id = session.sid if hasattr(session, 'sid') else 'default'
    provider = providers.get(session_id)

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
    """生成HTML报告"""
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': '未登录'})

    session_id = session.sid if hasattr(session, 'sid') else 'default'
    results = scan_results.get(session_id)

    if not results:
        return jsonify({'success': False, 'message': '请先进行扫描'})

    provider_type = session.get('provider_type', 'baidu')
    provider_name = PROVIDER_TYPES.get(provider_type, '网盘')

    html = generate_html_report(
        statistics=results['statistics'],
        duplicate_files=results['duplicate_files'],
        duplicate_folders=results['duplicate_folders'],
        large_files=results['large_files'],
        executables=results['executables'],
        provider_name=provider_name
    )

    # 保存报告文件
    report_dir = os.path.join(os.path.dirname(__file__), 'reports')
    os.makedirs(report_dir, exist_ok=True)

    report_filename = f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.html'
    report_path = os.path.join(report_dir, report_filename)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return send_file(report_path, as_attachment=True, download_name=report_filename)


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
