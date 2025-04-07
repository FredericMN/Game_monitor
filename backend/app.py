import os
import json
import pandas as pd
import math # 导入 math 模块用于 isnan 判断
from flask import Flask, jsonify, request # 导入 jsonify 和 request
from flask_cors import CORS # 导入 CORS

# --- 配置 --- #
# 获取当前脚本所在的目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 数据文件路径
DATA_DIR = os.path.join(BASE_DIR, '..', 'data')
JSON_FILE_PATH = os.path.join(DATA_DIR, 'all_games.json')
EXCEL_FILE_PATH = os.path.join(DATA_DIR, 'sample_games.xlsx')

# 创建 Flask 应用实例
app = Flask(__name__)

# --- 启用 CORS --- #
# 最简单的方式：允许所有来源访问所有路由
CORS(app)
# 更精细的控制 (例如只允许特定来源访问特定路由):
# CORS(app, resources={r"/api/*": {"origins": "*"}}) # 允许所有来源访问 /api/ 开头的路由
# CORS(app, resources={r"/api/*": {"origins": ["http://localhost:8000", "http://127.0.0.1:8000"]}}) # 只允许特定来源


# --- 数据加载函数 --- #
def load_game_data():
    """加载游戏数据，优先使用 JSON 数据源，如果不存在则使用 Excel"""
    try:
        # 首先尝试从 JSON 文件加载数据（数据采集脚本生成的结果）
        if os.path.exists(JSON_FILE_PATH):
            print(f"从 JSON 文件加载数据: {JSON_FILE_PATH}")
            with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        
        # 如果 JSON 文件不存在，回退到 Excel 文件
        print(f"JSON 文件不存在，尝试从 Excel 加载数据: {EXCEL_FILE_PATH}")
        # 读取 Excel 文件，指定 sheet_name
        df = pd.read_excel(EXCEL_FILE_PATH, sheet_name='Sheet1')
        # 将 NaN (Not a Number) 值替换为 None，以便 JSON 序列化
        # 转换为字典列表，但 NaN 可能仍然存在
        data = df.to_dict(orient='records')
        # **显式处理 NaN 转换为 None**
        cleaned_data = []
        for row in data:
            cleaned_row = {}
            for key, value in row.items():
                # 检查值是否为 float 类型的 NaN
                if isinstance(value, float) and math.isnan(value):
                    cleaned_row[key] = None
                else:
                    cleaned_row[key] = value
            cleaned_data.append(cleaned_row)
        return cleaned_data
    except FileNotFoundError:
        print(f"错误：无法找到数据文件")
        return [] # 或者可以返回一个错误信息
    except Exception as e:
        print(f"读取或处理数据文件时出错: {e}")
        return [] # 或者可以返回一个错误信息


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
    
    # 获取请求参数
    is_featured = request.args.get('featured', '').lower() in ['true', '1', 'yes']
    status = request.args.get('status', None)
    search = request.args.get('search', None)
    source = request.args.get('source', None)
    page = request.args.get('page', default=1, type=int)
    per_page = request.args.get('per_page', default=50, type=int)
    
    # 根据参数过滤数据
    filtered_data = game_data
    
    # 按是否重点关注过滤
    if is_featured:
        filtered_data = [
            game for game in filtered_data 
            if game.get('is_featured', False) or 
               (game.get('status', '').lower() in ['测试中', '可预约'] and 'is_featured' not in game)
        ]
    
    # 按状态过滤
    if status:
        filtered_data = [
            game for game in filtered_data 
            if status.lower() in game.get('status', '').lower()
        ]
    
    # 按来源过滤
    if source:
        filtered_data = [
            game for game in filtered_data 
            if source.lower() in game.get('source', '').lower()
        ]
    
    # 搜索功能（在名称、分类中搜索）
    if search:
        search = search.lower()
        filtered_data = [
            game for game in filtered_data 
            if (search in game.get('name', '').lower() or 
                search in game.get('category', '').lower())
        ]
    
    # 统计总条目数和页数
    total_items = len(filtered_data)
    total_pages = (total_items + per_page - 1) // per_page  # 向上取整
    
    # 计算分页
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
    """返回重点关注的游戏数据"""
    game_data = load_game_data()
    
    # 筛选重点游戏
    featured_games = [
        game for game in game_data 
        if game.get('is_featured', False) or 
           (game.get('status', '').lower() in ['测试中', '可预约'] and 'is_featured' not in game)
    ]
    
    return jsonify(featured_games)


# --- 应用启动 --- #
if __name__ == '__main__':
    # 检查数据文件是否存在
    if not os.path.exists(JSON_FILE_PATH) and not os.path.exists(EXCEL_FILE_PATH):
        print(f"警告：未找到数据文件。API 可能返回空数据。")

    app.run(host='0.0.0.0', port=5000, debug=True) 