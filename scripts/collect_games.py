# collect_games.py
# 整合多个数据源的游戏信息

import os
import json
import time
import re
import sys
from datetime import datetime
import pandas as pd
import logging

# --- 配置日志 ---
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_filename = os.path.join(log_dir, f'collect_games_{datetime.now().strftime("%Y%m%d")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout) # 同时输出到控制台
    ]
)

# --- 动态导入爬虫和匹配器模块 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
data_dir = os.path.join(root_dir, 'data')
os.makedirs(data_dir, exist_ok=True)

# 将 scripts 目录添加到 Python 路径，以便导入
if script_dir not in sys.path:
    sys.path.append(script_dir)

try:
    # 假设 taptap_selenium.py 有一个名为 get_taptap_games_for_date 的函数获取数据
    from taptap_selenium import get_taptap_games_for_date # 使用具体函数名
    logging.info("成功导入 taptap_selenium 模块。")
except ImportError as e:
    logging.error(f"导入 taptap_selenium 失败: {e}")
    get_taptap_games_for_date = None # 设置为 None，稍后检查

try:
    # 假设 16p_selenium.py 有一个名为 get_16p_data 的函数获取数据
    # 注意 get_16p_data 通常在 16p_selenium.py 文件里
    from p16_selenium import get_16p_data # 假设文件名为 p16_selenium.py
    logging.info("成功导入 p16_selenium 模块。")
except ImportError as e:
    # 尝试另一个常见命名
    try:
        from sixteenp_selenium import get_16p_data # 修正: 尝试 16p_selenium
        logging.info("成功导入 16p_selenium 模块。")
    except ImportError as e2:
        logging.error(f"导入 16p_selenium/p16_selenium 失败: {e} / {e2}")
        get_16p_data = None

try:
    from version_matcher import match_version_numbers_for_games
    logging.info("成功导入 version_matcher 模块。")
except ImportError as e:
    logging.error(f"导入 version_matcher 失败: {e}")
    match_version_numbers_for_games = None

# --- 游戏名称清洗 ---
def clean_game_name(name):
    """清理游戏名称，移除常见的宣传后缀和括号内容"""
    if not name:
        return "未知名称"
    # 移除括号及其内容（中文和英文）
    cleaned = re.sub(r'[（(].*?[)）]', '', name)
    # 移除末尾的 - xxx, – xxx, — xxx
    cleaned = re.sub(r'[-–—]\s*[^-\s]+$', '', cleaned)
    # 移除可能残留的前后空格
    cleaned = cleaned.strip()
    # 如果清理后为空，返回原始名称或标记
    return cleaned if cleaned else name

# --- 数据标准化 ---
def standardize_game_data(games_list):
    """标准化游戏数据，确保字段统一，处理版号信息"""
    standardized_games = []
    # 定义所有期望的字段，包括版号信息
    expected_fields = [
        "name", "date", "status", "platform", "category", "rating",
        "publisher", "source", "is_featured", "link", "icon_url", "description",
        "version_checked", "approval_num", "publication_num", "approval_date",
        "publisher_unit", "operator_unit", "game_type_version", # 注意字段名统一
        "declaration_category", "multiple_results"
    ]

    for game in games_list:
        std_game = {}
        # 优先使用清洗后的 name
        std_game["name"] = game.get("cleaned_name") or game.get("name", "未知名称")

        # 处理基本字段
        std_game["date"] = game.get("date", datetime.now().strftime("%Y-%m-%d"))
        std_game["status"] = standardize_status(game.get("status", "未知状态"))
        std_game["platform"] = game.get("platform", "未知平台")
        std_game["category"] = game.get("category", "未知分类")
        std_game["rating"] = extract_rating_value(game.get("rating", "暂无评分"))
        std_game["publisher"] = game.get("publisher", "未知厂商")
        std_game["source"] = game.get("source", "未知来源")
        std_game["link"] = game.get("link", "")
        std_game["icon_url"] = game.get("icon_url", "")
        std_game["description"] = game.get("description", "")

        # 处理 is_featured (如果需要，可以调用 is_featured_game 函数)
        std_game["is_featured"] = game.get("is_featured", False) # 默认为 False

        # 处理版号相关字段，提供默认值
        std_game["version_checked"] = game.get("version_checked", False)
        std_game["approval_num"] = game.get("approval_num", "")
        std_game["publication_num"] = game.get("publication_num", "")
        std_game["approval_date"] = game.get("approval_date", "")
        std_game["publisher_unit"] = game.get("publisher_unit", "")
        std_game["operator_unit"] = game.get("operator_unit", "")
        # 确保使用统一的字段名 game_type_version
        std_game["game_type_version"] = game.get("game_type_version") or game.get("game_type", "") # 兼容 version_matcher 可能用的 game_type
        std_game["declaration_category"] = game.get("declaration_category", "")
        std_game["multiple_results"] = game.get("multiple_results", "") # 通常是 '是'/'否' 或布尔值，统一为字符串

        # 确保所有预期字段都存在
        for field in expected_fields:
            if field not in std_game:
                # 根据字段类型设置合适的默认值
                if field in ["rating"]:
                     std_game[field] = 0.0
                elif field in ["is_featured", "version_checked", "multiple_results"]: # multiple_results 也可用 False
                     std_game[field] = False # 统一用布尔值
                else:
                     std_game[field] = "" # 其他默认为空字符串

        standardized_games.append(std_game)

    return standardized_games

def standardize_status(status):
    """标准化游戏状态 (保持和之前一致)"""
    if not isinstance(status, str): status = str(status) # 确保是字符串
    status_lower = status.lower()
    if any(keyword in status_lower for keyword in ["测试", "test", "beta", "限量", "不删档", "删档"]):
        return "测试中"
    if any(keyword in status_lower for keyword in ["预约", "预定", "pre", "待上线", "即将上线"]):
        return "可预约"
    if any(keyword in status_lower for keyword in ["发布", "上线", "已上线", "公测", "首发", "更新", "新版本"]):
        return "已上线"
    return status # 保留无法识别的状态

def extract_rating_value(rating_text):
    """从评分文本中提取数值 (保持和之前一致)"""
    if isinstance(rating_text, (int, float)): return float(rating_text)
    if not isinstance(rating_text, str): return 0.0

    match = re.search(r'(\d+\.\d+|\d+)', rating_text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 0.0

# (如果需要 is_featured 逻辑，可以在这里定义)
# def is_featured_game(game): ...

# --- 主流程 ---
def collect_all_game_data():
    """收集、清洗、匹配、合并、保存所有游戏数据"""
    start_time = time.time()
    logging.info("="*20 + " 开始执行游戏数据收集任务 " + "="*20)

    # 1. 加载历史数据
    history_file = os.path.join(data_dir, "all_games.json")
    existing_games = []
    if os.path.exists(history_file):
        try:
            with open(history_file, 'r', encoding='utf-8') as f:
                existing_games = json.load(f)
            logging.info(f"成功从 {history_file} 加载 {len(existing_games)} 条历史数据。")
        except json.JSONDecodeError:
            logging.error(f"历史数据文件 {history_file} 格式错误，将作为空数据处理。")
        except Exception as e:
            logging.error(f"加载历史数据时出错: {e}")

    # 2. 获取新数据
    newly_fetched_games = []
    current_date_str = datetime.now().strftime("%Y-%m-%d") # 获取当天的日期用于 TapTap

    # TapTap 数据源
    if get_taptap_games_for_date:
        logging.info("--- 开始获取 TapTap 数据 ---")
        try:
            # 假设 get_taptap_games_for_date 需要一个日期参数
            # 你可能需要调整这里以适应你 taptap 脚本的实际调用方式
            # 例如，如果你想获取多天的数据，需要循环调用
            taptap_new_count = get_taptap_games_for_date(current_date_str) # 获取当天的数据
            if taptap_new_count > 0: # 注意：这里返回的是新增数量
                 # 需要修改 taptap_selenium.py 让它返回列表或读取当天生成的文件
                 taptap_file = os.path.join(data_dir, f'taptap_games_{current_date_str}.jsonl')
                 if os.path.exists(taptap_file):
                     with open(taptap_file, 'r', encoding='utf-8') as f_tap:
                         tap_games_list = [json.loads(line) for line in f_tap]
                     logging.info(f"成功从 TapTap ({current_date_str}) 获取 {len(tap_games_list)} 条新数据。")
                     newly_fetched_games.extend(tap_games_list)
                 else:
                     logging.warning(f"TapTap 脚本报告成功，但未找到文件: {taptap_file}")
            else:
                logging.info(f"TapTap ({current_date_str}) 未获取到新数据或脚本返回0。")
        except Exception as e:
            logging.error(f"获取 TapTap 数据时出错: {e}", exc_info=True) # 记录详细错误信息
    else:
        logging.warning("TapTap 爬虫模块未成功导入，跳过 TapTap 数据获取。")

    # 16p 数据源
    if get_16p_data:
        logging.info("--- 开始获取 16p 数据 ---")
        try:
            # 假设 get_16p_data 不需要参数，或使用默认 URL
            # 同样，需要确保它返回游戏列表，或能读取到生成的文件
            p16_new_count = get_16p_data() # 假设它返回新增数量
            if p16_new_count > 0:
                 # 需要找到 16p 脚本生成的文件名模式
                 # 假设它生成类似 16p_games_YYYYMMDD_HHMMSS.jsonl 的文件
                 p16_files = sorted([f for f in os.listdir(data_dir) if f.startswith('16p_games_') and f.endswith('.jsonl')], reverse=True)
                 if p16_files:
                     latest_p16_file = os.path.join(data_dir, p16_files[0])
                     with open(latest_p16_file, 'r', encoding='utf-8') as f_16p:
                         p16_games_list = [json.loads(line) for line in f_16p]
                     logging.info(f"成功从 16p ({p16_files[0]}) 获取 {len(p16_games_list)} 条新数据。")
                     # 为16p数据添加日期（如果脚本本身没加）
                     for game in p16_games_list:
                         if 'date' not in game:
                             game['date'] = game.get('status_date') or current_date_str # 尝试获取状态日期或用当天日期
                     newly_fetched_games.extend(p16_games_list)
                 else:
                      logging.warning(f"16p 脚本报告成功，但未在 data 目录找到 16p_games 文件。")
            else:
                logging.info("16p 未获取到新数据或脚本返回0。")
        except Exception as e:
            logging.error(f"获取 16p 数据时出错: {e}", exc_info=True)
    else:
        logging.warning("16p 爬虫模块未成功导入，跳过 16p 数据获取。")

    logging.info(f"总共获取到 {len(newly_fetched_games)} 条新游戏数据。")

    if not newly_fetched_games:
        logging.info("未获取到任何新数据，流程提前结束。")
        # 即使没有新数据，也可能需要重新保存排序后的历史数据
        if existing_games:
             logging.info("对现有历史数据进行排序和保存...")
             existing_games.sort(key=lambda x: x.get('date', '0000-00-00'), reverse=True)
             # 保存 JSON
             try:
                 with open(history_file, 'w', encoding='utf-8') as f:
                     json.dump(existing_games, f, ensure_ascii=False, indent=2)
                 logging.info(f"排序后的历史数据已保存到 {history_file}")
             except Exception as e:
                 logging.error(f"保存排序后的历史 JSON 数据时出错: {e}")
             # 保存 Excel
             try:
                 df_existing = pd.DataFrame(existing_games)
                 excel_filename = os.path.join(data_dir, f'all_games_data_{datetime.now().strftime("%Y%m%d")}.xlsx')
                 excel_cols_map = get_excel_columns()
                 df_existing = df_existing[[col for col in excel_cols_map.values() if col in df_existing.columns]] # 保持列序
                 df_existing.rename(columns={v: k for k, v in excel_cols_map.items()}, inplace=True)
                 df_existing.to_excel(excel_filename, index=False, engine='openpyxl') # 需要安装 openpyxl
                 logging.info(f"排序后的历史数据已导出到 Excel: {excel_filename}")
             except Exception as e:
                 logging.error(f"导出排序后的历史 Excel 数据时出错: {e}")
        return # 结束

    # 3. 清洗新数据的名称
    logging.info("--- 开始清洗新获取的游戏名称 ---")
    for game in newly_fetched_games:
        original_name = game.get('name')
        cleaned_name = clean_game_name(original_name)
        game['cleaned_name'] = cleaned_name # 存储清洗后的名称
        if original_name != cleaned_name:
            logging.info(f"名称清洗: '{original_name}' -> '{cleaned_name}'")

    # 4. 版号匹配
    if match_version_numbers_for_games:
        logging.info("--- 开始进行版号匹配 ---")
        try:
            # 传递清洗后的名称给匹配器
            # 创建一个临时列表用于匹配，只包含必要信息或让匹配器自行处理
            games_to_match = [{"name": g['cleaned_name'], "_original_index": i} for i, g in enumerate(newly_fetched_games)]
            matched_results = match_version_numbers_for_games(games_to_match) # 假设它返回更新后的列表

            # 将匹配结果合并回 newly_fetched_games
            if matched_results and len(matched_results) == len(newly_fetched_games):
                for matched_game in matched_results:
                    original_index = matched_game.pop("_original_index", -1)
                    if original_index != -1:
                        # 合并 version_checked, approval_num 等字段
                        newly_fetched_games[original_index].update({k: v for k, v in matched_game.items() if k != 'name'}) # 避免覆盖 cleaned_name
            else:
                 logging.warning("版号匹配返回结果与预期不符，可能未成功合并版号信息。")

            logging.info("版号匹配完成。")
        except Exception as e:
            logging.error(f"版号匹配过程中出错: {e}", exc_info=True)
            logging.warning("版号信息可能不完整。")
    else:
        logging.warning("版号匹配模块未成功导入，跳过版号匹配。")

    # 5. 标准化新数据
    logging.info("--- 开始标准化新获取的数据 ---")
    try:
        standardized_new_games = standardize_game_data(newly_fetched_games)
        logging.info(f"完成 {len(standardized_new_games)} 条新数据的标准化。")
    except Exception as e:
        logging.error(f"数据标准化过程中出错: {e}", exc_info=True)
        standardized_new_games = [] # 出错则清空，避免后续问题

    # 6. 合并与去重 (里程碑逻辑)
    logging.info("--- 开始合并数据并处理重复项 ---")
    combined_games = existing_games + standardized_new_games
    logging.info(f"合并后共 {len(combined_games)} 条数据（历史+新增）。")

    unique_milestones = {}
    duplicates_handled = 0
    for game in combined_games:
        # 使用清洗后的名称进行匹配
        name = game.get("name", "未知名称") # standardize 已处理，这里直接用 name
        date = game.get("date", "0000-00-00")
        key = (name, date)

        if key not in unique_milestones:
            unique_milestones[key] = game
        else:
            duplicates_handled += 1
            existing_game = unique_milestones[key]
            # 优先保留 TapTap 来源
            if game.get('source') == 'TapTap' and existing_game.get('source') != 'TapTap':
                unique_milestones[key] = game
                logging.debug(f"重复处理: {key} - TapTap 优先，替换原有记录。")
            # (可选) 添加其他合并逻辑，例如保留信息更全的记录
            # 简单示例：保留非空字段更多的记录 (粗略判断)
            elif sum(1 for v in game.values() if v) > sum(1 for v in existing_game.values() if v):
                 unique_milestones[key] = game
                 logging.debug(f"重复处理: {key} - 新记录信息更完整，替换原有记录。")
            else:
                 logging.debug(f"重复处理: {key} - 保留原有记录。")

    final_games_list = list(unique_milestones.values())
    logging.info(f"处理重复项后剩余 {len(final_games_list)} 条独立游戏/日期记录 (处理了 {duplicates_handled} 个重复项)。")

    # 7. 排序
    logging.info("--- 按日期倒序排列数据 ---")
    final_games_list.sort(key=lambda x: x.get('date', '0000-00-00'), reverse=True)

    # 8. 保存结果
    # 保存 JSON
    logging.info("--- 保存最终结果到 JSON 文件 ---")
    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(final_games_list, f, ensure_ascii=False, indent=2)
        logging.info(f"最终数据已保存到 {history_file}")
    except Exception as e:
        logging.error(f"保存最终 JSON 数据时出错: {e}")

    # 保存 Excel
    logging.info("--- 保存最终结果到 Excel 文件 ---")
    try:
        df_final = pd.DataFrame(final_games_list)
        excel_columns = get_excel_columns()
        # 筛选并排序 DataFrame 的列，只保留定义好的列
        cols_to_export = [col for col in excel_columns.values() if col in df_final.columns]
        df_final_excel = df_final[cols_to_export].copy()
        # 重命名列为中文
        df_final_excel.rename(columns={v: k for k, v in excel_columns.items()}, inplace=True)

        excel_filename = os.path.join(data_dir, f'all_games_data_{datetime.now().strftime("%Y%m%d")}.xlsx')
        df_final_excel.to_excel(excel_filename, index=False, engine='openpyxl') # 需要安装 openpyxl
        logging.info(f"最终数据已导出到 Excel: {excel_filename}")
    except ImportError:
        logging.error("需要安装 'pandas' 和 'openpyxl' 才能导出 Excel。请运行: pip install pandas openpyxl")
    except Exception as e:
        logging.error(f"导出最终 Excel 数据时出错: {e}")

    # 9. 结束日志
    end_time = time.time()
    logging.info(f"数据收集任务完成，总耗时: {end_time - start_time:.2f} 秒。")
    logging.info("="*50 + "\n")

def get_excel_columns():
    """定义 Excel 导出的列名和顺序 (中文列名: 内部字段名)"""
    # 改为 中文: 英文 方便重命名
    return {
        "名称": "name",
        "日期": "date",
        "状态": "status",
        "平台": "platform",
        "分类": "category",
        "评分": "rating",
        "厂商": "publisher",
        "来源": "source",
        "是否重点": "is_featured",
        "链接": "link",
        "图标": "icon_url",
        "简介": "description",
        "版号已查": "version_checked",
        "批准文号": "approval_num",
        "出版物号": "publication_num",
        "批准日期": "approval_date",
        "出版单位": "publisher_unit",
        "运营单位": "operator_unit",
        "版号游戏类型": "game_type_version",
        "申报类别": "declaration_category",
        "版号多结果": "multiple_results"
    }

if __name__ == "__main__":
    # 确保 Pandas 和 openpyxl 可用
    try:
        import pandas
        import openpyxl
    except ImportError:
        logging.error("运行此脚本需要安装 pandas 和 openpyxl: pip install pandas openpyxl")
        sys.exit(1)

    collect_all_game_data() 