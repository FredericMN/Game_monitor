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

    // 新增：获取今日和本周游戏相关元素
    const todayGameList = document.getElementById('today-game-list');
    const weeklyGameList = document.getElementById('weekly-game-list');
    const weekNavigator = document.getElementById('week-navigator');
    const prevWeekButton = document.getElementById('prev-week');
    const nextWeekButton = document.getElementById('next-week');
    const weekRangeDisplay = document.getElementById('week-range-display');

    const API_BASE_URL = 'http://localhost:5000/api'; // 后端 API 地址

    let currentPage = 1;
    let totalPages = 1;
    const perPage = 15; // 每页显示数量，与后端一致

    let allGamesData = []; // 变量用于存储从后端获取的所有游戏数据 (用于填充过滤器)

    const sideNavLinks = document.querySelectorAll('.side-nav-link');
    const sections = document.querySelectorAll('[id$="-section"]'); // 获取所有以 "-section" 结尾的 ID 元素

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
                iconHtml = '<div class="featured-icon placeholder-icon">无</div>';
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

        updatePaginationControls(data.pagination.total_items, data.pagination.total_pages, data.pagination.current_page);
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

    // --- 新增：日期处理辅助函数 ---
    function formatDate(date) {
        // 将 Date 对象格式化为 YYYY-MM-DD
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    function getWeekRange(dateOffset = 0) {
        // dateOffset: 0 表示本周, -1 表示上周, 1 表示下周, 以此类推
        const today = new Date();
        today.setDate(today.getDate() + dateOffset * 7);

        const dayOfWeek = today.getDay(); // 0 = 周日, 1 = 周一, ..., 6 = 周六

        // 计算周一 (如果今天是周日 dayOfWeek 为 0，则减去 6 天；否则减去 dayOfWeek - 1 天)
        const monday = new Date(today);
        monday.setDate(today.getDate() - (dayOfWeek === 0 ? 6 : dayOfWeek - 1));

        // 计算周日
        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);

        return {
            start: formatDate(monday),
            end: formatDate(sunday)
        };
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

    // --- 更新分页控件状态 ---
    function updatePaginationControls(totalItems, totalPagesData, currentPageData) {
        totalPages = totalPagesData; // 更新全局 totalPages
        currentPage = currentPageData; // 更新全局 currentPage

        if (!paginationControls) return; // 确保元素存在

        if (totalItems === 0 || totalPages <= 1) { // 如果没有数据或只有一页
            pageInfo.textContent = totalItems === 0 ? '无数据' : `页码 1 / 1`;
            prevPageButton.disabled = true;
            nextPageButton.disabled = true;
            // 可以选择隐藏分页控件
            // paginationControls.style.display = 'none';
        } else {
            pageInfo.textContent = `页码 ${currentPage} / ${totalPages}`;
            prevPageButton.disabled = currentPage <= 1;
            nextPageButton.disabled = currentPage >= totalPages;
            // 确保分页控件可见
            // paginationControls.style.display = 'flex';
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

    // --- 新增：加载今日游戏数据 ---
    async function loadTodayGames() {
        todayGameList.innerHTML = '<p class="loading-message">正在加载今日游戏...</p>';
        const todayDate = formatDate(new Date());
        // 新增：设置今日日期显示
        const todayDateDisplay = document.getElementById('today-date-display');
        if(todayDateDisplay) {
            todayDateDisplay.textContent = `(${todayDate})`;
        }

        const params = {
            start_date: todayDate,
            end_date: todayDate,
            // per_page: 12 // 移除前端的 per_page 限制，让后端决定
        };
        const data = await fetchData('/games', params);
        if (data && data.games) {
            // 修改：调用 renderWeeklyGames 来渲染，但只传入游戏列表和目标元素
            // renderWeeklyGames 会自动处理无数据情况，但没有按日期分组的标题
            renderWeeklyGames(data.games, todayGameList, false); // 添加第三个参数 false 表示不分组
        } else {
            // renderWeeklyGames 内部会处理空列表
             renderWeeklyGames([], todayGameList, false);
            // renderSimpleGameList([], todayGameList); // 显示"暂无游戏"
        }
    }

    // --- 新增：加载本周游戏数据 ---
    let currentWeekOffset = 0; // 0 表示本周

    async function loadWeeklyGames() {
        weeklyGameList.innerHTML = '<p class="loading-message">正在加载本周游戏...</p>';
        const weekRange = getWeekRange(currentWeekOffset);

        // 修改：始终显示日期范围
        weekRangeDisplay.textContent = `${weekRange.start} ~ ${weekRange.end}`;
        /*
        // 更新周导航显示
        if (currentWeekOffset === 0) {
            weekRangeDisplay.textContent = "本周";
        } else if (currentWeekOffset === -1) {
            weekRangeDisplay.textContent = "上周";
        } else if (currentWeekOffset === 1) {
            weekRangeDisplay.textContent = "下周";
        } else {
            weekRangeDisplay.textContent = `${weekRange.start} ~ ${weekRange.end}`;
        }
        */
        // 更新按钮状态（可选，例如限制不能查看太远的未来）
        // nextWeekButton.disabled = currentWeekOffset >= 2; // 示例：最多查看未来两周
        // prevWeekButton.disabled = currentWeekOffset <= -8; // 示例：最多查看过去八周

        const params = {
            start_date: weekRange.start,
            end_date: weekRange.end,
            // per_page: 12 // 移除前端的 per_page 限制，让后端决定
        };
        const data = await fetchData('/games', params);
        if (data && data.games) {
            renderWeeklyGames(data.games, weeklyGameList);
        } else {
            renderSimpleGameList([], weeklyGameList);
        }
    }

    // --- 新增：渲染本周游戏列表（按日期分组） ---
    function renderWeeklyGames(games, targetElement, isGrouped = true) {
        targetElement.innerHTML = ''; // 清空
        if (!games || games.length === 0) {
            const message = isGrouped ? "本周暂无游戏动态。" : "今日暂无游戏动态。"; // 根据模式显示不同提示
            targetElement.innerHTML = `<p class="loading-message">${message}</p>`;
            return;
        }

        if (isGrouped) {
            // --- 按日期分组渲染 --- (原有逻辑)
            // 1. 按日期分组
            const gamesByDate = games.reduce((acc, game) => {
                const date = game.date || '未知日期';
                if (!acc[date]) {
                    acc[date] = [];
                }
                acc[date].push(game);
                return acc;
            }, {});

            // 2. 获取排序后的日期键
            const sortedDates = Object.keys(gamesByDate).sort((a, b) => {
                 // 确保未知日期排在最后
                 if (a === '未知日期') return 1;
                 if (b === '未知日期') return -1;
                 // 按日期字符串排序
                 return a.localeCompare(b);
            });

            // 3. 为每个日期渲染一个部分
            sortedDates.forEach(date => {
                const dailyGames = gamesByDate[date];
                const dateSection = document.createElement('div');
                dateSection.className = 'weekly-date-section';

                const dateTitle = document.createElement('h4');
                dateTitle.className = 'weekly-date-title';
                // dateTitle.textContent = date; // 移动到下方
                // 新增：添加星期几
                if (date !== '未知日期') {
                    dateTitle.textContent = date; // 先设置日期
                    try {
                        const dateObj = new Date(date + 'T00:00:00'); // 避免时区问题
                        const dayOfWeek = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][dateObj.getDay()];
                        dateTitle.textContent += ` ${dayOfWeek}`;
                    } catch (e) {
                        console.error("无法解析日期以获取星期几:", date, e);
                    }
                } else {
                    dateTitle.textContent = '未知日期';
                }
                dateSection.appendChild(dateTitle);

                const dailyList = document.createElement('div');
                dailyList.className = 'daily-game-list'; // 新 class 用于样式
                dailyGames.forEach(game => {
                    // --- 卡片创建逻辑 (保持不变) ---
                    const card = document.createElement('div');
                    card.className = 'game-card compact-card weekly-item-card'; // 可以加个特定 class

                    let iconHtml = '';
                    if (game.icon_url && String(game.icon_url).trim() !== '') {
                        const proxyImageUrl = `${API_BASE_URL}/image?url=${encodeURIComponent(game.icon_url)}`;
                        iconHtml = `<img src="${proxyImageUrl}" alt="${game.name || '图标'}" class="compact-icon" loading="lazy">`;
                    } else {
                        iconHtml = '<div class="compact-icon placeholder-icon">无</div>';
                    }

                    const nameTextHtml = game.link ? `<a href="${game.link}" target="_blank">${game.name || '未知名称'}</a>` : (game.name || '未知名称');
                    const statusTagHtml = `<span class="status-tag ${getStatusClass(game.status)}">${game.status || '未知状态'}</span>`;

                    // 修改卡片结构 V3
                    card.innerHTML = `
                        <div class="card-row card-header-row">
                            ${iconHtml}
                            <div class="header-main">
                                <h4 class="compact-name" title="${game.name || '未知名称'}">${nameTextHtml}</h4>
                                ${statusTagHtml}  </div>
                        </div>
                        <div class="card-row card-details-row publisher-row">
                            <p class="compact-details publisher" title="${game.publisher || '未知厂商'}"><span class="detail-label">厂商:</span> ${game.publisher || '-'}</p>
                        </div>
                        <div class="card-row card-details-row category-row">
                            <p class="compact-details category" title="${game.category || '无分类'}"><span class="detail-label">分类:</span> ${game.category || '-'}</p>
                        </div>
                    `;
                    dailyList.appendChild(card);
                    // --- 卡片创建逻辑结束 ---
                });
                dateSection.appendChild(dailyList);
                targetElement.appendChild(dateSection);
            });
        } else {
             // --- 不分组直接渲染卡片 (用于今日游戏) ---
            targetElement.className = 'game-list daily-game-list'; // 确保目标元素有 grid 样式
            games.forEach(game => {
                 // --- 卡片创建逻辑 (与上方分组渲染中的逻辑完全一致) ---
                 const card = document.createElement('div');
                 card.className = 'game-card compact-card today-item-card'; // 可以给今日卡片一个特定 class

                 let iconHtml = '';
                 if (game.icon_url && String(game.icon_url).trim() !== '') {
                     const proxyImageUrl = `${API_BASE_URL}/image?url=${encodeURIComponent(game.icon_url)}`;
                     iconHtml = `<img src="${proxyImageUrl}" alt="${game.name || '图标'}" class="compact-icon" loading="lazy">`;
                 } else {
                     iconHtml = '<div class="compact-icon placeholder-icon">无</div>';
                 }

                 const nameTextHtml = game.link ? `<a href="${game.link}" target="_blank">${game.name || '未知名称'}</a>` : (game.name || '未知名称');
                 const statusTagHtml = `<span class="status-tag ${getStatusClass(game.status)}">${game.status || '未知状态'}</span>`;

                 // 修改卡片结构 V3
                 card.innerHTML = `
                     <div class="card-row card-header-row">
                         ${iconHtml}
                         <div class="header-main">
                             <h4 class="compact-name" title="${game.name || '未知名称'}">${nameTextHtml}</h4>
                             ${statusTagHtml}  </div>
                     </div>
                     <div class="card-row card-details-row publisher-row">
                         <p class="compact-details publisher" title="${game.publisher || '未知厂商'}"><span class="detail-label">厂商:</span> ${game.publisher || '-'}</p>
                     </div>
                     <div class="card-row card-details-row category-row">
                         <p class="compact-details category" title="${game.category || '无分类'}"><span class="detail-label">分类:</span> ${game.category || '-'}</p>
                     </div>
                 `;
                 targetElement.appendChild(card); // 直接添加卡片
                 // --- 卡片创建逻辑结束 ---
            });
        }
    }

    // --- 事件监听器设置 (修改) ---
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

        // --- 新增：周导航按钮事件监听 ---
        prevWeekButton.addEventListener('click', () => {
            currentWeekOffset--;
            loadWeeklyGames();
        });

        nextWeekButton.addEventListener('click', () => {
            currentWeekOffset++;
            loadWeeklyGames();
        });
    }

    // --- 添加平滑滚动功能 ---
    function setupSideNavScrolling() {
        sideNavLinks.forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault(); // 阻止默认的锚点跳转行为
                const targetId = this.getAttribute('href').substring(1); // 获取目标 ID (#top-games-section -> top-games-section)

                // --- 修改开始 ---
                if (targetId === 'top-games-section') {
                    // 如果是点击"重点关注"，滚动到页面顶部
                    window.scrollTo({
                        top: 0,
                        behavior: 'smooth' // 平滑滚动
                    });
                } else {
                    // 否则，滚动到对应的区域
                    const targetElement = document.getElementById(targetId);
                    if (targetElement) {
                        // 计算目标位置，考虑顶部固定导航栏的高度
                        const navbarHeight = document.querySelector('.navbar')?.offsetHeight || 0;
                        const targetPosition = targetElement.getBoundingClientRect().top + window.pageYOffset - navbarHeight - 10; // 减去导航栏高度并留一点间距

                        window.scrollTo({
                            top: targetPosition,
                            behavior: 'smooth' // 平滑滚动
                        });
                    }
                }
                // --- 修改结束 ---
            });
        });
    }

    // --- 添加滚动监听以高亮导航项 (使用 Intersection Observer) ---
    function setupScrollSpy() {
        const observerOptions = {
            root: null, // 相对于视口
            rootMargin: '-50px 0px -50% 0px', // 修改：调整顶部和底部偏移
            threshold: 0.05 // 修改：稍微增加阈值
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                const targetId = entry.target.id;
                const correspondingLink = document.querySelector(`.side-nav-link[href="#${targetId}"]`);

                if (correspondingLink) {
                    if (entry.isIntersecting) {
                        // 进入视口，先移除所有 active 类，再添加给当前链接
                        sideNavLinks.forEach(link => link.classList.remove('active'));
                        correspondingLink.classList.add('active');
                    }
                    // 可选：如果希望元素完全离开视口时取消高亮（但可能会导致没有链接高亮）
                     else {
                        // correspondingLink.classList.remove('active');
                    }
                }
            });
        }, observerOptions);

        // 观察所有目标区域
        sections.forEach(section => {
            if (section) { // 确保 section 存在
                observer.observe(section);
            }
        });
    }

    // --- 初始化和启动 (修改) ---
    async function initialLoad() {
        // 直接设置初始状态为 all，无需调用 updateUIForSection
        const activeLink = document.querySelector(`.navbar a[data-section="all"]`);
        if (activeLink) {
            activeLink.classList.add('active');
        }
        topGamesSection.style.display = 'block';
        gamesTableTitle.textContent = '全部游戏列表';

        setupEventListeners();        // 设置所有事件监听器
        setupSideNavScrolling();      // 新增：设置侧边导航滚动
        setupScrollSpy();             // 新增：设置滚动监听高亮

        loadFeaturedGames();          // 加载首页的重点游戏卡片
        loadTodayGames();             // 加载今日游戏
        loadWeeklyGames();            // 加载本周游戏
        await fetchAllGamesForFilters(); // 获取所有游戏数据并填充所有过滤器
        loadAllGames();                // 初始加载全部游戏列表
    }

    initialLoad(); // 执行初始加载
}); 