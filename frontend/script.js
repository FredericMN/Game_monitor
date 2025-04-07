// 等待 DOM 内容完全加载完成后执行
document.addEventListener('DOMContentLoaded', () => {
    const topGamesList = document.querySelector('.top-games .game-list');
    const allGamesTableBody = document.querySelector('.all-games-table .styled-table tbody');

    // --- 函数：获取状态标签的 CSS 类 --- //
    function getStatusClass(status) {
        if (!status) return ''; // 处理空状态
        status = status.toLowerCase(); // 转换为小写以方便匹配
        if (status.includes('上线')) {
            return 'status-online';
        } else if (status.includes('测试') || status.includes('封测') || status.includes('内测')) {
            return 'status-testing';
        } else if (status.includes('开发') || status.includes('预告')) {
            return 'status-dev';
        } else if (status.includes('预约')) {
            return 'status-preorder';
        } else if (status.includes('更新')) {
            return 'status-update';
        } else {
            return 'status-other'; // 可以为其他状态定义一个默认样式
        }
    }

    // --- 函数：创建游戏卡片的 HTML --- //
    function createGameCardHTML(game) {
        // 处理可能的 null 值，显示为空字符串或默认值
        const name = game['游戏名称'] || '未知游戏';
        const status = game['状态'] || '未知';
        const time = game['预计时间'] || game['日期'] || '未知时间'; // 优先用预计时间，否则用日期
        const platform = game['平台'] || '未知';
        const description = game['游戏简介'] || '暂无简介';
        const statusClass = getStatusClass(status);

        return `
            <div class="game-card">
                <h3>${name}</h3>
                <p><span class="label">状态/计划:</span> <span class="status-tag ${statusClass}">${status}</span></p>
                <p><span class="label">时间:</span> ${time}</p>
                <p><span class="label">平台:</span> ${platform}</p>
                <p><span class="label">简介:</span> ${description}</p>
            </div>
        `;
    }

    // --- 函数：创建表格行的 HTML --- //
    function createGameTableRowHTML(game) {
        const name = game['游戏名称'] || '未知游戏';
        const status = game['状态'] || '未知';
        const time = game['预计时间'] || game['日期'] || '未知时间';
        const platform = game['平台'] || '未知';
        const description = game['游戏简介'] || '暂无简介';
        const statusClass = getStatusClass(status);

        // 注意：表格列顺序应与 HTML 中 thead 的列顺序一致
        return `
            <tr>
                <td>${name}</td>
                <td><span class="status-tag ${statusClass}">${status}</span></td>
                <td>${time}</td>
                <td>${platform}</td>
                <td>${description}</td>
            </tr>
        `;
    }

    // --- 获取并渲染数据 --- //
    // 使用完整的后端 API 地址
    const apiUrl = 'http://127.0.0.1:5000/api/games';
    // 或者 const apiUrl = 'http://localhost:5000/api/games';

    fetch(apiUrl) // 向完整的后端 API 地址发送请求
        .then(response => {
            if (!response.ok) { // 检查响应是否成功
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json(); // 解析 JSON 数据
        })
        .then(data => {
            // 清空现有的示例内容 (如果容器存在)
            if (topGamesList) topGamesList.innerHTML = '';
            if (allGamesTableBody) allGamesTableBody.innerHTML = '';

            // 渲染重点关注区域 (最多 8 个)
            const topGames = data.slice(0, 8);
            topGames.forEach(game => {
                if (topGamesList) {
                    topGamesList.innerHTML += createGameCardHTML(game);
                }
            });

            // 渲染全部游戏列表
            data.forEach(game => {
                if (allGamesTableBody) {
                    allGamesTableBody.innerHTML += createGameTableRowHTML(game);
                }
            });
        })
        .catch(error => {
            console.error('获取或处理游戏数据时出错:', error);
            // 可以在页面上显示错误信息给用户
            if (topGamesList) topGamesList.innerHTML = '<p style="color: red;">加载重点游戏失败。</p>';
            if (allGamesTableBody) allGamesTableBody.innerHTML = '<tr><td colspan="5" style="color: red; text-align: center;">加载游戏列表失败。</td></tr>';
        });
}); 