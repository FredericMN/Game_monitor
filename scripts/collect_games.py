# collect_games.py
# 整合多个数据源的游戏信息

import os
import json
import time
import shutil
from datetime import datetime
import importlib.util
import sys

# 添加 scripts 目录到 Python 路径
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
data_dir = os.path.join(root_dir, 'data')
os.makedirs(data_dir, exist_ok=True)

# 将 scripts 目录添加到 Python 路径
if script_dir not in sys.path:
    sys.path.append(script_dir)

# 导入抓取脚本
from taptap_selenium import get_taptap_daily_games, save_to_json
from haoyou_selenium import get_haoyou_games

def standardize_game_data(games):
    """
    标准化游戏数据，确保字段统一
    
    参数:
        games (list): 游戏数据列表
        
    返回:
        list: 标准化后的游戏数据列表
    """
    standardized_games = []
    
    for game in games:
        # 基本字段标准化
        std_game = {
            "name": game.get("name", "未知游戏"),
            "link": game.get("link", ""),
            "status": standardize_status(game.get("status", "未知状态")),
            "rating": extract_rating_value(game.get("rating", "暂无评分")),
            "category": game.get("category", "未知分类"),
            "icon_url": game.get("icon_url", ""),
            "source": game.get("source", "未知来源"),
            "date": game.get("date", datetime.now().strftime("%Y-%m-%d")),
            # 添加一个字段，用于前端标记是否为"重点关注"
            "is_featured": is_featured_game(game)
        }
        
        standardized_games.append(std_game)
    
    return standardized_games

def standardize_status(status):
    """
    标准化游戏状态
    
    参数:
        status (str): 原始状态描述
        
    返回:
        str: 标准化后的状态
    """
    status = status.lower()
    
    # 测试相关状态
    if any(keyword in status for keyword in ["测试", "test", "beta"]):
        return "测试中"
    
    # 预约相关状态
    if any(keyword in status for keyword in ["预约", "预定", "pre"]):
        return "可预约"
    
    # 已发布状态
    if any(keyword in status for keyword in ["发布", "上线", "已上线", "公测", "首发"]):
        return "已上线"
    
    # 未知或其他状态保留原样
    return status

def extract_rating_value(rating_text):
    """
    从评分文本中提取数值
    
    参数:
        rating_text (str): 评分文本，如 "9.4分"
        
    返回:
        float: 评分数值
    """
    import re
    
    # 尝试从文本中提取数字
    match = re.search(r'(\d+\.\d+|\d+)', rating_text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    
    return 0.0

def is_featured_game(game):
    """
    判断游戏是否为"重点关注"
    
    参数:
        game (dict): 游戏信息
        
    返回:
        bool: 是否为重点关注游戏
    """
    # 检查游戏状态
    status = game.get("status", "").lower()
    if any(keyword in status for keyword in ["测试", "test", "beta", "预约", "预定"]):
        return True
    
    # 检查评分是否很高
    rating = extract_rating_value(game.get("rating", "0"))
    if rating >= 9.0:
        return True
    
    # 检查是否为特定分类的游戏
    category = game.get("category", "").lower()
    featured_categories = ["角色扮演", "rpg", "动作", "action", "mmorpg", "开放世界"]
    if any(keyword in category for keyword in featured_categories):
        return True
    
    return False

def backup_existing_data():
    """
    备份现有的游戏数据
    """
    source_file = os.path.join(data_dir, "all_games.json")
    if os.path.exists(source_file):
        # 创建备份文件名，包含时间戳
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_file = os.path.join(data_dir, f"all_games_backup_{timestamp}.json")
        
        # 复制文件
        shutil.copy2(source_file, backup_file)
        print(f"已将现有游戏数据备份到 {backup_file}")

def copy_to_excel_file():
    """
    将收集到的数据复制到 sample_games.xlsx 文件
    (这里只是占位，实际实现需要使用 pandas 导出数据到 Excel)
    """
    import pandas as pd
    
    # 读取JSON数据
    json_file = os.path.join(data_dir, "all_games.json")
    if not os.path.exists(json_file):
        print("未找到游戏数据，无法导出到 Excel")
        return
    
    with open(json_file, 'r', encoding='utf-8') as f:
        games = json.load(f)
    
    # 将数据转换为 DataFrame
    df = pd.DataFrame(games)
    
    # 设置列顺序和重命名列（根据需要调整）
    columns = {
        "name": "名称",
        "category": "分类",
        "status": "状态",
        "rating": "评分",
        "source": "来源",
        "date": "日期",
        "is_featured": "是否重点",
        "link": "链接",
        "icon_url": "图标"
    }
    
    # 重新排序和重命名列
    df = df.rename(columns=columns)
    df = df[[col for col in columns.values() if col in df.columns]]
    
    # 保存到 Excel 文件
    excel_file = os.path.join(data_dir, "sample_games.xlsx")
    df.to_excel(excel_file, index=False)
    print(f"游戏数据已导出到 Excel 文件: {excel_file}")

def collect_all_game_data():
    """收集所有数据源的游戏信息"""
    all_games = []
    log_lines = []
    
    # 记录开始时间
    start_time = time.time()
    log_lines.append(f"开始收集游戏数据: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 备份现有数据
    backup_existing_data()
    
    # TapTap 数据源
    try:
        log_lines.append("\n-------------- TapTap 数据源 --------------")
        # 尝试多个 TapTap 相关页面
        taptap_urls = [
            "https://www.taptap.cn/app-calendar/2025-04-07",
            "https://www.taptap.cn/top/download",  # 热门榜单页面
            "https://www.taptap.cn/mobile"         # 首页
        ]
        
        taptap_games = []
        for url in taptap_urls:
            log_lines.append(f"正在从 {url} 获取数据...")
            games = get_taptap_daily_games(url)
            
            if games:
                log_lines.append(f"成功获取 {len(games)} 个 TapTap 游戏信息")
                taptap_games.extend(games)
                break  # 成功获取数据后退出循环
        
        if taptap_games:
            log_lines.append(f"总共从 TapTap 获取了 {len(taptap_games)} 个游戏信息")
            standardized_taptap_games = standardize_game_data(taptap_games)
            save_to_json(standardized_taptap_games, "taptap_games.json")
            
            # 将游戏添加到总列表
            all_games.extend(standardized_taptap_games)
        else:
            log_lines.append("未获取到 TapTap 游戏数据")
    except Exception as e:
        log_lines.append(f"获取 TapTap 数据时出错: {e}")
    
    # 好游快爆数据源
    try:
        log_lines.append("\n-------------- 好游快爆数据源 --------------")
        haoyou_url = "https://www.3839.com/top/hot.html"
        log_lines.append(f"正在从 {haoyou_url} 获取数据...")
        
        haoyou_games = get_haoyou_games(haoyou_url)
        
        if haoyou_games:
            log_lines.append(f"成功获取 {len(haoyou_games)} 个好游快爆游戏信息")
            standardized_haoyou_games = standardize_game_data(haoyou_games)
            save_to_json(standardized_haoyou_games, "haoyou_games.json")
            
            # 将游戏添加到总列表
            all_games.extend(standardized_haoyou_games)
        else:
            log_lines.append("未获取到好游快爆游戏数据")
    except Exception as e:
        log_lines.append(f"获取好游快爆数据时出错: {e}")
    
    # 检查是否获取到游戏数据
    if all_games:
        # 去重处理
        unique_games = remove_duplicates(all_games)
        log_lines.append(f"\n总共收集了 {len(all_games)} 个游戏信息，去重后剩余 {len(unique_games)} 个")
        
        # 保存汇总的游戏数据
        output_file = "all_games.json"
        output_path = os.path.join(data_dir, output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(unique_games, f, ensure_ascii=False, indent=2)
        log_lines.append(f"所有游戏数据已保存到 {output_path}")
        
        # 复制到 Excel 文件
        try:
            copy_to_excel_file()
            log_lines.append("已将数据导出到 Excel 文件")
        except Exception as e:
            log_lines.append(f"导出到 Excel 文件时出错: {e}")
    else:
        log_lines.append("\n未获取到任何游戏数据")
    
    # 记录结束时间
    elapsed_time = time.time() - start_time
    log_lines.append(f"\n数据收集完成，耗时: {elapsed_time:.2f} 秒")
    
    # 保存日志
    log_file = os.path.join(data_dir, "collect_log.txt")
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(log_lines))
    
    print("\n".join(log_lines))
    print(f"\n日志已保存到 {log_file}")
    
    return all_games

def remove_duplicates(games):
    """
    去除重复的游戏数据
    
    参数:
        games (list): 游戏数据列表
        
    返回:
        list: 去重后的游戏数据列表
    """
    # 使用游戏名称作为唯一标识
    unique_games = {}
    
    for game in games:
        name = game.get("name")
        if name in unique_games:
            # 如果已存在，根据优先级规则决定是否替换
            # 1. 评分更高的优先
            # 2. 状态为"测试中"或"可预约"的优先
            # 3. TapTap 来源优先于其他来源
            existing_game = unique_games[name]
            
            # 替换条件
            should_replace = False
            
            # 评分比较
            if game.get("rating", 0) > existing_game.get("rating", 0) + 0.5:  # 评分高 0.5 以上才替换
                should_replace = True
            # 状态比较
            elif game.get("status") in ["测试中", "可预约"] and existing_game.get("status") not in ["测试中", "可预约"]:
                should_replace = True
            # 来源比较
            elif game.get("source") == "TapTap" and existing_game.get("source") != "TapTap":
                should_replace = True
            
            if should_replace:
                unique_games[name] = game
        else:
            # 新游戏，直接添加
            unique_games[name] = game
    
    return list(unique_games.values())

if __name__ == "__main__":
    collect_all_game_data() 