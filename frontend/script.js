// 等待 DOM 内容完全加载完成后执行
document.addEventListener('DOMContentLoaded', () => {
    const featuredGameList = document.getElementById('featured-game-list');
    const allGamesTbody = document.getElementById('all-games-tbody');
    const paginationControls = document.getElementById('pagination-controls');
    const prevPageButton = document.getElementById('prev-page');
    const nextPageButton = document.getElementById('next-page');
    const pageInfo = document.getElementById('page-info');
    const searchInput = document.getElementById('search-input');
    const statusFilter = document.getElementById('status-filter');
    const sourceFilter = document.getElementById('source-filter');
    const filterButton = document.getElementById('filter-button');
    const topGamesSection = document.getElementById('top-games-section');
    const gamesTableTitle = document.getElementById('games-table-title');

    const API_BASE_URL = 'http://localhost:5000/api'; // 后端 API 地址

    let currentPage = 1;
    let totalPages = 1;
    const perPage = 15; // 每页显示数量，与后端一致

    let allGamesData = []; // 变量用于存储从后端获取的所有游戏数据 (用于填充过滤器)
    let currentSection = 'all'; // 当前激活的页签，默认为全部游戏

    // --- 数据获取函数 ---
    async function fetchData(endpoint, params = {}) {
        const url = new URL(`${API_BASE_URL}${endpoint}`);
        Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
                url.searchParams.append(key, params[key]);
            }
        });
        console.log(`Fetching data from: ${url}`); // 调试日志
        try {
            const response = await fetch(url);
            if (!response.ok) {
                console.error(`HTTP error! status: ${response.status}, url: ${url}`); // 记录更详细的错误
                // 尝试读取错误响应体
                let errorBody = 'No error body available.';
                try {
                    errorBody = await response.text();
                    console.error(`Error body: ${errorBody}`);
                } catch (e) {
                    console.error('Could not read error response body:', e);
                }
                throw new Error(`HTTP error! status: ${response.status}. ${errorBody}`);
            }
            const data = await response.json();
            console.log("Data received:", data); // 调试日志
            return data;
        } catch (error) {
            console.error('Fetch data error:', error);
            // 向用户显示更友好的错误提示，或者记录错误
            if (endpoint === '/games' && allGamesTbody) {
                 allGamesTbody.innerHTML = `<tr><td colspan="6">加载数据失败，请稍后重试或联系管理员。(${error.message})</td></tr>`;
            } else if (endpoint === '/featured-games' && featuredGameList) {
                 featuredGameList.innerHTML = `<p>加载重点游戏失败。(${error.message})</p>`;
            }
            return null; // 或者可以返回一个包含错误信息的对象
        }
    }

    // --- 渲染函数 ---
    function renderFeaturedGames(games) {
        featuredGameList.innerHTML = ''; // 清空加载提示
        if (!games || games.length === 0) {
            featuredGameList.innerHTML = '<p>暂无重点关注游戏。</p>';
            return;
        }
        // 最多显示 16 个 (可以在后端限制，前端也做一层保护)
        games.slice(0, 16).forEach(game => {
            const card = document.createElement('div');
            card.className = 'game-card featured-card'; // 保持类名一致

            let iconHtml = '';
            // 确保 game.icon_url 存在且不为空
            if (game.icon_url && String(game.icon_url).trim() !== '') {
                const proxyImageUrl = `${API_BASE_URL}/image?url=${encodeURIComponent(game.icon_url)}`;
                iconHtml = `<img src="${proxyImageUrl}" alt="${game.name || '图标'}" class="featured-icon" loading="lazy">`; // 添加 lazy loading
            } else {
                iconHtml = '<div class="featured-icon placeholder-icon">无图</div>'; // 添加占位符样式
            }


            card.innerHTML = `
                <div class="featured-card-header">
                    ${iconHtml}
                    <h3>${game.name || '未知名称'}</h3>
                </div>
                <p><span class="label">状态/计划:</span> <span class="status-tag ${getStatusClass(game.status)}">${game.status || '未知状态'}</span></p>
                <p><span class="label">厂商:</span> ${game.publisher || '未知厂商'}</p>
                <p><span class="label">更新日期:</span> ${game.date || '未知'}</p>
                <p><span class="label">简介:</span> ${truncateText(game.description, 40) || '无'}</p>
                ${game.link ? `<a href="${game.link}" target="_blank" class="game-link">查看详情</a>` : ''}
            `;
            featuredGameList.appendChild(card);
        });
    }

    function renderAllGames(data) {
        allGamesTbody.innerHTML = ''; // 清空加载提示或旧数据
        // 注意：现在没有单独的"重点关注"列，固定为6列
        const colspan = 6;
        if (!data || !data.games || data.games.length === 0) {
            allGamesTbody.innerHTML = `<tr><td colspan="${colspan}">未找到符合条件的游戏。</td></tr>`;
            updatePaginationControls(0, 1, 1);
            return;
        }

        data.games.forEach(game => {
            const row = document.createElement('tr');
            // const gameId = game.id || `${game.name}-${game.publisher}`; // 不再需要 gameId 进行本地操作

            // Date cell (first column)
            const dateCell = `<td>${game.date || '未知'}</td>`;

            // Icon cell
            let iconHtml = '无';
            if (game.icon_url && String(game.icon_url).trim() !== '') {
                const proxyImageUrl = `${API_BASE_URL}/image?url=${encodeURIComponent(game.icon_url)}`;
                iconHtml = `<img src="${proxyImageUrl}" alt="${game.name || '图标'}" class="table-icon" loading="lazy">`;
            }
            const iconCell = `<td>${iconHtml}</td>`;

            // Name cell with link
            const nameHtml = game.link ? `<a href="${game.link}" target="_blank">${game.name || '未知名称'}</a>` : (game.name || '未知名称');
            const nameCell = `<td>${nameHtml}</td>`;

            // Status cell
            const statusCell = `<td><span class="status-tag ${getStatusClass(game.status)}">${game.status || '未知状态'}</span></td>`;

            // Publisher cell
            const publisherCell = `<td class="publisher-cell">${game.publisher || '未知厂商'}</td>`;

            // Description cell
            const descriptionCell = `<td class="description-cell">${truncateText(game.description, 60) || '无'}</td>`; // 给简介单元格添加类名

            // 移除 Featured toggle cell
            /*
            const isFeatured = userFeaturedGames.includes(gameId);
            const featuredCell = `
                <td class="featured-toggle-cell" ${currentSection !== 'featured' ? 'style="display:none;"' : ''}>
                    <label class="toggle-switch">
                        <input type="checkbox" class="featured-toggle" data-game-id="${gameId}" ${isFeatured ? 'checked' : ''}>
                        <span class="toggle-slider"></span>
                    </label>
                </td>
            `;
            */

            // Assemble row HTML (6 columns)
            row.innerHTML = dateCell + iconCell + nameCell + statusCell + publisherCell + descriptionCell;
            allGamesTbody.appendChild(row);

            // 移除开关事件监听器
            /*
            if (currentSection === 'featured') {
                const toggleInput = row.querySelector('.featured-toggle');
                if (toggleInput) {
                    toggleInput.addEventListener('change', (e) => {
                        const gameId = e.target.getAttribute('data-game-id');
                        toggleFeaturedGame(gameId, e.target.checked);
                    });
                }
            }
            */
        });

        // 更新分页
        updatePaginationControls(data.pagination.total_items, data.pagination.total_pages, data.pagination.current_page);
    }

    function updatePaginationControls(totalItems, totalPgs, currentPg) {
        totalPages = totalPgs;
        currentPage = currentPg;

        if (totalItems === 0) {
            pageInfo.textContent = '无数据';
            prevPageButton.disabled = true;
            nextPageButton.disabled = true;
        } else {
            pageInfo.textContent = `页码 ${currentPage} / ${totalPages}`;
            prevPageButton.disabled = currentPage <= 1;
            nextPageButton.disabled = currentPage >= totalPages;
        }
        paginationControls.style.display = totalItems > 0 ? 'flex' : 'none'; // 无数据时隐藏分页
    }

    // --- 辅助函数 ---
    function getStatusClass(status) {
        if (!status) return 'status-unknown';
        const lowerStatus = String(status).toLowerCase(); // 确保是字符串
        // 优先匹配更具体的
        if (lowerStatus.includes('首发')) return 'status-release';
        if (lowerStatus.includes('新游爆料') || lowerStatus.includes('爆料')) return 'status-reveal'; // 扩展匹配
        if (lowerStatus.includes('上线') || lowerStatus.includes('公测')) return 'status-online';
        if (lowerStatus.includes('测试')) return 'status-testing';
        if (lowerStatus.includes('预约') || lowerStatus.includes('预订')) return 'status-preorder';
        if (lowerStatus.includes('开发中')) return 'status-dev';
        if (lowerStatus.includes('更新')) return 'status-update'; // 假设有更新状态
        return 'status-unknown'; // 其他或未知
    }

    function truncateText(text, maxLength) {
        if (!text) return '';
        text = String(text); // 确保是字符串
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    // --- 填充状态过滤器 (确保使用 allGamesData) ---
    function populateStatusFilter(games) { // 这个 games 参数现在代表 allGamesData
        const currentSelectedValue = statusFilter.value;
        const statuses = new Set();
        games.forEach(game => {
            // 确保 game.status 存在且不为空字符串
            if (game.status && String(game.status).trim() !== '') {
                statuses.add(String(game.status).trim());
            }
        });

        statusFilter.innerHTML = '<option value="">所有状态</option>';

        const sortedStatuses = Array.from(statuses).sort();

        sortedStatuses.forEach(status => {
            const option = document.createElement('option');
            option.value = status;
            option.textContent = status;
            statusFilter.appendChild(option);
        });

        // 尝试恢复之前的选中值 (如果存在于新列表中)
        if (Array.from(statuses).includes(currentSelectedValue)) {
            statusFilter.value = currentSelectedValue;
        } else {
             statusFilter.value = ""; // 如果之前选的值不在列表里了，重置为"所有状态"
        }
    }

    // --- 更新UI以反映当前选择的页签 ---
    function updateUIForSection(section) {
        currentSection = section;
        // 清理之前的激活状态
        document.querySelectorAll('.navbar a.active').forEach(el => el.classList.remove('active'));
        // 设置当前激活状态
        const activeLink = document.querySelector(`.navbar a[data-section="${section}"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }


        if (section === 'featured') {
            // 热门关注页签
            topGamesSection.style.display = 'none'; // 隐藏首页的重点关注模块
            gamesTableTitle.textContent = '重点关注游戏列表'; // 修改标题
            // 表格本身现在不需要特殊处理，因为不再有开关列
        } else {
            // 全部游戏页签
            topGamesSection.style.display = 'block'; // 显示首页的重点关注模块
            gamesTableTitle.textContent = '全部游戏列表';
            // 表格本身也不需要特殊处理
        }
         // 切换时重置筛选条件并重新加载
        resetFilters();
        currentPage = 1;
        loadAllGames(); // 重新加载数据以匹配新 section
    }

     // --- 重置筛选条件的辅助函数 ---
    function resetFilters() {
        searchInput.value = '';
        statusFilter.value = '';
        sourceFilter.value = '';
    }


    // --- 加载全部游戏数据（带过滤和分页）---
    async function loadAllGames() {
        const colspan = 6; // 固定为 6 列
        allGamesTbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-message">正在加载游戏列表...</td></tr>`;
        prevPageButton.disabled = true;
        nextPageButton.disabled = true;

        const params = {
            page: currentPage,
            per_page: perPage,
            search: searchInput.value.trim(),
            status: statusFilter.value,
            source: sourceFilter.value,
            // 新增：根据当前页签决定是否只看重点游戏
            featured: currentSection === 'featured' ? 'true' : null // 使用 featured 参数
        };

        const data = await fetchData('/games', params);
        if (data) {
            renderAllGames(data);
        } else {
            // fetchData 内部已处理错误显示，这里可以留空或添加额外处理
            // renderAllGames(null); // 避免重复渲染错误信息
            updatePaginationControls(0, 1, 1); // 确保分页控件正确显示无数据状态
        }
    }

    // --- 获取所有游戏数据（仅用于状态填充，在初始加载时调用一次）---
    async function fetchAllGamesForStatus() {
        console.log("Fetching all games data for status filter (once)... ");
        // 请求所有数据，不分页，只为获取所有状态
        const allData = await fetchData('/games', { per_page: 10000 }); // 获取足够多的数据
        if (allData && allData.games) {
            allGamesData = allData.games; // 存储完整数据
            populateStatusFilter(allGamesData); // 使用完整数据填充状态过滤器
        } else {
            console.warn("Could not fetch all games data for status filter.");
            populateStatusFilter([]); // 即使失败也尝试清空并填充默认值
        }
    }

    // --- 加载重点游戏数据 (现在直接从后端获取) ---
    async function loadFeaturedGames() {
        featuredGameList.innerHTML = '<p class="loading-message">正在加载重点游戏...</p>'; // 显示加载提示

        // 直接请求 /api/featured-games
        const featuredGames = await fetchData('/featured-games');

        renderFeaturedGames(featuredGames); // 直接渲染从 API 获取的数据
    }

    // --- 事件监听器设置 ---
    function setupEventListeners() {
        // 筛选按钮点击
        filterButton.addEventListener('click', () => {
            currentPage = 1; // 筛选时重置到第一页
            loadAllGames();
        });

        // 搜索框回车触发筛选
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                currentPage = 1;
                loadAllGames();
            }
        });

        // 下拉框改变时也触发筛选 (可选，看是否需要实时筛选)
        // statusFilter.addEventListener('change', () => {
        //     currentPage = 1;
        //     loadAllGames();
        // });
        // sourceFilter.addEventListener('change', () => {
        //     currentPage = 1;
        //     loadAllGames();
        // });


        // 分页控件
        prevPageButton.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                loadAllGames();
            }
        });

        nextPageButton.addEventListener('click', () => {
            if (currentPage < totalPages) {
                currentPage++;
                loadAllGames();
            }
        });

        // 导航切换 (修改：切换时调用 updateUIForSection)
        document.querySelectorAll('.navbar a').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const section = e.target.getAttribute('data-section');
                if (section !== currentSection) { // 只有在切换不同 section 时才执行
                    updateUIForSection(section);
                     // updateUIForSection 内部会重置过滤器并加载数据
                }
            });
        });
    }

    // --- 初始化和启动 ---
    async function initialLoad() {
        // 默认加载 'all' 区块
        const initialSection = 'all';
        updateUIForSection(initialSection); // 设置初始UI状态 (这会加载数据)
        setupEventListeners();        // 设置所有事件监听器
        loadFeaturedGames();          // 加载首页的重点游戏卡片
        await fetchAllGamesForStatus(); // 获取所有游戏数据并填充状态过滤器
        // loadAllGames() 已经在 updateUIForSection 中调用，无需重复加载
    }

    initialLoad(); // 执行初始加载
}); 