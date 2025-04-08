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
            card.className = 'game-card';
            card.innerHTML = `
                <h3>${game.name || '未知名称'}</h3>
                <p><span class="label">状态/计划:</span> <span class="status-tag ${getStatusClass(game.status)}">${game.status || '未知状态'}</span></p>
                <p><span class="label">更新日期:</span> ${game.date || '未知'}</p>
                <p><span class="label">平台:</span> ${game.platform || '未知'}</p>
                <p><span class="label">来源:</span> ${game.source || '未知'}</p>
                <p><span class="label">简介:</span> ${truncateText(game.description, 50) || '无'}</p>
                ${game.link ? `<a href="${game.link}" target="_blank" class="game-link">查看详情</a>` : ''}
            `;
            featuredGameList.appendChild(card);
        });
    }

    function renderAllGames(data) {
        allGamesTbody.innerHTML = ''; // 清空加载提示或旧数据
        if (!data || !data.games || data.games.length === 0) {
            allGamesTbody.innerHTML = '<tr><td colspan="9">未找到符合条件的游戏。</td></tr>';
            // 禁用分页
            updatePaginationControls(0, 1, 1); // 总项目0, 总页数1, 当前页1
            return;
        }

        data.games.forEach(game => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${game.name || '未知名称'}</td>
                <td><span class="status-tag ${getStatusClass(game.status)}">${game.status || '未知状态'}</span></td>
                <td>${game.date || '未知'}</td>
                <td>${game.platform || '未知'}</td>
                <td>${game.source || '未知'}</td>
                <td>${truncateText(game.description, 100) || '无'}</td>
                <td>${game.rating || '暂无评分'}</td>
                <td>${game.icon_url ? `<img src="${game.icon_url}" alt="${game.name}" width="30" height="30" style="vertical-align: middle;">` : '无'}</td>
                <td>${game.link ? `<a href="${game.link}" target="_blank">链接</a>` : '无'}</td>
            `;
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
        if (lowerStatus.includes('上线') || lowerStatus.includes('公测')) return 'status-online';
        if (lowerStatus.includes('测试')) return 'status-testing';
        if (lowerStatus.includes('预约') || lowerStatus.includes('预订')) return 'status-preorder';
        if (lowerStatus.includes('开发中')) return 'status-dev';
        return 'status-unknown';
    }

    function truncateText(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    // --- 加载全部游戏数据（带过滤和分页）---
    async function loadAllGames() {
        allGamesTbody.innerHTML = '<tr><td colspan="9" class="loading-message">正在加载游戏列表...</td></tr>'; // 显示加载提示
        prevPageButton.disabled = true;
        nextPageButton.disabled = true;

        const params = {
            page: currentPage,
            per_page: perPage,
            search: searchInput.value.trim(),
            status: statusFilter.value,
            source: sourceFilter.value,
            // 如果有 featured 过滤需求，也可以在这里添加
            // featured: document.querySelector('.navbar a.active[data-section="featured"]') ? true : null
        };

        const data = await fetchData('/games', params);
        renderAllGames(data);
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
    loadFeaturedGames(); // 加载重点游戏
    loadAllGames();      // 加载第一页的全部游戏

}); 