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
    const publisherFilter = document.getElementById('publisher-filter'); // 新增厂商筛选器
    const filterButton = document.getElementById('filter-button');
    const topGamesSection = document.getElementById('top-games-section');
    const gamesTableTitle = document.getElementById('games-table-title');

    const API_BASE_URL = 'http://localhost:5000/api'; // 后端 API 地址

    let currentPage = 1;
    let totalPages = 1;
    const perPage = 15; // 每页显示数量，与后端一致

    let allGamesData = []; // 变量用于存储从后端获取的所有游戏数据 (用于填充过滤器)

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

    // --- 渲染函数 (修改 focus 模块) ---
    function renderFeaturedGames(games) {
        featuredGameList.innerHTML = ''; // 清空加载提示
        if (!games || games.length === 0) {
            featuredGameList.innerHTML = '<p>暂无重点关注游戏。</p>';
            return;
        }
        // games 现在是合并后的数据结构
        games.slice(0, 16).forEach(game => {
            const card = document.createElement('div');
            card.className = 'game-card featured-card';

            let iconHtml = '';
            if (game.icon_url && String(game.icon_url).trim() !== '') {
                const proxyImageUrl = `${API_BASE_URL}/image?url=${encodeURIComponent(game.icon_url)}`;
                iconHtml = `<img src="${proxyImageUrl}" alt="${game.name || '图标'}" class="featured-icon" loading="lazy">`;
            } else {
                iconHtml = '<div class="featured-icon placeholder-icon">无图</div>';
            }

            // 构建里程碑 HTML
            let milestonesHtml = '';
            if (game.milestones && game.milestones.length > 0) {
                game.milestones.forEach(milestone => {
                    // 添加 status-tag 以应用颜色
                    milestonesHtml += `<p class="milestone-item"><span class="milestone-date">${milestone.date || '未知日期'}:</span> <span class="status-tag ${getStatusClass(milestone.status)}">${milestone.status || '未知状态'}</span></p>`;
                });
            } else {
                milestonesHtml = '<p class="milestone-item">暂无动态</p>';
            }

            // 构建卡片内部 HTML
            card.innerHTML = `
                <div class="featured-card-header">
                    ${iconHtml}
                    <h3>${game.name || '未知名称'}</h3>
                </div>
                <div class="milestones-section">
                    ${milestonesHtml}
                </div>
                <p><span class="label">厂商:</span> ${game.publisher || '未知厂商'}</p>
                <p><span class="label">分类:</span> ${game.category || '无'}</p>
                ${game.link ? `<a href="${game.link}" target="_blank" class="game-link">查看详情</a>` : ''}
            `;
            featuredGameList.appendChild(card);
        });
    }

    function renderAllGames(data) {
        allGamesTbody.innerHTML = ''; // 清空加载提示或旧数据
        const colspan = 5; // 保持 5 列
        if (!data || !data.games || data.games.length === 0) {
            allGamesTbody.innerHTML = `<tr><td colspan="${colspan}">未找到符合条件的游戏。</td></tr>`;
            updatePaginationControls(0, 1, 1);
            return;
        }

        data.games.forEach(game => {
            const row = document.createElement('tr');

            // Date cell
            const dateCell = `<td>${game.date || '未知'}</td>`;

            // 生成图标 HTML
            let iconHtml = '<span class="icon-placeholder">无</span>';
            if (game.icon_url && String(game.icon_url).trim() !== '') {
                const proxyImageUrl = `${API_BASE_URL}/image?url=${encodeURIComponent(game.icon_url)}`;
                iconHtml = `<span class="icon-wrapper"><img src="${proxyImageUrl}" alt="${game.name || '图标'}" class="table-icon" loading="lazy"></span>`;
            }

            // 生成名称 HTML
            const nameTextHtml = game.link ? `<a href="${game.link}" target="_blank">${game.name || '未知名称'}</a>` : (game.name || '未知名称');

            // 生成状态标签 HTML
            const statusTagHtml = `<span class="status-tag ${getStatusClass(game.status)}">${game.status || '未知状态'}</span>`;

            // 合并图标、名称和状态标签到同一个单元格
            const nameCell = `<td class="game-name-cell">${iconHtml}<span class="name-text">${nameTextHtml}</span>${statusTagHtml}</td>`;

            // 新增：Category cell (替换原 Status cell)
            const categoryCell = `<td class="category-cell">${game.category || '无'}</td>`;

            // Publisher cell
            const publisherCell = `<td class="publisher-cell">${game.publisher || '未知厂商'}</td>`;

            // Description cell
            const descriptionCell = `<td class="description-cell">${truncateText(game.description, 60) || '无'}</td>`;

            // 组装行 HTML (日期, 名称/状态, 分类, 厂商, 简介)
            row.innerHTML = dateCell + nameCell + categoryCell + publisherCell + descriptionCell;
            allGamesTbody.appendChild(row);
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
        const statusStr = String(status); // 确保是字符串
        const lowerStatus = statusStr.toLowerCase();

        // 优先匹配包含"招募"的状态
        if (statusStr.includes('招募')) { // 直接检查原始字符串，不忽略大小写
            return 'status-recruitment'; // 新的 CSS 类
        }

        // 接着匹配其他状态（忽略大小写）
        if (lowerStatus.includes('首发')) return 'status-release';
        if (lowerStatus.includes('新游爆料') || lowerStatus.includes('爆料')) return 'status-reveal';
        if (lowerStatus.includes('上线') || lowerStatus.includes('公测')) return 'status-online';
        // 注意：由于 "招募" 已被优先处理，这里的 "测试" 不会覆盖 "测试招募"
        if (lowerStatus.includes('测试')) return 'status-testing';
        if (lowerStatus.includes('预约') || lowerStatus.includes('预订')) return 'status-preorder';
        if (lowerStatus.includes('开发中')) return 'status-dev';
        if (lowerStatus.includes('更新')) return 'status-update';

        return 'status-unknown'; // 其他或未知
    }

    function truncateText(text, maxLength) {
        if (!text) return '';
        text = String(text); // 确保是字符串
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    // --- 填充过滤器 (修改，分为状态、来源、厂商) ---
    function populateStatusFilter(games) {
        const currentSelectedValue = statusFilter.value;
        const statuses = new Set();
        games.forEach(game => {
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

        if (sortedStatuses.includes(currentSelectedValue)) {
            statusFilter.value = currentSelectedValue;
        } else {
             statusFilter.value = "";
        }
    }

    // 新增：填充来源过滤器
    function populateSourceFilter(games) {
        const currentSelectedValue = sourceFilter.value;
        const sources = new Set();
        games.forEach(game => {
            if (game.source && String(game.source).trim() !== '') {
                sources.add(String(game.source).trim());
            }
        });

        sourceFilter.innerHTML = '<option value="">所有来源</option>'; // 清空旧选项并添加默认值
        const sortedSources = Array.from(sources).sort();
        sortedSources.forEach(source => {
            const option = document.createElement('option');
            option.value = source;
            option.textContent = source;
            sourceFilter.appendChild(option);
        });

        if (sortedSources.includes(currentSelectedValue)) {
            sourceFilter.value = currentSelectedValue;
        } else {
             sourceFilter.value = "";
        }
    }

    // 新增：填充厂商过滤器
    function populatePublisherFilter(games) {
        const currentSelectedValue = publisherFilter.value;
        const publishers = new Set();
        games.forEach(game => {
            if (game.publisher && String(game.publisher).trim() !== '') {
                publishers.add(String(game.publisher).trim());
            }
        });

        // 保留 "所有厂商" 和 "腾网米"
        publisherFilter.innerHTML = '<option value="">所有厂商</option><option value="TWM">腾网米</option>';

        const sortedPublishers = Array.from(publishers).sort((a, b) => a.localeCompare(b, 'zh-CN')); // 按中文排序

        sortedPublishers.forEach(publisher => {
            const option = document.createElement('option');
            option.value = publisher;
            option.textContent = publisher;
            publisherFilter.appendChild(option);
        });

        // 尝试恢复之前的选中值 (如果存在于新列表中，且不是特殊值 TWM)
        if (sortedPublishers.includes(currentSelectedValue) || currentSelectedValue === 'TWM') {
            publisherFilter.value = currentSelectedValue;
        } else {
             publisherFilter.value = "";
        }
    }

    // --- 更新UI以反映当前选择的页签 (简化) ---
    function updateUIForSection(section) {
        // currentSection = section; // 不再需要
        // 清理之前的激活状态 (保留，以防未来添加新页签)
        document.querySelectorAll('.navbar a.active').forEach(el => el.classList.remove('active'));
        // 设置当前激活状态 (硬编码为 all)
        const activeLink = document.querySelector(`.navbar a[data-section="all"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }

        // 移除根据 section 显示/隐藏 top-games 和修改标题的逻辑
        // 因为现在只有一个 section，UI 始终是显示 top-games 和"全部游戏列表"
        topGamesSection.style.display = 'block';
        gamesTableTitle.textContent = '全部游戏列表';

         // 切换时重置筛选条件并重新加载 (保留，虽然现在不会切换，但逻辑完整)
        resetFilters();
        currentPage = 1;
        loadAllGames(); // 重新加载数据
    }

     // --- 重置筛选条件的辅助函数 --- (保持不变)
    function resetFilters() {
        searchInput.value = '';
        statusFilter.value = '';
        sourceFilter.value = '';
        publisherFilter.value = ''; // 新增重置
    }


    // --- 加载全部游戏数据（带过滤和分页）(移除 featured 参数) ---
    async function loadAllGames() {
        const colspan = 5; // 固定为 5 列
        allGamesTbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-message">正在加载游戏列表...</td></tr>`;
        prevPageButton.disabled = true;
        nextPageButton.disabled = true;

        const params = {
            page: currentPage,
            per_page: perPage,
            search: searchInput.value.trim(),
            status: statusFilter.value,
            source: sourceFilter.value,
            publisher: publisherFilter.value,
            // featured: currentSection === 'featured' ? 'true' : null // 移除 featured 参数
        };

        // 特殊处理 TWM 选项
        if (params.publisher === 'TWM') {
            params.publisher = 'TENCENT,NETEASE,MIHOYO';
        }

        const data = await fetchData('/games', params);
        if (data) {
            renderAllGames(data);
        } else {
            // fetchData 内部已处理错误显示，这里可以留空或添加额外处理
            // renderAllGames(null); // 避免重复渲染错误信息
            updatePaginationControls(0, 1, 1); // 确保分页控件正确显示无数据状态
        }
    }

    // --- 获取所有游戏数据（用于填充所有过滤器，在初始加载时调用一次）---
    async function fetchAllGamesForFilters() { // 重命名函数
        console.log("Fetching all games data for filters (once)... ");
        // 请求所有数据，不分页，只为获取所有状态、来源、厂商
        const allData = await fetchData('/games', { per_page: 10000 });
        if (allData && allData.games) {
            allGamesData = allData.games; // 存储完整数据
            populateStatusFilter(allGamesData); // 填充状态
            populateSourceFilter(allGamesData); // 填充来源
            populatePublisherFilter(allGamesData); // 填充厂商
        } else {
            console.warn("Could not fetch all games data for filters.");
            populateStatusFilter([]);
            populateSourceFilter([]);
            populatePublisherFilter([]);
        }
    }

    // --- 加载重点游戏数据 (现在直接从后端获取) ---
    async function loadFeaturedGames() {
        featuredGameList.innerHTML = '<p class="loading-message">正在加载重点游戏...</p>'; // 显示加载提示

        // 直接请求 /api/featured-games
        const featuredGames = await fetchData('/featured-games');

        renderFeaturedGames(featuredGames); // 直接渲染从 API 获取的数据
    }

    // --- 事件监听器设置 (简化导航切换) ---
    function setupEventListeners() {
        // 筛选按钮点击 (保持不变)
        filterButton.addEventListener('click', () => {
            currentPage = 1; // 筛选时重置到第一页
            loadAllGames();
        });

        // 搜索框回车触发筛选 (保持不变)
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                currentPage = 1;
                loadAllGames();
            }
        });

        // 分页控件 (保持不变)
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

        // 导航切换 (简化，因为只有一个页签了)
        // 可以完全移除，或者保留以备将来扩展
        /*
        document.querySelectorAll('.navbar a').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                // const section = e.target.getAttribute('data-section');
                // updateUIForSection('all'); // 始终回到 all
            });
        });
        */
    }

    // --- 初始化和启动 (简化) ---
    async function initialLoad() {
        // 直接设置初始状态为 all，无需调用 updateUIForSection
        const activeLink = document.querySelector(`.navbar a[data-section="all"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }
        topGamesSection.style.display = 'block';
        gamesTableTitle.textContent = '全部游戏列表';

        setupEventListeners();        // 设置所有事件监听器
        loadFeaturedGames();          // 加载首页的重点游戏卡片 (仍然保留)
        await fetchAllGamesForFilters(); // 获取所有游戏数据并填充所有过滤器
        loadAllGames();                // 初始加载全部游戏列表
    }

    initialLoad(); // 执行初始加载
}); 