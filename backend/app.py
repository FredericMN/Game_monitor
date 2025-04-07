import os
import pandas as pd
import math # 导入 math 模块用于 isnan 判断
from flask import Flask, jsonify # 导入 jsonify
from flask_cors import CORS # 导入 CORS

# --- 配置 --- #
# 获取当前脚本所在的目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Excel 文件的相对路径 (相对于 app.py)
EXCEL_FILE_PATH = os.path.join(BASE_DIR, '..', 'data', 'sample_games.xlsx')

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
    """从 Excel 文件加载游戏数据并处理"""
    try:
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
        print(f"错误：无法找到 Excel 文件：{EXCEL_FILE_PATH}")
        return [] # 或者可以返回一个错误信息
    except Exception as e:
        print(f"读取或处理 Excel 文件时出错: {e}")
        return [] # 或者可以返回一个错误信息


# --- 路由定义 --- #

# 根路由 (用于测试)
@app.route('/')
def home():
    return "后端服务器正在运行！访问 /api/games 获取数据。"

# 游戏数据 API 路由
@app.route('/api/games')
def get_games():
    """返回游戏数据的 JSON 响应"""
    game_data = load_game_data()
    # 使用 jsonify 将 Python 列表/字典转换为 JSON 响应
    return jsonify(game_data)


# --- 应用启动 --- #
if __name__ == '__main__':
    # 可以在这里检查 Excel 文件是否存在
    if not os.path.exists(EXCEL_FILE_PATH):
        print(f"警告：Excel 文件未找到于 {EXCEL_FILE_PATH}。API 可能返回空数据。")

    app.run(host='0.0.0.0', port=5000, debug=True) 