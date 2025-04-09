import os
import json
# import glob # 不再需要 glob
import pandas as pd
# import math # pandas 处理 NaN
import requests
from io import BytesIO
from flask import Flask, jsonify, request, send_file, Response
from flask_cors import CORS
from urllib.parse import urlparse, parse_qs, unquote

# --- 配置 --- #
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, '..', 'data')
# JSON_FILE_PATH = os.path.join(DATA_DIR, 'all_games.json') # 不再使用
EXCEL_FILE_PATH = os.path.join(DATA_DIR, 'all_games_data.xlsx') # 改为 Excel 文件路径

# 创建 Flask 应用实例
app = Flask(__name__)

# --- 启用 CORS --- #
CORS(app)

# --- 数据加载函数 (修改后) --- #
def load_game_data():
    """加载游戏数据，从 data/all_games_data.xlsx 文件读取，并包含所有指定列"""
    all_games = []
    if not os.path.exists(EXCEL_FILE_PATH):
        print(f"警告: 在路径 {EXCEL_FILE_PATH} 未找到 Excel 数据文件。")
        return []

    print(f"正在从文件加载数据: {EXCEL_FILE_PATH}")
    try:
        # 读取 Excel 文件，可以指定需要读取的列以提高效率，如果列很多的话
        # usecols = ['名称', '日期', ..., '是否人工校对'] # 可以定义一个列表
        # df = pd.read_excel(EXCEL_FILE_PATH, engine='openpyxl', usecols=usecols)
        df = pd.read_excel(EXCEL_FILE_PATH, engine='openpyxl') # 暂时读取所有列

        # 将 NaN 值替换为 None
        df = df.where(pd.notnull(df), None)

        # 将 DataFrame 转换为字典列表，并进行键名映射和处理
        for index, row in df.iterrows():
            # --- 基本信息 --- #
            name = row.get('名称')
            date = str(row.get('日期')) if pd.notna(row.get('日期')) else None
            status = row.get('状态')
            platform = row.get('平台')
            category = row.get('分类')
            publisher = row.get('厂商')
            source = row.get('来源')
            link = row.get('链接')
            icon_url = row.get('图标')
            description = row.get('简介')

            # --- 评分处理 (尝试转为 float) --- #
            score_raw = row.get('评分')
            score = None
            if pd.notna(score_raw):
                try:
                    score = float(score_raw)
                except (ValueError, TypeError):
                    print(f"警告: 无法将评分 '{score_raw}' (行 {index + 2}) 转换为浮点数。将设置为 None。")
                    score = None # 转换失败则设为 None

            # --- 是否重点处理 (布尔值) --- #
            is_featured_raw = row.get('是否重点')
            # 检查是否非空、非 NaN，并且不是明确的否定词（如果需要的话）
            is_featured = pd.notna(is_featured_raw) and str(is_featured_raw).strip() not in ['', '0', '否', 'False', 'false']

            # --- 版号相关信息 --- #
            license_checked = row.get('版号已查')
            license_name = row.get('版号名称')
            approval_number = row.get('批准文号')
            publication_number = row.get('出版物号')
            approval_date = str(row.get('批准日期')) if pd.notna(row.get('批准日期')) else None
            publishing_unit = row.get('出版单位')
            operating_unit = row.get('运营单位')
            license_game_type = row.get('版号游戏类型')
            application_category = row.get('申报类别')
            license_multiple_results = row.get('版号多结果')

            # --- 其他信息 --- #
            manual_checked_raw = row.get('是否人工校对')
            manual_checked = pd.notna(manual_checked_raw) and str(manual_checked_raw).strip().lower() in ['是', 'true', '1', 'yes']

            game_data = {
                'id': index, # 使用行索引作为临时 ID
                # 基础信息
                'name': name,
                'date': date,
                'status': status,
                'platform': platform,
                'category': category,
                'score': score, # 评分
                'publisher': publisher,
                'source': source,
                'is_featured': is_featured, # 是否重点
                'link': link,
                'icon_url': icon_url,
                'description': description,
                # 版号信息
                'license_checked': license_checked,
                'license_name': license_name,
                'approval_number': approval_number,
                'publication_number': publication_number,
                'approval_date': approval_date,
                'publishing_unit': publishing_unit,
                'operating_unit': operating_unit,
                'license_game_type': license_game_type,
                'application_category': application_category,
                'license_multiple_results': license_multiple_results,
                # 其他
                'manual_checked': manual_checked # 是否人工校对
            }
            all_games.append(game_data)

    except FileNotFoundError:
        print(f"错误：找不到 Excel 文件 {EXCEL_FILE_PATH}")
    except ImportError:
        print("错误：需要安装 'openpyxl' 库来读取 .xlsx 文件。请运行 pip install openpyxl")
        return []
    except Exception as e:
        print(f"读取或处理 Excel 文件 {EXCEL_FILE_PATH} 时发生意外错误: {e}")
        import traceback
        traceback.print_exc() # 打印详细错误信息

    print(f"总共从 Excel 文件加载了 {len(all_games)} 条游戏数据，包含扩展列。")
    return all_games

# --- 路由定义 --- #

# 根路由 (用于测试)
@app.route('/')
def home():
    return "后端服务器正在运行！访问 /api/games 获取数据。"

# 游戏数据 API 路由
@app.route('/api/games')
def get_games():
    """返回游戏数据的 JSON 响应，支持过滤和分页"""
    game_data = load_game_data()
    if not game_data:
         return jsonify({'games': [], 'pagination': {'total_items': 0, 'total_pages': 1, 'current_page': 1, 'per_page': 15}})

    # 获取请求参数
    is_featured_query = request.args.get('featured', '').lower() in ['true', '1', 'yes']
    status = request.args.get('status', None)
    search = request.args.get('search', None)
    source = request.args.get('source', None)
    publisher_filter = request.args.get('publisher', None) # 新增厂商过滤参数
    platform_filter = request.args.get('platform', None)
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=15, type=int)

    # 根据参数过滤数据
    filtered_data = game_data

    # 按是否重点关注过滤
    if is_featured_query:
        filtered_data = [game for game in filtered_data if game.get('is_featured', False)]

    # 按状态过滤
    if status:
        filtered_data = [
            game for game in filtered_data
            if game.get('status') and status.lower() in str(game.get('status', '')).lower()
        ]

    # 按来源过滤
    if source:
        filtered_data = [
            game for game in filtered_data
            if game.get('source') and source.lower() in str(game.get('source', '')).lower()
        ]

    # 新增：按厂商过滤 (处理特殊值 TWM)
    if publisher_filter:
        target_publishers = []
        if publisher_filter == 'TENCENT,NETEASE,MIHOYO': # 特殊值处理
            target_publishers = ['腾讯', 'tencent', '网易', 'netease', '米哈游', 'mihoyo']
            print(f"Filtering for TWM publishers: {target_publishers}")
            filtered_data = [
                game for game in filtered_data
                if game.get('publisher') and any(p.lower() in str(game.get('publisher', '')).lower() for p in target_publishers)
            ]
        else:
            # 普通厂商名称过滤
            target_publishers = [publisher_filter.lower()]
            print(f"Filtering for publisher: {publisher_filter}")
            filtered_data = [
                game for game in filtered_data
                if game.get('publisher') and publisher_filter.lower() in str(game.get('publisher', '')).lower()
            ]

    # 按平台过滤
    if platform_filter:
        filtered_data = [
            game for game in filtered_data
            if game.get('platform') and platform_filter.lower() in str(game.get('platform', '')).lower()
        ]

    # 搜索功能
    if search:
        search_lower = search.lower()
        filtered_data = [
            game for game in filtered_data
            if (search_lower in str(game.get('name', '')).lower() or
                search_lower in str(game.get('category', '')).lower() or
                search_lower in str(game.get('publisher', '')).lower() or
                search_lower in str(game.get('platform', '')).lower())
        ]

    # 排序 (可选，例如按日期降序)
    # try:
    #     # 假设 date 字段是 'YYYY-MM-DD' 或类似格式
    #     filtered_data.sort(key=lambda g: str(g.get('date', '1970-01-01')), reverse=True)
    # except Exception as sort_e:
    #     print(f"排序时出错: {sort_e}")

    # 统计总条目数和页数
    total_items = len(filtered_data)
    total_pages = max(1, (total_items + per_page - 1) // per_page)

    # 计算分页
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * per_page
    end_idx = min(start_idx + per_page, total_items)

    # 获取当前页的数据
    paged_data = filtered_data[start_idx:end_idx]

    # 构建响应
    response = {
        'games': paged_data,
        'pagination': {
            'total_items': total_items,
            'total_pages': total_pages,
            'current_page': page,
            'per_page': per_page
        }
    }

    return jsonify(response)

# 重点游戏 API 路由
@app.route('/api/featured-games')
def get_featured_games():
    """返回重点关注的游戏数据 (基于 Excel 的 is_featured 字段)"""
    game_data = load_game_data()
    if not game_data:
        return jsonify([])

    featured_games = [
        game for game in game_data
        if game.get('is_featured', False)
    ]
    # print(f"Returning {len(featured_games)} featured games from /api/featured-games endpoint.")

    # 可以考虑在这里限制返回数量或排序
    # featured_games.sort(key=lambda g: str(g.get('date', '1970-01-01')), reverse=True)
    # featured_games = featured_games[:16]

    return jsonify(featured_games)

# --- 图片代理路由 (修改后，处理嵌套 URL) --- #
@app.route('/api/image')
def proxy_image():
    """代理获取外部图片 URL，尝试处理嵌套的代理 URL"""
    image_url_initial = request.args.get('url')
    if not image_url_initial:
        return "Missing image URL", 400

    print(f"收到代理请求 URL: {image_url_initial}") # Log initial URL

    image_url = image_url_initial # Start with the initial URL

    # --- 尝试解析嵌套 URL ---
    try:
        # 检查是否是已知的嵌套代理格式 (例如 img.16p.com)
        parsed_initial = urlparse(image_url_initial)
        if parsed_initial.netloc == 'img.16p.com' and parsed_initial.path.startswith('/img_proxy'):
            print("检测到 img.16p.com 嵌套代理 URL...")
            query_params = parse_qs(parsed_initial.query)
            nested_url_list = query_params.get('url') # parse_qs returns a list
            if nested_url_list and nested_url_list[0]:
                # 提取并解码嵌套的 URL
                extracted_url = unquote(nested_url_list[0])
                print(f"  提取到的嵌套 URL: {extracted_url}")
                # 验证提取的 URL 是否看起来像一个有效的 HTTP/HTTPS URL
                if extracted_url.lower().startswith(('http://', 'https://')):
                    image_url = extracted_url # 使用提取到的 URL 进行后续操作
                else:
                    print(f"  警告: 提取到的嵌套 URL '{extracted_url}' 格式无效，将继续使用原始 URL。")
            else:
                print("  警告: 未能在 img.16p.com 代理 URL 中找到有效的嵌套 'url' 参数。")

        # 在这里可以添加对其他已知代理格式的检查 (elif ...)

    except Exception as e:
        print(f"解析嵌套 URL 时出错: {e}，将继续使用原始 URL: {image_url_initial}")
        # 出错时，回退到使用原始 URL

    # --- 后续处理使用最终确定的 image_url ---
    print(f"最终处理的图片 URL: {image_url}")

    # 如果最终 URL 仍然是嵌套代理格式（例如解析失败或非已知格式），后续请求可能会失败
    # 但我们还是尝试请求
    if not image_url or not image_url.lower().startswith(('http://', 'https://')):
         print(f"错误: 最终图片 URL 无效: {image_url}")
         return "Invalid final image URL", 400


    try:
        # 根据图片URL的域名选择适当的Referer
        referer = 'https://www.google.com/' # 通用 Referer
        # 对最终确定的 image_url 判断来源
        if 'taptap.cn' in image_url or 'tapimg.com' in image_url:
            referer = 'https://www.taptap.cn/'
        elif 'biligame.com' in image_url or 'hdslb.com' in image_url:
             referer = 'https://www.biligame.com/'
        elif '71acg.net' in image_url: # 为新发现的域名添加 Referer (可选，可能不需要)
             referer = 'https://www.71acg.net/' # 或者一个更通用的 Referer

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36',
            'Referer': referer,
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }

        if image_url.startswith('//'):
            image_url = 'https:' + image_url

        response = requests.get(image_url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()

        content_type = response.headers.get('Content-Type', 'image/jpeg')

        if not content_type.startswith('image/'):
             if image_url.lower().endswith('.png'): content_type = 'image/png'
             elif image_url.lower().endswith(('.jpg', '.jpeg')): content_type = 'image/jpeg'
             elif image_url.lower().endswith('.gif'): content_type = 'image/gif'
             elif image_url.lower().endswith('.webp'): content_type = 'image/webp'
             else: content_type = 'image/jpeg'

        image_data = BytesIO(response.content)

        resp = send_file(image_data, mimetype=content_type)
        resp.headers['Cache-Control'] = 'public, max-age=86400'
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp

    except requests.exceptions.Timeout:
        print(f"代理请求超时: {image_url}")
        return "Image request timed out", 408
    except requests.exceptions.RequestException as e:
        print(f"代理请求失败 ({type(e).__name__}): {e} for URL: {image_url}")
        transparent_pixel = b'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
        resp = Response(transparent_pixel, mimetype='image/gif')
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp, 404

    except Exception as e:
        print(f"处理代理请求时发生未知错误: {e}")
        return "Internal server error: " + str(e), 500


# --- 应用启动 --- #
if __name__ == '__main__':
    # 检查数据文件是否存在
    if not os.path.exists(EXCEL_FILE_PATH):
        print(f"警告：未找到数据文件 {EXCEL_FILE_PATH}。API 将返回空数据。请确保文件存在于 data 目录中。")
        print("如果需要安装 openpyxl 库，请运行: pip install openpyxl")

    print("启动 Flask 开发服务器...")
    # host='0.0.0.0' 允许从网络中的其他设备访问
    app.run(host='0.0.0.0', port=5000, debug=True) 