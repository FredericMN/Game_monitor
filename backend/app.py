import os
import json
import glob # 导入 glob 用于查找文件
import pandas as pd
import math # 导入 math 模块用于 isnan 判断
from flask import Flask, jsonify, request # 导入 jsonify 和 request
from flask_cors import CORS # 导入 CORS

# --- 配置 --- #
# 获取当前脚本所在的目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 数据文件路径
DATA_DIR = os.path.join(BASE_DIR, '..', 'data')
# JSON_FILE_PATH = os.path.join(DATA_DIR, 'all_games.json') # 不再使用
# EXCEL_FILE_PATH = os.path.join(DATA_DIR, 'sample_games.xlsx') # 不再使用

# 创建 Flask 应用实例
app = Flask(__name__)

# --- 启用 CORS --- #
# 最简单的方式：允许所有来源访问所有路由
CORS(app)
# 更精细的控制 (例如只允许特定来源访问特定路由):
# CORS(app, resources={r"/api/*": {"origins": "*"}}) # 允许所有来源访问 /api/ 开头的路由
# CORS(app, resources={r"/api/*": {"origins": ["http://localhost:8000", "http://127.0.0.1:8000"]}}) # 只允许特定来源


# --- 数据加载函数 (修改后) --- #
def load_game_data():
    """加载游戏数据，从 data/ 目录下所有 .jsonl 文件读取"""
    all_games = []
    jsonl_files = glob.glob(os.path.join(DATA_DIR, '*.jsonl')) # 查找所有 .jsonl 文件

    if not jsonl_files:
        print(f"警告: 在目录 {DATA_DIR} 中未找到任何 .jsonl 文件。")
        return []

    print(f"找到以下 .jsonl 文件: {jsonl_files}")

    for filepath in jsonl_files:
        print(f"正在从文件加载数据: {filepath}")
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f):
                    line = line.strip()
                    if not line: # 跳过空行
                        continue
                    try:
                        game_data = json.loads(line)
                        # 可以在这里添加一些数据清洗或验证逻辑，例如确保关键字段存在
                        all_games.append(game_data)
                    except json.JSONDecodeError as json_err:
                        print(f"  警告: 解析文件 {filepath} 第 {line_num + 1} 行时出错: {json_err}")
                        print(f"    问题行内容: {line[:100]}...") # 打印部分问题行内容
        except FileNotFoundError:
            print(f"错误：尝试读取文件时找不到 {filepath} (可能在查找后被删除？)")
        except Exception as e:
            print(f"读取或处理文件 {filepath} 时发生意外错误: {e}")

    print(f"总共从 {len(jsonl_files)} 个文件加载了 {len(all_games)} 条游戏数据。")
    # 可选：去重（如果不同文件可能有相同游戏，基于 link 或 name+publisher 等）
    # unique_games = {game.get('link', '') or f"{game.get('name', '')}-{game.get('publisher', '')}": game for game in all_games}.values()
    # print(f"去重后剩余 {len(unique_games)} 条数据。")
    # return list(unique_games)
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
               (game.get('status', '').lower() in ['测试中', '可预约', '测试招募', '新游预约'] and 'is_featured' not in game) # 调整判断逻辑以适应 TapTap 状态
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
    
    # 筛选重点游戏 (调整判断逻辑以适应 TapTap 状态)
    featured_games = [
        game for game in game_data 
        if game.get('is_featured', False) or 
           (game.get('status', '').lower() in ['测试中', '可预约', '测试招募', '新游预约'] and 'is_featured' not in game)
    ]
    
    return jsonify(featured_games)


# --- 应用启动 --- #
if __name__ == '__main__':
    # 检查数据目录是否存在
    if not os.path.exists(DATA_DIR) or not glob.glob(os.path.join(DATA_DIR, '*.jsonl')):
        print(f"警告：未找到数据目录或目录中没有 .jsonl 文件。API 可能返回空数据。")

    app.run(host='0.0.0.0', port=5000, debug=True) 