/**
 * 网盘文件清理工具 - 前端交互逻辑
 */

// 全局状态
const state = {
    scanning: false,
    scanResults: null,
    selectedFiles: new Set()
};

// 工具函数
function formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

// DOM 加载完成后初始化
document.addEventListener('DOMContentLoaded', function () {
    initNavigation();
    initScanButton();
    initExportButton();
    initCopyButtons();
    initDeleteButtons();
    initModal();
});

// 初始化导航
function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.content-section');

    navItems.forEach(item => {
        item.addEventListener('click', function (e) {
            e.preventDefault();

            const targetSection = this.dataset.section;

            // 更新导航状态
            navItems.forEach(nav => nav.classList.remove('active'));
            this.classList.add('active');

            // 更新内容区域
            sections.forEach(section => {
                section.classList.remove('active');
                if (section.id === targetSection + '-section') {
                    section.classList.add('active');
                }
            });
        });
    });
}

// 执行扫描
async function performScan(forceRescan = false) {
    if (state.scanning) return;

    const scanPath = document.getElementById('scanPath').value || '/';
    const scanBtn = document.getElementById('scanBtn');
    const forceRescanBtn = document.getElementById('forceRescanBtn');

    // 更新UI状态
    state.scanning = true;
    const btnText = scanBtn.querySelector('.btn-text');
    const btnLoading = scanBtn.querySelector('.btn-loading');
    btnText.style.display = 'none';
    btnLoading.style.display = 'inline';
    scanBtn.disabled = true;
    if (forceRescanBtn) forceRescanBtn.disabled = true;

    // 显示进度
    document.getElementById('beforeScan').style.display = 'none';
    document.getElementById('scanProgress').style.display = 'block';
    document.getElementById('afterScan').style.display = 'none';
    hideCacheStatus();

    try {
        const response = await fetch('/api/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path: scanPath, force_rescan: forceRescan })
        });

        const result = await response.json();

        if (result.success) {
            state.scanResults = result.summary;

            // 更新概览数据
            updateSummary(result.summary);

            // 加载详细数据
            await loadAllResults();

            // 显示结果
            document.getElementById('scanProgress').style.display = 'none';
            document.getElementById('afterScan').style.display = 'grid';

            // 启用导出按钮
            document.getElementById('exportBtn').disabled = false;

            // 显示缓存状态
            if (result.from_cache) {
                showCacheStatus(`数据来自缓存（扫描时间: ${formatDateTime(result.scan_time)}）`);
            } else {
                showCacheStatus('扫描完成，结果已缓存');
            }
        } else {
            alert(result.message || '扫描失败');
            document.getElementById('scanProgress').style.display = 'none';
            document.getElementById('beforeScan').style.display = 'block';
        }
    } catch (error) {
        console.error('扫描错误:', error);
        alert('扫描过程中发生错误');
        document.getElementById('scanProgress').style.display = 'none';
        document.getElementById('beforeScan').style.display = 'block';
    } finally {
        state.scanning = false;
        btnText.style.display = 'inline';
        btnLoading.style.display = 'none';
        scanBtn.disabled = false;
        if (forceRescanBtn) forceRescanBtn.disabled = false;
    }
}

// 初始化扫描按钮
function initScanButton() {
    const scanBtn = document.getElementById('scanBtn');
    const forceRescanBtn = document.getElementById('forceRescanBtn');

    if (scanBtn) {
        scanBtn.addEventListener('click', function () {
            performScan(false);
        });
    }

    if (forceRescanBtn) {
        forceRescanBtn.addEventListener('click', function () {
            if (confirm('确定要重新扫描吗？这将忽略缓存，可能需要较长时间。')) {
                performScan(true);
            }
        });
    }
}

// 格式化日期时间
function formatDateTime(isoString) {
    if (!isoString) return '未知';
    try {
        const date = new Date(isoString);
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch (e) {
        return isoString.slice(0, 19).replace('T', ' ');
    }
}

// 显示缓存状态
function showCacheStatus(message) {
    const statusEl = document.getElementById('cacheStatus');
    if (statusEl) {
        statusEl.querySelector('.cache-message').textContent = message;
        statusEl.style.display = 'flex';
    }
}

// 隐藏缓存状态
function hideCacheStatus() {
    const statusEl = document.getElementById('cacheStatus');
    if (statusEl) {
        statusEl.style.display = 'none';
    }
}

// 更新概览摘要
function updateSummary(summary) {
    document.getElementById('totalFiles').textContent = summary.total_files;
    document.getElementById('totalFolders').textContent = summary.total_folders;
    document.getElementById('totalSize').textContent = summary.total_size_formatted;
    document.getElementById('duplicateGroups').textContent = summary.duplicate_file_groups;
    document.getElementById('duplicateFolderGroups').textContent = summary.duplicate_folder_groups;
    document.getElementById('wastedSpace').textContent = summary.wasted_space_formatted;
    document.getElementById('largeFileCount').textContent = summary.large_file_count;
    document.getElementById('executableCount').textContent = summary.executable_count;
}

// 加载所有详细结果
async function loadAllResults() {
    await Promise.all([
        loadDuplicateFiles(),
        loadDuplicateFolders(),
        loadLargeFiles(),
        loadExecutables(),
        loadCategoryStats()
    ]);
}

// 加载重复文件
async function loadDuplicateFiles() {
    try {
        const response = await fetch('/api/results/duplicate_files');
        const result = await response.json();

        if (result.success) {
            renderDuplicateFiles(result.data);
        }
    } catch (error) {
        console.error('加载重复文件失败:', error);
    }
}

// 渲染重复文件
function renderDuplicateFiles(data) {
    const container = document.getElementById('duplicateFilesList');
    const countEl = document.getElementById('dupFileCount');

    countEl.textContent = data.length;

    if (data.length === 0) {
        container.innerHTML = '<div class="empty-state">没有发现重复文件</div>';
        return;
    }

    let html = '';
    data.forEach((group, index) => {
        html += `
            <div class="file-group" data-hash="${group.hash}">
                <div class="group-header">
                    <div class="group-info">
                        <span>重复 <strong>${group.count}</strong> 份</span>
                        <span>单文件 <strong>${group.size_formatted}</strong></span>
                        <span>可节省 <strong>${group.wasted_space_formatted}</strong></span>
                    </div>
                </div>
                <div class="group-files">
                    ${group.files.map((file, i) => `
                        <div class="file-item">
                            <input type="checkbox"
                                class="dup-file-checkbox"
                                data-path="${file.path}"
                                data-group="${group.hash}"
                                ${i === 0 ? '' : 'checked'}>
                            <span class="file-path">${file.path}</span>
                            <span class="file-size">${formatSize(file.size)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;

    // 添加复选框事件
    container.querySelectorAll('.dup-file-checkbox').forEach(cb => {
        cb.addEventListener('change', function () {
            updateDeleteButton('deleteSelectedDupFiles', '.dup-file-checkbox:checked');
        });
    });

    updateDeleteButton('deleteSelectedDupFiles', '.dup-file-checkbox:checked');
}

// 加载重复文件夹
async function loadDuplicateFolders() {
    try {
        const response = await fetch('/api/results/duplicate_folders');
        const result = await response.json();

        if (result.success) {
            renderDuplicateFolders(result.data);
        }
    } catch (error) {
        console.error('加载重复文件夹失败:', error);
    }
}

// 渲染重复文件夹
function renderDuplicateFolders(data) {
    const container = document.getElementById('duplicateFoldersList');
    const countEl = document.getElementById('dupFolderCount');

    countEl.textContent = data.length;

    if (data.length === 0) {
        container.innerHTML = '<div class="empty-state">没有发现重复文件夹</div>';
        return;
    }

    let html = '';
    data.forEach((group, index) => {
        html += `
            <div class="file-group" data-hash="${group.content_hash}">
                <div class="group-header">
                    <div class="group-info">
                        <span>重复 <strong>${group.count}</strong> 份</span>
                        <span>文件夹大小 <strong>${group.size_formatted}</strong></span>
                        <span>可节省 <strong>${group.wasted_space_formatted}</strong></span>
                    </div>
                </div>
                <div class="group-files">
                    ${group.folders.map((folder, i) => `
                        <div class="file-item">
                            <input type="checkbox"
                                class="dup-folder-checkbox"
                                data-path="${folder.path}"
                                data-group="${group.content_hash}"
                                ${i === 0 ? '' : 'checked'}>
                            <span class="file-path">${folder.path}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;

    // 添加复选框事件
    container.querySelectorAll('.dup-folder-checkbox').forEach(cb => {
        cb.addEventListener('change', function () {
            updateDeleteButton('deleteSelectedDupFolders', '.dup-folder-checkbox:checked');
        });
    });

    updateDeleteButton('deleteSelectedDupFolders', '.dup-folder-checkbox:checked');
}

// 加载大文件
async function loadLargeFiles() {
    try {
        const response = await fetch('/api/results/large_files');
        const result = await response.json();

        if (result.success) {
            renderLargeFiles(result.data);
        }
    } catch (error) {
        console.error('加载大文件失败:', error);
    }
}

// 渲染大文件
function renderLargeFiles(data) {
    const container = document.getElementById('largeFilesList');

    // 合并所有文件
    let allFiles = [];
    Object.entries(data).forEach(([category, files]) => {
        files.forEach(file => {
            allFiles.push({ ...file, category });
        });
    });

    if (allFiles.length === 0) {
        container.innerHTML = '<div class="empty-state">没有发现大文件</div>';
        return;
    }

    // 按大小排序
    allFiles.sort((a, b) => b.size - a.size);

    // 存储数据用于筛选
    container.dataset.files = JSON.stringify(allFiles);

    renderLargeFilesTable(allFiles, 'all');

    // 初始化分类标签
    initLargeCategoryTabs(data);
}

// 渲染大文件表格
function renderLargeFilesTable(files, category) {
    const container = document.getElementById('largeFilesList');

    let filteredFiles = files;
    if (category !== 'all') {
        filteredFiles = files.filter(f => f.category === category);
    }

    const categoryNames = {
        'video': '视频',
        'archive': '压缩包',
        'disk_image': '磁盘镜像',
        'executable': '可执行文件',
        'other': '其他'
    };

    let html = `
        <table class="file-table">
            <thead>
                <tr>
                    <th><input type="checkbox" id="selectAllLarge"></th>
                    <th>文件名</th>
                    <th>类型</th>
                    <th>路径</th>
                    <th>大小</th>
                </tr>
            </thead>
            <tbody>
                ${filteredFiles.map(file => `
                    <tr>
                        <td><input type="checkbox" class="large-file-checkbox" data-path="${file.path}"></td>
                        <td>${file.name}</td>
                        <td>${categoryNames[file.category] || file.category}</td>
                        <td class="file-path">${file.path}</td>
                        <td>${file.size_formatted}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    container.innerHTML = html;

    // 全选功能
    document.getElementById('selectAllLarge').addEventListener('change', function () {
        container.querySelectorAll('.large-file-checkbox').forEach(cb => {
            cb.checked = this.checked;
        });
        updateDeleteButton('deleteSelectedLarge', '.large-file-checkbox:checked');
    });

    // 单个复选框事件
    container.querySelectorAll('.large-file-checkbox').forEach(cb => {
        cb.addEventListener('change', function () {
            updateDeleteButton('deleteSelectedLarge', '.large-file-checkbox:checked');
        });
    });
}

// 初始化大文件分类标签
function initLargeCategoryTabs(data) {
    const tabsContainer = document.getElementById('largeCategoryTabs');
    if (!tabsContainer) return;

    tabsContainer.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            tabsContainer.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            const container = document.getElementById('largeFilesList');
            const allFiles = JSON.parse(container.dataset.files || '[]');
            renderLargeFilesTable(allFiles, this.dataset.category);
        });
    });
}

// 加载可执行文件
async function loadExecutables() {
    try {
        const response = await fetch('/api/results/executables');
        const result = await response.json();

        if (result.success) {
            renderExecutables(result.data);
        }
    } catch (error) {
        console.error('加载可执行文件失败:', error);
    }
}

// 渲染可执行文件
function renderExecutables(data) {
    const container = document.getElementById('executablesList');
    const countEl = document.getElementById('execCount');

    countEl.textContent = data.length;

    if (data.length === 0) {
        container.innerHTML = '<div class="empty-state">没有发现可执行文件</div>';
        return;
    }

    let html = `
        <table class="file-table">
            <thead>
                <tr>
                    <th><input type="checkbox" id="selectAllExec"></th>
                    <th>文件名</th>
                    <th>类型</th>
                    <th>路径</th>
                    <th>大小</th>
                </tr>
            </thead>
            <tbody>
                ${data.map(file => `
                    <tr>
                        <td><input type="checkbox" class="exec-file-checkbox" data-path="${file.path}"></td>
                        <td>${file.name}</td>
                        <td>.${file.extension}</td>
                        <td class="file-path">${file.path}</td>
                        <td>${file.size_formatted}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    container.innerHTML = html;

    // 全选功能
    document.getElementById('selectAllExec').addEventListener('change', function () {
        container.querySelectorAll('.exec-file-checkbox').forEach(cb => {
            cb.checked = this.checked;
        });
        updateDeleteButton('deleteSelectedExec', '.exec-file-checkbox:checked');
    });

    // 单个复选框事件
    container.querySelectorAll('.exec-file-checkbox').forEach(cb => {
        cb.addEventListener('change', function () {
            updateDeleteButton('deleteSelectedExec', '.exec-file-checkbox:checked');
        });
    });
}

// 加载分类统计
async function loadCategoryStats() {
    try {
        const response = await fetch('/api/results/statistics');
        const result = await response.json();

        if (result.success) {
            renderCategoryStats(result.data.category_stats);
        }
    } catch (error) {
        console.error('加载分类统计失败:', error);
    }
}

// 渲染分类统计
function renderCategoryStats(stats) {
    const container = document.getElementById('categoryStats');

    // 计算总大小
    let totalSize = 0;
    Object.values(stats).forEach(cat => {
        totalSize += cat.size;
    });

    // 颜色映射
    const colors = {
        'video': '#667eea',
        'image': '#10b981',
        'audio': '#f59e0b',
        'document': '#3b82f6',
        'archive': '#8b5cf6',
        'executable': '#ef4444',
        'disk_image': '#06b6d4',
        'other': '#6b7280'
    };

    // 按大小排序
    const sortedStats = Object.entries(stats).sort((a, b) => b[1].size - a[1].size);

    let html = '';
    sortedStats.forEach(([key, cat]) => {
        const percentage = totalSize > 0 ? (cat.size / totalSize * 100) : 0;
        const color = colors[key] || '#6b7280';

        html += `
            <div class="category-card">
                <div class="category-header">
                    <span class="category-name">${cat.name}</span>
                    <span class="category-count">${cat.count} 个文件</span>
                </div>
                <div class="category-bar">
                    <div class="category-bar-fill" style="width: ${percentage}%; background: ${color};"></div>
                </div>
                <div class="category-size">${formatSize(cat.size)}</div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// 更新删除按钮状态
function updateDeleteButton(btnId, selector) {
    const btn = document.getElementById(btnId);
    if (!btn) return;

    const checkedCount = document.querySelectorAll(selector).length;
    btn.disabled = checkedCount === 0;
}

// 初始化导出按钮
function initExportButton() {
    const exportBtn = document.getElementById('exportBtn');
    if (!exportBtn) return;

    exportBtn.addEventListener('click', function () {
        window.location.href = '/api/report';
    });
}

// 复制路径到剪贴板
function copyPathsToClipboard(paths) {
    const text = paths.join('\n');
    navigator.clipboard.writeText(text).then(() => {
        alert(`已复制 ${paths.length} 个路径到剪贴板！\n\n您可以在百度网盘网页端搜索这些路径并手动删除。`);
    }).catch(err => {
        // 降级方案：创建临时文本框
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        alert(`已复制 ${paths.length} 个路径到剪贴板！\n\n您可以在百度网盘网页端搜索这些路径并手动删除。`);
    });
}

// 初始化复制路径按钮
function initCopyButtons() {
    // 复制重复文件路径
    document.getElementById('copyDupFilePaths')?.addEventListener('click', function () {
        const paths = Array.from(document.querySelectorAll('.dup-file-checkbox:checked'))
            .map(cb => cb.dataset.path);
        if (paths.length === 0) {
            alert('请先选择要复制的文件');
            return;
        }
        copyPathsToClipboard(paths);
    });

    // 复制重复文件夹路径
    document.getElementById('copyDupFolderPaths')?.addEventListener('click', function () {
        const paths = Array.from(document.querySelectorAll('.dup-folder-checkbox:checked'))
            .map(cb => cb.dataset.path);
        if (paths.length === 0) {
            alert('请先选择要复制的文件夹');
            return;
        }
        copyPathsToClipboard(paths);
    });

    // 复制大文件路径
    document.getElementById('copyLargePaths')?.addEventListener('click', function () {
        const paths = Array.from(document.querySelectorAll('.large-file-checkbox:checked'))
            .map(cb => cb.dataset.path);
        if (paths.length === 0) {
            alert('请先选择要复制的文件');
            return;
        }
        copyPathsToClipboard(paths);
    });

    // 复制可执行文件路径
    document.getElementById('copyExecPaths')?.addEventListener('click', function () {
        const paths = Array.from(document.querySelectorAll('.exec-file-checkbox:checked'))
            .map(cb => cb.dataset.path);
        if (paths.length === 0) {
            alert('请先选择要复制的文件');
            return;
        }
        copyPathsToClipboard(paths);
    });
}

// 初始化删除按钮
function initDeleteButtons() {
    // 重复文件删除
    document.getElementById('deleteSelectedDupFiles')?.addEventListener('click', function () {
        const paths = Array.from(document.querySelectorAll('.dup-file-checkbox:checked'))
            .map(cb => cb.dataset.path);
        showDeleteConfirm(paths);
    });

    // 重复文件夹删除
    document.getElementById('deleteSelectedDupFolders')?.addEventListener('click', function () {
        const paths = Array.from(document.querySelectorAll('.dup-folder-checkbox:checked'))
            .map(cb => cb.dataset.path);
        showDeleteConfirm(paths);
    });

    // 大文件删除
    document.getElementById('deleteSelectedLarge')?.addEventListener('click', function () {
        const paths = Array.from(document.querySelectorAll('.large-file-checkbox:checked'))
            .map(cb => cb.dataset.path);
        showDeleteConfirm(paths);
    });

    // 可执行文件删除
    document.getElementById('deleteSelectedExec')?.addEventListener('click', function () {
        const paths = Array.from(document.querySelectorAll('.exec-file-checkbox:checked'))
            .map(cb => cb.dataset.path);
        showDeleteConfirm(paths);
    });
}

// 显示删除确认对话框
function showDeleteConfirm(paths) {
    state.selectedFiles = new Set(paths);

    const modal = document.getElementById('deleteModal');
    const countEl = document.getElementById('deleteCount');

    countEl.textContent = paths.length;
    modal.style.display = 'flex';
}

// 初始化模态框
function initModal() {
    const modal = document.getElementById('deleteModal');
    if (!modal) return;

    // 关闭按钮
    modal.querySelector('.modal-close')?.addEventListener('click', closeModal);
    document.getElementById('cancelDelete')?.addEventListener('click', closeModal);

    // 点击背景关闭
    modal.addEventListener('click', function (e) {
        if (e.target === modal) {
            closeModal();
        }
    });

    // 确认删除
    document.getElementById('confirmDelete')?.addEventListener('click', async function () {
        const paths = Array.from(state.selectedFiles);

        this.disabled = true;
        this.textContent = '删除中...';

        try {
            const response = await fetch('/api/delete', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ paths })
            });

            const result = await response.json();

            if (result.success) {
                alert(`成功删除 ${result.deleted.length} 个文件`);
                closeModal();
                // 重新扫描
                document.getElementById('scanBtn')?.click();
            } else {
                alert(result.message || '删除失败');
            }
        } catch (error) {
            console.error('删除错误:', error);
            alert('删除过程中发生错误');
        } finally {
            this.disabled = false;
            this.textContent = '确认删除';
        }
    });
}

// 关闭模态框
function closeModal() {
    const modal = document.getElementById('deleteModal');
    if (modal) {
        modal.style.display = 'none';
    }
    state.selectedFiles.clear();
}
