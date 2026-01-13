"""
HTML 报告生成模块
"""

from datetime import datetime
from typing import Dict, List
from .file_utils import format_size


def generate_html_report(
    statistics: Dict,
    duplicate_files: List[Dict],
    duplicate_folders: List[Dict],
    large_files: Dict,
    executables: List,
    provider_name: str = '网盘'
) -> str:
    """
    生成HTML分析报告
    """
    report_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 计算统计数据
    total_files = statistics.get('total_files', 0)
    total_folders = statistics.get('total_folders', 0)
    total_size = statistics.get('total_size', 0)

    duplicate_file_groups = len(duplicate_files)
    duplicate_file_count = sum(d['count'] for d in duplicate_files)
    duplicate_file_wasted = sum(d['wasted_space'] for d in duplicate_files)

    duplicate_folder_groups = len(duplicate_folders)
    duplicate_folder_count = sum(d['count'] for d in duplicate_folders)
    duplicate_folder_wasted = sum(d['wasted_space'] for d in duplicate_folders)

    large_file_count = sum(len(files) for files in large_files.values())
    large_file_size = sum(sum(f.size for f in files) for files in large_files.values())

    executable_count = len(executables)
    executable_size = sum(f.size for f in executables)

    # 生成分类统计HTML
    category_stats = statistics.get('category_stats', {})
    category_rows = ''
    category_labels = []
    category_sizes = []

    for cat, data in sorted(category_stats.items(), key=lambda x: x[1]['size'], reverse=True):
        category_rows += f'''
        <tr>
            <td>{data['name']}</td>
            <td>{data['count']}</td>
            <td>{format_size(data['size'])}</td>
            <td>{data['size'] / total_size * 100:.1f}%</td>
        </tr>
        '''
        category_labels.append(data['name'])
        category_sizes.append(data['size'])

    # 生成重复文件HTML
    duplicate_file_rows = ''
    for i, dup in enumerate(duplicate_files[:100], 1):  # 最多显示100组
        files_html = '<ul class="file-list">'
        for f in dup['files']:
            files_html += f'<li>{f.path} ({format_size(f.size)})</li>'
        files_html += '</ul>'

        duplicate_file_rows += f'''
        <tr>
            <td>{i}</td>
            <td>{dup['count']}</td>
            <td>{format_size(dup['size'])}</td>
            <td>{format_size(dup['wasted_space'])}</td>
            <td>{files_html}</td>
        </tr>
        '''

    # 生成重复文件夹HTML
    duplicate_folder_rows = ''
    for i, dup in enumerate(duplicate_folders[:50], 1):
        folders_html = '<ul class="file-list">'
        for f in dup['folders']:
            folders_html += f'<li>{f.path}</li>'
        folders_html += '</ul>'

        duplicate_folder_rows += f'''
        <tr>
            <td>{i}</td>
            <td>{dup['count']}</td>
            <td>{format_size(dup.get('size', 0))}</td>
            <td>{format_size(dup['wasted_space'])}</td>
            <td>{folders_html}</td>
        </tr>
        '''

    # 生成大文件HTML（按类型）
    large_file_sections = ''
    category_names = {
        'video': '视频',
        'archive': '压缩包',
        'disk_image': '磁盘镜像',
        'executable': '可执行文件',
        'other': '其他'
    }

    for cat, files in large_files.items():
        if not files:
            continue

        cat_name = category_names.get(cat, cat)
        rows = ''
        for i, f in enumerate(files[:50], 1):
            rows += f'''
            <tr>
                <td>{i}</td>
                <td>{f.name}</td>
                <td>{f.path}</td>
                <td>{format_size(f.size)}</td>
            </tr>
            '''

        large_file_sections += f'''
        <h4>{cat_name} ({len(files)} 个文件)</h4>
        <table class="data-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>文件名</th>
                    <th>路径</th>
                    <th>大小</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        '''

    # 生成可执行文件HTML
    executable_rows = ''
    for i, f in enumerate(executables[:100], 1):
        executable_rows += f'''
        <tr>
            <td>{i}</td>
            <td>{f.name}</td>
            <td>.{f.extension}</td>
            <td>{f.path}</td>
            <td>{format_size(f.size)}</td>
        </tr>
        '''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{provider_name}文件清理分析报告</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
        }}
        .header .meta {{
            opacity: 0.9;
            font-size: 14px;
        }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .card h3 {{
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        .card .value {{
            font-size: 28px;
            font-weight: bold;
            color: #333;
        }}
        .card .sub {{
            font-size: 12px;
            color: #999;
            margin-top: 5px;
        }}
        .card.warning .value {{
            color: #f59e0b;
        }}
        .card.danger .value {{
            color: #ef4444;
        }}
        .section {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            font-size: 20px;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        .data-table th,
        .data-table td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        .data-table th {{
            background: #f8f9fa;
            font-weight: 600;
        }}
        .data-table tr:hover {{
            background: #f8f9fa;
        }}
        .file-list {{
            margin: 0;
            padding-left: 20px;
            font-size: 12px;
            color: #666;
        }}
        .file-list li {{
            margin: 3px 0;
        }}
        .chart-container {{
            max-width: 400px;
            margin: 0 auto;
        }}
        h4 {{
            margin: 20px 0 10px;
            color: #555;
        }}
        .footer {{
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 30px;
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{provider_name}文件清理分析报告</h1>
            <div class="meta">生成时间: {report_time}</div>
        </div>

        <div class="summary-cards">
            <div class="card">
                <h3>文件总数</h3>
                <div class="value">{total_files}</div>
                <div class="sub">文件夹: {total_folders}</div>
            </div>
            <div class="card">
                <h3>总空间占用</h3>
                <div class="value">{format_size(total_size)}</div>
            </div>
            <div class="card warning">
                <h3>重复文件</h3>
                <div class="value">{duplicate_file_groups} 组</div>
                <div class="sub">可节省: {format_size(duplicate_file_wasted)}</div>
            </div>
            <div class="card warning">
                <h3>重复文件夹</h3>
                <div class="value">{duplicate_folder_groups} 组</div>
                <div class="sub">可节省: {format_size(duplicate_folder_wasted)}</div>
            </div>
            <div class="card">
                <h3>大文件 (>100MB)</h3>
                <div class="value">{large_file_count}</div>
                <div class="sub">占用: {format_size(large_file_size)}</div>
            </div>
            <div class="card danger">
                <h3>可执行文件</h3>
                <div class="value">{executable_count}</div>
                <div class="sub">占用: {format_size(executable_size)}</div>
            </div>
        </div>

        <div class="section">
            <h2>文件类型分布</h2>
            <div class="chart-container">
                <canvas id="categoryChart"></canvas>
            </div>
            <table class="data-table" style="margin-top: 20px;">
                <thead>
                    <tr>
                        <th>类型</th>
                        <th>数量</th>
                        <th>大小</th>
                        <th>占比</th>
                    </tr>
                </thead>
                <tbody>
                    {category_rows}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>重复文件 ({duplicate_file_groups} 组, 共 {duplicate_file_count} 个文件)</h2>
            <p style="color: #666; margin-bottom: 15px;">清理重复文件可节省 <strong>{format_size(duplicate_file_wasted)}</strong> 空间</p>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>重复数</th>
                        <th>单文件大小</th>
                        <th>可节省</th>
                        <th>文件列表</th>
                    </tr>
                </thead>
                <tbody>
                    {duplicate_file_rows if duplicate_file_rows else '<tr><td colspan="5" style="text-align:center;">没有发现重复文件</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>重复文件夹 ({duplicate_folder_groups} 组)</h2>
            <p style="color: #666; margin-bottom: 15px;">清理重复文件夹可节省 <strong>{format_size(duplicate_folder_wasted)}</strong> 空间</p>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>重复数</th>
                        <th>文件夹大小</th>
                        <th>可节省</th>
                        <th>文件夹列表</th>
                    </tr>
                </thead>
                <tbody>
                    {duplicate_folder_rows if duplicate_folder_rows else '<tr><td colspan="5" style="text-align:center;">没有发现重复文件夹</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="section">
            <h2>大文件 (>100MB)</h2>
            <p style="color: #666; margin-bottom: 15px;">共 {large_file_count} 个大文件，占用 {format_size(large_file_size)} 空间</p>
            {large_file_sections if large_file_sections else '<p>没有发现大文件</p>'}
        </div>

        <div class="section">
            <h2>可执行文件</h2>
            <p style="color: #666; margin-bottom: 15px;">共 {executable_count} 个可执行文件，请注意安全风险</p>
            <table class="data-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>文件名</th>
                        <th>类型</th>
                        <th>路径</th>
                        <th>大小</th>
                    </tr>
                </thead>
                <tbody>
                    {executable_rows if executable_rows else '<tr><td colspan="5" style="text-align:center;">没有发现可执行文件</td></tr>'}
                </tbody>
            </table>
        </div>

        <div class="footer">
            网盘文件清理工具 - 分析报告<br>
            {report_time}
        </div>
    </div>

    <script>
        // 文件类型分布饼图
        const ctx = document.getElementById('categoryChart').getContext('2d');
        new Chart(ctx, {{
            type: 'doughnut',
            data: {{
                labels: {category_labels},
                datasets: [{{
                    data: {category_sizes},
                    backgroundColor: [
                        '#667eea', '#764ba2', '#f59e0b', '#10b981',
                        '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>'''

    return html
