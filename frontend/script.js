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

    const API_BASE_URL = 'http://localhost:5000/api'; // 后端 API 地址

    let currentPage = 1;
    let totalPages = 1;
    const perPage = 15; // 每页显示数量，可以根据需要调整

    let allGamesData = []; // 变量用于存储从后端获取的所有游戏数据

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
        // 最多显示 8 个
        games.slice(0, 8).forEach(game => {
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
                <p><span class="label">平台:</span> ${game.platform || '未知'}</p>
                <p><span class="label">简介:</span> ${truncateText(game.description, 40) || '无'}</p>
                ${game.link ? `<a href="${game.link}" target="_blank" class="game-link">查看详情</a>` : ''}
            `;
            featuredGameList.appendChild(card);
        });
    }

    function renderAllGames(data) {
        allGamesTbody.innerHTML = ''; // 清空加载提示或旧数据
        if (!data || !data.games || data.games.length === 0) {
            allGamesTbody.innerHTML = '<tr><td colspan="8">未找到符合条件的游戏。</td></tr>'; // Adjusted colspan
            updatePaginationControls(0, 1, 1);
            return;
        }

        data.games.forEach(game => {
            const row = document.createElement('tr');
            
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

            // Publisher cell (New)
            const publisherCell = `<td>${game.publisher || '未知厂商'}</td>`;

            // Platform cell
            const platformCell = `<td>${game.platform || '未知'}</td>`;

            // Source cell
            const sourceCell = `<td>${game.source || '未知'}</td>`;

            // Description cell (Last)
            const descriptionCell = `<td>${truncateText(game.description, 60) || '无'}</td>`;
            
            // Assemble row HTML in the new order
            row.innerHTML = dateCell + iconCell + nameCell + statusCell + publisherCell + platformCell + sourceCell + descriptionCell;
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

    // --- 加载全部游戏数据（带过滤和分页）---
    async function loadAllGames() {
        allGamesTbody.innerHTML = '<tr><td colspan="8" class="loading-message">正在加载游戏列表...</td></tr>'; // Adjusted colspan
        prevPageButton.disabled = true;
        nextPageButton.disabled = true;

        const params = {
            page: currentPage,
            per_page: perPage,
            search: searchInput.value.trim(),
            status: statusFilter.value,
            source: sourceFilter.value,
        };

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
        // 注意：后端的 /api/featured-games 路由目前不直接支持分页和过滤，它返回所有符合条件的
        // 如果需要分页，需要调整后端或在前端对返回结果进行处理
        const data = await fetchData('/featured-games'); // 直接调用不带参数的接口
        // 后端返回的是一个列表，而不是带 pagination 的结构
        renderFeaturedGames(data);
    }

    // --- 事件监听器 ---
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

    // 导航切换（示例，简单实现）
    // 你可以根据需要扩展这个逻辑，例如真正地隐藏/显示不同区域
    document.querySelectorAll('.navbar a').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelector('.navbar a.active').classList.remove('active');
            e.target.classList.add('active');
            
            const section = e.target.getAttribute('data-section');
            if (section === 'featured') {
                 // 如果想在点击"热门关注"时只看重点列表，可以在此调整
                 console.log("切换到热门关注视图 (功能待实现)");
                 // 可以隐藏 all-games-table，或者重新加载 featured 数据到 all-games-table (需要后端支持或前端过滤)
                 // 为了简单起见，这里仅作演示，实际还是加载所有数据
                 // 若要实现仅显示 featured, 可以调用 loadFeaturedGames 并渲染到 all-games-table
                 // 或者修改 loadAllGames 的参数，添加 featured=true
                 const params = {
                     page: 1,
                     per_page: perPage,
                     featured: true // 假设后端 /api/games 支持 featured 参数
                 };
                 currentPage = 1;
                 fetchData('/games', params).then(renderAllGames);
            } else if (section === 'all') {
                console.log("切换到全部游戏视图");
                currentPage = 1;
                loadAllGames(); // 重新加载全部游戏的第一页
            }
        });
    });

    // --- 初始加载 ---
    async function initialLoad() {
        loadFeaturedGames(); // 加载重点游戏
        await fetchAllGamesForStatus(); // 先获取所有游戏数据并填充状态过滤器
        loadAllGames();      // 然后加载第一页的全部游戏
    }

    initialLoad(); // 执行初始加载

}); 