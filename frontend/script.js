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
    const featuredColumnHead = document.getElementById('featured-column-head');
    const topGamesSection = document.getElementById('top-games-section');
    const gamesTableTitle = document.getElementById('games-table-title');

    const API_BASE_URL = 'http://localhost:5000/api'; // 后端 API 地址

    let currentPage = 1;
    let totalPages = 1;
    const perPage = 15; // 每页显示数量，可以根据需要调整

    let allGamesData = []; // 变量用于存储从后端获取的所有游戏数据
    let userFeaturedGames = loadUserFeaturedGames(); // 存储用户自选的重点关注游戏
    let currentSection = 'all'; // 当前激活的页签，默认为全部游戏

    // --- 用户重点关注游戏存储功能 ---
    function loadUserFeaturedGames() {
        const saved = localStorage.getItem('userFeaturedGames');
        return saved ? JSON.parse(saved) : [];
    }

    function saveUserFeaturedGames() {
        localStorage.setItem('userFeaturedGames', JSON.stringify(userFeaturedGames));
    }

    function toggleFeaturedGame(gameId, featured) {
        if (featured && !userFeaturedGames.includes(gameId)) {
            userFeaturedGames.push(gameId);
        } else if (!featured) {
            userFeaturedGames = userFeaturedGames.filter(id => id !== gameId);
        }
        saveUserFeaturedGames();
        
        // 如果在首页，则需要刷新重点游戏区域
        if (currentSection === 'all') {
            loadFeaturedGames();
        }
    }

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
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            console.log("Data received:", data); // 调试日志
            return data;
        } catch (error) {
            console.error('Fetch data error:', error);
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
        // 最多显示 16 个
        games.slice(0, 16).forEach(game => {
            const card = document.createElement('div');
            card.className = 'game-card featured-card';

            let iconHtml = '';
            if (game.icon_url) {
                const proxyImageUrl = `${API_BASE_URL}/image?url=${encodeURIComponent(game.icon_url)}`;
                iconHtml = `<img src="${proxyImageUrl}" alt="${game.name || '图标'}" class="featured-icon">`;
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
        if (!data || !data.games || data.games.length === 0) {
            const colspan = currentSection === 'featured' ? 7 : 6;
            allGamesTbody.innerHTML = `<tr><td colspan="${colspan}">未找到符合条件的游戏。</td></tr>`;
            updatePaginationControls(0, 1, 1);
            return;
        }

        // 检查是否在"热门关注"页签下
        if (currentSection === 'featured') {
            featuredColumnHead.style.display = 'table-cell'; // 显示"重点关注"列表头
        } else {
            featuredColumnHead.style.display = 'none'; // 隐藏"重点关注"列表头
        }

        data.games.forEach(game => {
            const row = document.createElement('tr');
            const gameId = game.id || `${game.name}-${game.publisher}`; // 使用ID或生成唯一标识
            
            // Date cell (first column)
            const dateCell = `<td>${game.date || '未知'}</td>`;
            
            // Icon cell
            let iconHtml = '无';
            if (game.icon_url) {
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
            const publisherCell = `<td>${game.publisher || '未知厂商'}</td>`;

            // Description cell
            const descriptionCell = `<td>${truncateText(game.description, 60) || '无'}</td>`;
            
            // Featured toggle cell (Only visible in featured tab)
            const isFeatured = userFeaturedGames.includes(gameId);
            const featuredCell = `
                <td class="featured-toggle-cell" ${currentSection !== 'featured' ? 'style="display:none;"' : ''}>
                    <label class="toggle-switch">
                        <input type="checkbox" class="featured-toggle" data-game-id="${gameId}" ${isFeatured ? 'checked' : ''}>
                        <span class="toggle-slider"></span>
                    </label>
                </td>
            `;
            
            // Assemble row HTML
            row.innerHTML = dateCell + iconCell + nameCell + statusCell + publisherCell + descriptionCell + featuredCell;
            allGamesTbody.appendChild(row);
            
            // 添加开关事件监听器
            if (currentSection === 'featured') {
                const toggleInput = row.querySelector('.featured-toggle');
                if (toggleInput) {
                    toggleInput.addEventListener('change', (e) => {
                        const gameId = e.target.getAttribute('data-game-id');
                        toggleFeaturedGame(gameId, e.target.checked);
                    });
                }
            }
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
        const lowerStatus = status.toLowerCase();
        // 优先匹配更具体的
        if (lowerStatus.includes('首发')) return 'status-release';
        if (lowerStatus.includes('新游爆料')) return 'status-reveal'; // 注意 TapTap 可能有多种类似表述
        if (lowerStatus.includes('上线') || lowerStatus.includes('公测')) return 'status-online';
        if (lowerStatus.includes('测试')) return 'status-testing';
        if (lowerStatus.includes('预约') || lowerStatus.includes('预订')) return 'status-preorder';
        if (lowerStatus.includes('开发中')) return 'status-dev';
        if (lowerStatus.includes('更新')) return 'status-update'; // 假设有更新状态
        return 'status-unknown'; // 其他或未知
    }

    function truncateText(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    // --- 填充状态过滤器 (确保使用 allGamesData) --- 
    function populateStatusFilter(games) { // 这个 games 参数现在代表 allGamesData
        const currentSelectedValue = statusFilter.value; 
        const statuses = new Set();
        games.forEach(game => {
            if (game.status) {
                statuses.add(game.status.trim());
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

        if (section === 'featured') {
            // 热门关注页签
            topGamesSection.style.display = 'none'; // 隐藏重点关注模块
            gamesTableTitle.textContent = '热门关注游戏列表';
            featuredColumnHead.style.display = 'table-cell'; // 显示重点关注列
        } else {
            // 全部游戏页签
            topGamesSection.style.display = 'block'; // 显示重点关注模块
            gamesTableTitle.textContent = '全部游戏列表';
            featuredColumnHead.style.display = 'none'; // 隐藏重点关注列
        }
    }

    // --- 加载全部游戏数据（带过滤和分页）---
    async function loadAllGames() {
        const colspan = currentSection === 'featured' ? 7 : 6;
        allGamesTbody.innerHTML = `<tr><td colspan="${colspan}" class="loading-message">正在加载游戏列表...</td></tr>`;
        prevPageButton.disabled = true;
        nextPageButton.disabled = true;

        const params = {
            page: currentPage,
            per_page: perPage,
            search: searchInput.value.trim(),
            status: statusFilter.value,
            source: sourceFilter.value,
        };

        // 根据当前页签添加特定筛选条件
        if (currentSection === 'featured') {
            // 热门关注页签 - 筛选评分不为0的项目
            params.min_score = "0.1"; // 确保评分大于0
        }

        const data = await fetchData('/games', params);
        if (data) {
            renderAllGames(data);
        } else {
            renderAllGames(null);
        }
    }
    
    // --- 获取所有游戏数据（仅用于状态填充，在初始加载时调用一次）---
    async function fetchAllGamesForStatus() {
        console.log("Fetching all games data for status filter (once)... ");
        const allData = await fetchData('/games', { per_page: 10000 });
        if (allData && allData.games) {
            allGamesData = allData.games; // 存储完整数据
            populateStatusFilter(allGamesData); // 使用完整数据填充状态过滤器
        } else {
            console.warn("Could not fetch all games data for status filter.");
            populateStatusFilter([]); // 即使失败也尝试清空并填充默认值
        }
    }
    
    // --- 加载重点游戏数据 ---
    async function loadFeaturedGames() {
        featuredGameList.innerHTML = '<p class="loading-message">正在加载重点游戏...</p>'; // 显示加载提示
        
        // 优先使用用户自选的重点游戏
        if (userFeaturedGames.length > 0) {
            // 获取所有游戏数据
            const allGames = await fetchData('/games', { per_page: 1000 });
            if (allGames && allGames.games) {
                // 筛选出用户标记的重点游戏
                const featuredGames = allGames.games.filter(game => {
                    const gameId = game.id || `${game.name}-${game.publisher}`;
                    return userFeaturedGames.includes(gameId);
                });
                
                if (featuredGames.length > 0) {
                    renderFeaturedGames(featuredGames);
                    return;
                }
            }
        }
        
        // 如果没有用户自选游戏或者获取失败，回退到厂商筛选逻辑
        const allGames = await fetchData('/games', { per_page: 100 });
        
        if (!allGames || !allGames.games || allGames.games.length === 0) {
            featuredGameList.innerHTML = '<p>未能获取游戏数据。</p>';
            return;
        }
        
        // 筛选重点游戏（根据厂商名称）
        const featuredGames = allGames.games.filter(game => {
            if (!game.publisher) return false;
            
            const publisher = game.publisher.toLowerCase();
            return publisher.includes('腾讯') || 
                   publisher.includes('tencent') || 
                   publisher.includes('网易') || 
                   publisher.includes('netease') || 
                   publisher.includes('米哈游') || 
                   publisher.includes('mihoyo') ||
                   publisher.includes('hoyoverse');
        });
        
        // 如果筛选后没有结果，尝试使用后端的 featured-games 接口
        if (featuredGames.length === 0) {
            const backendFeatured = await fetchData('/featured-games');
            renderFeaturedGames(backendFeatured);
        } else {
            renderFeaturedGames(featuredGames);
        }
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

        // 导航切换
        document.querySelectorAll('.navbar a').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelector('.navbar a.active').classList.remove('active');
                e.target.classList.add('active');
                
                const section = e.target.getAttribute('data-section');
                updateUIForSection(section);
                currentPage = 1;
                loadAllGames();
            });
        });
    }

    // --- 初始化和启动 ---
    async function initialLoad() {
        updateUIForSection('all'); // 设置初始UI状态
        setupEventListeners(); // 设置所有事件监听器
        loadFeaturedGames(); // 加载重点游戏
        await fetchAllGamesForStatus(); // 先获取所有游戏数据并填充状态过滤器
        loadAllGames();      // 然后加载第一页的全部游戏
    }

    initialLoad(); // 执行初始加载
}); 