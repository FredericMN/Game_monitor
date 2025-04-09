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
import glob # Needed for checking excel file

# --- 配置日志 ---
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_filename = os.path.join(log_dir, f'collect_games_{datetime.now().strftime("%Y%m%d")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- 动态导入爬虫和匹配器模块 ---
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
data_dir = os.path.join(root_dir, 'data')
os.makedirs(data_dir, exist_ok=True)

if script_dir not in sys.path:
    sys.path.append(script_dir)

fetch_taptap_func = None
fetch_16p_func = None
match_versions_func = None

try: from taptap_selenium import get_taptap_games_for_date; fetch_taptap_func = get_taptap_games_for_date; logging.info("成功导入 taptap_selenium 模块。")
except ImportError as e: logging.error(f"导入 taptap_selenium 失败: {e}")
try:
    # 尝试导入 p16_selenium.py (假设你已将 16p_selenium.py 重命名为此)
    from p16_selenium import get_16p_data
    fetch_16p_func = get_16p_data
    logging.info("成功导入 p16_selenium 模块。")
except ImportError as e:
     logging.error(f"导入 p16_selenium 失败: {e} - 请确保文件已重命名为 p16_selenium.py")
try: from version_matcher import match_version_numbers_for_games; match_versions_func = match_version_numbers_for_games; logging.info("成功导入 version_matcher 模块。")
except ImportError as e: logging.error(f"导入 version_matcher 失败: {e}")


# --- 辅助函数 ---
def clean_game_name(name):
    if not name: return "未知名称"
    cleaned = re.sub(r'[（(].*?[)）]', '', name)
    cleaned = re.sub(r'[-–—]\s*[^-\s]+$', '', cleaned)
    cleaned = cleaned.strip()
    return cleaned if cleaned else name

def standardize_status(status):
    """
    标准化游戏状态字符串。
    优先处理包含"招募"的，然后处理"不删档"，再将其他测试（包括删档）归为"测试"，最后处理其他状态。

    Args:
        status: 原始状态字符串。

    Returns:
        标准化后的状态字符串。
    """
    # 确保输入是字符串
    if not isinstance(status, str):
        status = str(status)
    status_lower = status.lower() # 转小写方便比较

    # 优先处理包含"招募"的情况
    if "招募" in status: # 直接使用原始 status, 不用 status_lower
        return status # 保留原始状态，例如 "测试招募"

    # 处理不删档测试
    if "不删档" in status_lower:
        return "不删档测试"

    # 处理所有其他类型的测试（包括删档、beta、限量等）
    # 注意：此检查现在会捕获 "删档测试"
    if any(keyword in status_lower for keyword in ["测试", "test", "beta", "限量"]):
        return "测试" # Updated as per user edit

    # 处理预约状态
    if any(keyword in status_lower for keyword in ["预约", "预定", "pre", "待上线", "即将上线"]):
        return "可预约"
    # 处理上线状态
    if any(keyword in status_lower for keyword in ["上线", "公测", "首发"]):
        return "上线"
    # 处理更新状态
    if any(keyword in status_lower for keyword in ["更新", "新版本"]):
        return "更新"

    # 如果以上都不是，返回原始状态
    return status

def extract_rating_value(rating_text):
    if isinstance(rating_text, (int, float)): return float(rating_text)
    if not isinstance(rating_text, str): return 0.0
    match = re.search(r'(\d+\.\d+|\d+)', rating_text)
    if match:
        try: return float(match.group(1))
        except ValueError: pass
    return 0.0

def get_excel_columns():
    return {
        "名称": "name", "日期": "date", "状态": "status", "平台": "platform",
        "分类": "category", "评分": "rating", "厂商": "publisher", "来源": "source",
        "是否重点": "is_featured", "链接": "link", "图标": "icon_url", "简介": "description",
        "版号已查": "version_checked", "版号名称": "nppa_name", "批准文号": "approval_num",
        "出版物号": "publication_num", "批准日期": "approval_date", "出版单位": "publisher_unit",
        "运营单位": "operator_unit", "版号游戏类型": "game_type_version",
        "申报类别": "declaration_category", "版号多结果": "multiple_results",
        "是否人工校对": "manual_checked"
    }

def standardize_game_data(games_list, excel_columns_map):
    standardized_games = []
    internal_field_names = list(excel_columns_map.values())
    for game in games_list:
        std_game = {}
        # Use cleaned name for the main 'name' field
        std_game["name"] = game.get("cleaned_name") or clean_game_name(game.get("name", "未知名称")) # Ensure name is cleaned if cleaned_name missing
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
        std_game["is_featured"] = game.get("is_featured", False)
        std_game["version_checked"] = game.get("version_checked", False)
        std_game["nppa_name"] = game.get("nppa_name", "") # From version matcher
        std_game["approval_num"] = game.get("approval_num", "")
        std_game["publication_num"] = game.get("publication_num", "")
        std_game["approval_date"] = game.get("approval_date", "")
        std_game["publisher_unit"] = game.get("publisher_unit", "")
        std_game["operator_unit"] = game.get("operator_unit", "")
        std_game["game_type_version"] = game.get("game_type_version") or game.get("game_type", "")
        std_game["declaration_category"] = game.get("declaration_category", "")
        std_game["multiple_results"] = game.get("multiple_results", "")
        std_game["manual_checked"] = game.get("manual_checked", "") # From Excel/default
        # Ensure all fields exist
        for field in internal_field_names:
            if field not in std_game:
                if field == "rating": std_game[field] = 0.0
                elif field in ["is_featured", "version_checked"]: std_game[field] = False
                elif field == "manual_checked": std_game[field] = ""
                elif field == "nppa_name": std_game[field] = ""
                else: std_game[field] = ""
        standardized_games.append(std_game)
    return standardized_games

# --- 核心数据处理流程 ---
def collect_all_game_data(fetch_taptap=True, fetch_16p=True, process_history_only=False):
    start_time = time.time()
    task_description = "历史数据整理与版号匹配" if process_history_only else "今日数据爬取与整理"
    logging.info(f"{'='*20} 开始执行任务: {task_description} {'='*20}")

    master_excel_file = os.path.join(data_dir, "all_games_data.xlsx")
    master_json_file = os.path.join(data_dir, "all_games.json")

    final_games_list_unprocessed = [] # Store results before final checks/save
    execution_successful = False # Flag to indicate if try block completed

    try: # --- Main try block ---
        excel_columns_map = get_excel_columns()
        internal_excel_fields = list(excel_columns_map.values())

        # 0. Read Excel for locked records AND feature flags
        locked_records = {}
        excel_feature_flags = {} # Store (name, date) -> is_featured status from Excel
        if os.path.exists(master_excel_file):
            try:
                logging.info(f"读取主 Excel 文件: {master_excel_file}")
                df_excel = pd.read_excel(master_excel_file, engine='openpyxl', dtype=str) # Read all as string initially
                excel_rename_map_reverse = {v: k for k, v in excel_columns_map.items()}
                df_excel.rename(columns=lambda c: excel_rename_map_reverse.get(c, c), inplace=True)

                # Convert relevant columns back to expected types after reading as string
                if 'rating' in df_excel.columns: df_excel['rating'] = pd.to_numeric(df_excel['rating'], errors='coerce').fillna(0.0)
                # Explicitly handle boolean conversion for is_featured and version_checked for *all* records initially
                is_featured_col_present = 'is_featured' in df_excel.columns
                version_checked_col_present = 'version_checked' in df_excel.columns
                manual_checked_col_present = 'manual_checked' in df_excel.columns

                excel_records_list = df_excel.to_dict('records')

                for record in excel_records_list:
                    name = clean_game_name(record.get('name'))
                    date_raw = record.get('date')
                    if isinstance(date_raw, datetime): date_str = date_raw.strftime('%Y-%m-%d')
                    elif isinstance(date_raw, str):
                        try: date_str = pd.to_datetime(date_raw).strftime('%Y-%m-%d')
                        except: date_str = date_raw; logging.warning(f"无法标准化Excel日期: {date_raw} for game {name}")
                    else: date_str = "0000-00-00" # Should ideally not happen if read as string
                    key = (name, date_str)

                    # --- Check and store 'is_featured' flag for ALL records ---
                    is_featured_excel = False
                    if is_featured_col_present:
                        is_featured_raw = record.get('is_featured', '')
                        is_featured_excel = str(is_featured_raw).strip().lower() == '是'
                    excel_feature_flags[key] = is_featured_excel
                    # --- End feature flag check ---

                    # --- Check manual checked status ---
                    is_manually_checked = False
                    if manual_checked_col_present:
                        manual_checked_raw = record.get('manual_checked', '')
                        is_manually_checked = str(manual_checked_raw).strip() != ''
                    # --- End manual check ---

                    if is_manually_checked:
                        # Ensure record has all fields, converting types where needed for locked record
                        full_record = {}
                        for field in internal_excel_fields:
                            value = record.get(field)
                            if field == 'rating': full_record[field] = float(value) if value is not None else 0.0
                            elif field == 'is_featured': full_record[field] = is_featured_excel # Use parsed boolean
                            elif field == 'version_checked': full_record[field] = bool(str(record.get('version_checked', '')).strip().lower() == '是') if version_checked_col_present else False
                            elif field == 'manual_checked': full_record[field] = str(value).strip() if value is not None else "" # Keep as string
                            else: full_record[field] = str(value).strip() if value is not None else "" # Default to string
                        full_record['name'] = name # Use cleaned name
                        full_record['date'] = date_str # Use standardized date
                        locked_records[key] = full_record

                logging.info(f"从主 Excel 加载了 {len(locked_records)} 条人工校对记录，并记录了 {len(excel_feature_flags)} 条记录的重点状态。")

            except Exception as e:
                logging.error(f"读取或处理主 Excel 文件 ({master_excel_file}) 时出错: {e}", exc_info=True)
                # Allow continuing without locked records/flags, but log error
        else:
            logging.info(f"主 Excel 文件 {master_excel_file} 不存在，将创建新文件。")

        # 1. Load JSON history
        existing_games_from_json = []
        if os.path.exists(master_json_file):
            try:
                with open(master_json_file, 'r', encoding='utf-8') as f:
                    loaded_json_data = json.load(f)
                    for game in loaded_json_data:
                        name = clean_game_name(game.get('name'))
                        date = game.get('date', '0000-00-00')
                        key = (name, date)
                        if key not in locked_records:
                            # Ensure manual_checked field exists
                            game['manual_checked'] = game.get('manual_checked', '')
                            # --- Apply Excel feature flag if present ---
                            if excel_feature_flags.get(key, False):
                                game['is_featured'] = True
                                logging.debug(f"从Excel更新历史记录 {key} 的重点状态为 True")
                            # --- End feature flag apply ---
                            existing_games_from_json.append(game)
                logging.info(f"成功从 {master_json_file} 加载 {len(existing_games_from_json)} 条未被锁定的历史数据 (已应用Excel重点状态)。")
            except Exception as e:
                logging.error(f"加载或处理历史 JSON 数据 ({master_json_file}) 时出错: {e}") # Log error, continue
        else:
            logging.info(f"主 JSON 文件 {master_json_file} 不存在。")

        # --- Branch based on mode ---
        temp_final_list = [] # Store results of processing within try block
        if process_history_only:
            logging.info("模式: 只处理历史数据。跳过新数据爬取。")
            # Note: existing_games_from_json already has Excel flags applied
            games_to_process = list(locked_records.values()) + existing_games_from_json
            if not games_to_process:
                 logging.warning("历史数据为空，无法进行处理。")
            else:
                logging.info("--- 开始清洗历史游戏名称 ---")
                for game in games_to_process: game['cleaned_name'] = clean_game_name(game.get('name'))

                # --- 新增: 对历史数据应用 AppStore 过滤 ---
                logging.info("--- 开始过滤历史数据中的 AppStore 特定记录 ---")
                filtered_games_to_process = []
                removed_appstore_hist_count = 0
                # Define major publisher keywords (lowercase)
                major_publisher_keywords = {'ltd', '腾讯', 'tencent', '网易', 'netease', '米哈游', 'mihoyo', 'lingxi'}
                # Define blocked publishers (lowercase)
                blocked_publishers = {'big kid gaming studio (private) limited', 'ms zeroloft games'}

                for game in games_to_process:
                    # Use cleaned_name for key checking if available, otherwise clean the original name
                    cleaned_name_val = game.get('cleaned_name') or clean_game_name(game.get('name'))
                    date_val = game.get('date', '0000-00-00')
                    key = (cleaned_name_val, date_val)
                    if key in locked_records:
                        filtered_games_to_process.append(game)
                        continue

                    source = game.get('source', '').lower()
                    original_name = game.get('name', '')
                    # cleaned_name = game.get('cleaned_name', '') # Already got cleaned_name_val
                    publisher_lower = game.get('publisher', '').lower()

                    # --- 新增: 检查是否为阻止的发行商 ---
                    if publisher_lower in blocked_publishers:
                        logging.info(f"  过滤历史记录 (阻止的发行商): '{original_name}' [发行: {game.get('publisher')}]")
                        removed_appstore_hist_count += 1 # 计数也包含在此
                        continue # 直接跳过此游戏
                    # --- 结束阻止发行商检查 ---

                    is_appstore = (source == 'appstore')
                    too_many_spaces = original_name.count(' ') >= 2
                    too_long = len(cleaned_name_val) > 10 # Use cleaned name here

                    # Check if publisher is considered major
                    is_major_publisher = any(keyword in publisher_lower for keyword in major_publisher_keywords)

                    # Apply filter only if AppStore, meets criteria, AND is NOT from a major publisher
                    if is_appstore and (too_many_spaces or too_long) and not is_major_publisher:
                        logging.info(f"  过滤历史 AppStore 记录: '{original_name}' [发行: {game.get('publisher')}] (原因: {'多个空格' if too_many_spaces else ''}{'/' if too_many_spaces and too_long else ''}{'名称过长' if too_long else ''})")
                        removed_appstore_hist_count += 1
                        continue # Skip this game
                    else:
                        filtered_games_to_process.append(game)
                logging.info(f"历史数据 AppStore 过滤完成，移除了 {removed_appstore_hist_count} 条记录。")
                # --- 结束 AppStore 过滤 ---

                # Derive unlocked_history_games from the *filtered* list, ensuring cleaned_name exists for key lookup
                unlocked_history_games = []
                for g in filtered_games_to_process:
                    cleaned_name_val = g.get('cleaned_name') or clean_game_name(g.get('name'))
                    # Ensure cleaned_name is actually in the dict for later use
                    if 'cleaned_name' not in g: g['cleaned_name'] = cleaned_name_val
                    date_val = g.get('date', '0000-00-00')
                    key = (cleaned_name_val, date_val)
                    if key not in locked_records:
                        unlocked_history_games.append(g)


                if match_versions_func and unlocked_history_games:
                    logging.info(f"--- 开始对 {len(unlocked_history_games)} 条未锁定历史数据进行版号匹配 ---")
                    try:
                         # Add index for reliable update during version matching
                         for i, game in enumerate(unlocked_history_games): game['_original_index'] = i # Use consistent index key
                         # Prepare data for matcher - use cleaned name
                         games_for_matcher = [{"name": g.get('cleaned_name'), "_original_index": g.get('_original_index')} for g in unlocked_history_games]
                         match_versions_func(games_for_matcher) # Modifies games_for_matcher in place

                         # Merge results back based on index
                         for matched_info in games_for_matcher:
                             orig_idx = matched_info.get("_original_index", -1)
                             target_game = next((g for g in unlocked_history_games if g.get('_original_index') == orig_idx), None)
                             if target_game:
                                 update_data = {k: v for k, v in matched_info.items() if k not in ['name', '_original_index']}
                                 target_game.update(update_data)
                                 target_game['version_checked'] = True # Mark as checked

                         logging.info("历史数据版号匹配完成。")
                    except Exception as e: logging.error(f"历史数据版号匹配过程中出错: {e}", exc_info=True) # Log, don't raise
                elif not match_versions_func: logging.warning("版号匹配模块未导入，跳过历史数据匹配。")
                else: logging.info("没有需要进行版号匹配的未锁定历史数据。")

                # Combine locked records with the (potentially version-matched) filtered unlocked history
                final_processed_list = list(locked_records.values()) + unlocked_history_games
                logging.info("--- 开始标准化最终历史数据 ---")
                # Need to standardize AFTER potential version matching which might add fields
                temp_final_list = standardize_game_data(final_processed_list, excel_columns_map)
                # Re-apply excel feature flags after standardization if necessary (although history should have it)
                for game_final in temp_final_list:
                    key = (game_final.get('name'), game_final.get('date'))
                    if key not in locked_records and excel_feature_flags.get(key, False):
                        game_final['is_featured'] = True
                logging.info(f"完成 {len(temp_final_list)} 条历史数据的标准化。")

        else: # Fetch new data mode
            # 2. Fetch new data
            newly_fetched_games = []
            current_date_str = datetime.now().strftime("%Y-%m-%d")
            if fetch_taptap and fetch_taptap_func:
                logging.info("--- 开始获取 TapTap 数据 ---")
                try:
                    taptap_new_count = fetch_taptap_func(current_date_str)
                    if taptap_new_count > 0:
                        taptap_file = os.path.join(data_dir, f'taptap_games_{current_date_str}.jsonl')
                        if os.path.exists(taptap_file):
                            with open(taptap_file, 'r', encoding='utf-8') as f_tap: tap_games_list = [json.loads(line) for line in f_tap]
                            logging.info(f"成功从 TapTap ({current_date_str}) 获取 {len(tap_games_list)} 条新数据。")
                            newly_fetched_games.extend(tap_games_list)
                        else: logging.warning(f"TapTap 脚本报告成功，但未找到文件: {taptap_file}")
                    else: logging.info(f"TapTap ({current_date_str}) 未获取到新数据或脚本返回0。")
                except Exception as e: logging.error(f"获取 TapTap 数据时出错: {e}", exc_info=True)
            elif fetch_taptap: logging.warning("TapTap 模块未加载，跳过爬取。")
            else: logging.info("根据用户选择，跳过 TapTap 数据获取。")

            if fetch_16p and fetch_16p_func:
                logging.info("--- 开始获取 16p 数据 ---")
                try:
                    p16_new_count = fetch_16p_func()
                    if p16_new_count > 0:
                        p16_files = sorted([f for f in os.listdir(data_dir) if f.startswith('p16_games_') and f.endswith('.jsonl')], reverse=True) # Corrected prefix 'p16_'
                        if p16_files:
                            latest_p16_file = os.path.join(data_dir, p16_files[0])
                            with open(latest_p16_file, 'r', encoding='utf-8') as f_16p: p16_games_list = [json.loads(line) for line in f_16p]
                            logging.info(f"成功从 16p ({p16_files[0]}) 获取 {len(p16_games_list)} 条新数据。")
                            for game in p16_games_list:
                                if 'date' not in game or not game['date']: game['date'] = game.get('status_date') or current_date_str
                            newly_fetched_games.extend(p16_games_list)
                        else: logging.warning(f"16p 脚本报告成功，但未在 data 目录找到 p16_games 文件。")
                    else: logging.info("16p 未获取到新数据或脚本返回0。")
                except Exception as e: logging.error(f"获取 16p 数据时出错: {e}", exc_info=True)
            elif fetch_16p: logging.warning("16p 模块未加载，跳过爬取。")
            else: logging.info("根据用户选择，跳过 16p 数据获取。")

            logging.info(f"总共获取到 {len(newly_fetched_games)} 条新游戏数据。")

            if not newly_fetched_games and not existing_games_from_json and not locked_records:
                logging.info("未获取到新数据，且无历史数据，流程结束。")
            else:
                # 3. Clean names for new data
                logging.info("--- 开始清洗新获取的游戏名称 ---")
                for game in newly_fetched_games: game['cleaned_name'] = clean_game_name(game.get('name'))

                # --- 新增: AppStore 特定过滤 ---
                logging.info("--- 开始过滤 AppStore 特定记录 ---")
                initial_count = len(newly_fetched_games)
                filtered_new_games = []
                removed_appstore_count = 0
                # Define major publisher keywords (lowercase)
                major_publisher_keywords = {'ltd', '腾讯', 'tencent', '网易', 'netease', '米哈游', 'mihoyo', 'lingxi'}
                # Define blocked publishers (lowercase)
                blocked_publishers = {'big kid gaming studio (private) limited', 'ms zeroloft games'}

                for game in newly_fetched_games:
                    source = game.get('source', '').lower() # 检查来源，忽略大小写
                    original_name = game.get('name', '')
                    cleaned_name = game.get('cleaned_name', '') # 使用已清洗的名称
                    publisher_lower = game.get('publisher', '').lower()

                    # --- 新增: 检查是否为阻止的发行商 ---
                    if publisher_lower in blocked_publishers:
                        logging.info(f"  过滤新记录 (阻止的发行商): '{original_name}' [发行: {game.get('publisher')}]")
                        removed_appstore_count += 1 # 计数也包含在此
                        continue # 直接跳过此游戏
                    # --- 结束阻止发行商检查 ---

                    is_appstore = (source == 'appstore')

                    # 定义过滤条件
                    too_many_spaces = original_name.count(' ') >= 2
                    too_long = len(cleaned_name) > 10

                    # Check if publisher is considered major
                    is_major_publisher = any(keyword in publisher_lower for keyword in major_publisher_keywords)

                    # Apply filter only if AppStore, meets criteria, AND is NOT from a major publisher
                    if is_appstore and (too_many_spaces or too_long) and not is_major_publisher:
                        logging.info(f"  过滤 AppStore 记录: '{original_name}' [发行: {game.get('publisher')}] (原因: {'多个空格' if too_many_spaces else ''}{'/' if too_many_spaces and too_long else ''}{'名称过长' if too_long else ''})")
                        removed_appstore_count += 1
                        continue # 跳过此游戏
                    else:
                        filtered_new_games.append(game)

                logging.info(f"AppStore 过滤完成，移除了 {removed_appstore_count} 条记录。剩余新记录: {len(filtered_new_games)}")
                newly_fetched_games = filtered_new_games # 使用过滤后的列表进行后续操作
                # --- 结束 AppStore 过滤 ---

                # 4. Match versions for new, unlocked data (Now operates on filtered list)
                if match_versions_func and newly_fetched_games:
                    games_to_match = []
                    for i, game in enumerate(newly_fetched_games):
                        # Use cleaned name for key check
                        game_date = game.get('date', current_date_str)
                        if not game_date: game_date = current_date_str # Ensure date exists for key
                        game['date'] = game_date # Update game dict with date if missing
                        key = (game['cleaned_name'], game_date)
                        if key not in locked_records:
                            games_to_match.append({"name": game['cleaned_name'], "_original_index": i})

                    if games_to_match:
                        logging.info(f"--- 开始对 {len(games_to_match)} 条新获取的未锁定数据进行版号匹配 ---")
                        try:
                            match_versions_func(games_to_match) # Modifies games_to_match in place
                            # Merge results back to newly_fetched_games
                            for matched_game_info in games_to_match:
                                orig_idx = matched_game_info.get("_original_index", -1) # Use get for safety
                                if orig_idx != -1 and orig_idx < len(newly_fetched_games):
                                    update_data = {k: v for k, v in matched_game_info.items() if k not in ['name', '_original_index']}
                                    newly_fetched_games[orig_idx].update(update_data)
                            logging.info("新数据版号匹配完成。")
                        except Exception as e: logging.error(f"新数据版号匹配过程中出错: {e}", exc_info=True)
                    else: logging.info("所有新获取的数据都已被人工锁定或无新数据需匹配。")
                elif not match_versions_func: logging.warning("版号匹配模块未导入，跳过新数据匹配。")
                elif not newly_fetched_games: logging.info("无新数据，跳过版号匹配。")

                # 5. Standardize new data
                logging.info("--- 开始标准化新获取的数据 ---")
                standardized_new_games = []
                if newly_fetched_games:
                    try:
                        standardized_new_games = standardize_game_data(newly_fetched_games, excel_columns_map)
                        # --- Apply Excel feature flag to standardized new data ---
                        for std_game in standardized_new_games:
                            key = (std_game['name'], std_game['date'])
                            if key not in locked_records and excel_feature_flags.get(key, False):
                                std_game['is_featured'] = True
                                logging.debug(f"从Excel更新新标准化记录 {key} 的重点状态为 True")
                        # --- End feature flag apply ---
                        logging.info(f"完成 {len(standardized_new_games)} 条新数据的标准化 (已应用Excel重点状态)。")
                    except Exception as e:
                        logging.error(f"新数据标准化或应用Excel重点状态过程中出错: {e}", exc_info=True)
                        raise # Critical error

                # 6. Merge & Deduplicate
                logging.info("--- 开始合并数据并处理重复项 ---")
                # Note: existing_games_from_json and standardized_new_games already have flags applied
                combined_games = list(locked_records.values()) + existing_games_from_json + standardized_new_games
                logging.info(f"合并后共 {len(combined_games)} 条数据（已锁定+历史+新增）待处理。")

                # --- 修改：将上线冲突处理移到这里，在最终列表形成之后，保存之前 --- #
                if temp_final_list: # 确保列表不为空
                    logging.info("--- 开始处理最终列表中的上线日期冲突 --- ")
                    final_games_grouped = {}
                    for game in temp_final_list:
                        name = game.get("name", "未知名称")
                        if name not in final_games_grouped:
                            final_games_grouped[name] = []
                        final_games_grouped[name].append(game)

                    conflict_resolved_count_final = 0
                    processed_list_after_conflict = [] # 使用新列表存储处理结果

                    for name, group in final_games_grouped.items():
                        online_records = [g for g in group if g.get('status') == '上线']

                        if len(online_records) > 1:
                            logging.warning(f"游戏 '{name}' 存在多个上线日期冲突: {[g.get('date') for g in online_records]}")
                            online_records.sort(key=lambda g: g.get('date', '0000-00-00'), reverse=True)

                            latest_online_record = online_records[0]
                            latest_online_record['manual_checked'] = "上线日期冲突-自动保留最新" # 强制标记最新
                            conflict_resolved_count_final += 1

                            # 强制修改所有旧的上线记录状态为"未知状态"
                            for old_record in online_records[1:]:
                                old_record['status'] = "未知状态"
                                logging.info(f"  游戏 '{name}' 的旧上线记录 ({old_record.get('date')}) 因冲突被强制标记为未知状态。")

                            # 将处理过的这组记录加入新列表
                            processed_list_after_conflict.extend(group)
                        else:
                            # 没有冲突，直接将该组所有记录加入新列表
                            processed_list_after_conflict.extend(group)

                    if conflict_resolved_count_final > 0:
                        logging.info(f"处理了 {conflict_resolved_count_final} 个游戏的上线日期冲突（强制标记最新）。")
                        # 使用处理冲突后的列表进行后续排序和保存
                        temp_final_list = processed_list_after_conflict # 替换原有列表
                    else:
                        logging.info("未发现上线日期冲突。")

                # --- 继续去重逻辑 (使用 unique_milestones) --- #
                unique_milestones = {}
                duplicates_handled = 0
                processed_keys = set(locked_records.keys()) # 锁定记录优先保留
                unique_milestones.update(locked_records)

                # Process remaining (JSON history + new standardized)
                for game in existing_games_from_json + standardized_new_games:
                    name = game.get("name", "未知名称")
                    date = game.get("date", "0000-00-00")
                    key = (name, date)
                    if key in processed_keys: continue
                    game['manual_checked'] = game.get('manual_checked', '')
                    if key not in unique_milestones:
                        unique_milestones[key] = game
                        processed_keys.add(key)
                    else:
                        duplicates_handled += 1
                        existing_game = unique_milestones[key]
                        if game.get('source') == 'TapTap' and existing_game.get('source') != 'TapTap':
                            unique_milestones[key] = game
                        elif sum(1 for v in game.values() if v not in [None, '', False]) > sum(1 for v in existing_game.values() if v not in [None, '', False]):
                             unique_milestones[key] = game

                temp_final_list = list(unique_milestones.values())
                logging.info(f"初步去重后剩余 {len(temp_final_list)} 条记录 (处理了 {duplicates_handled} 个重复项)。")

        # --- Common steps within try block (适用于两种模式) --- #

        # --- 继续后续步骤 --- #
        if not temp_final_list:
             logging.warning("最终数据列表为空，无法进行排序。")
        else:
            # 7. Sort
            logging.info("--- 按日期倒序排列数据 ---")
            temp_final_list.sort(key=lambda x: x.get('date', '0000-00-00'), reverse=True)
            final_games_list_unprocessed = temp_final_list # Assign to outer scope var
            execution_successful = True # Mark as successful

    except Exception as main_error:
        logging.error("="*20 + " 数据处理流程中发生严重错误 " + "="*20, exc_info=True)
        logging.error("由于发生错误，将不会更新主数据文件。")
        # execution_successful remains False
    # Removed 'else' block, save logic is now conditional on flag

    finally: # --- Main finally block ---
        # Check flag before saving
        if execution_successful and final_games_list_unprocessed:
            logging.info("--- 保存最终结果 (覆盖主文件) ---")
            try:
                with open(master_json_file, 'w', encoding='utf-8') as f:
                    json.dump(final_games_list_unprocessed, f, ensure_ascii=False, indent=2)
                logging.info(f"最终数据已覆盖保存到 {master_json_file}")
            except Exception as e: logging.error(f"保存最终 JSON 数据时出错: {e}")

            try:
                df_final = pd.DataFrame(final_games_list_unprocessed)
                cols_map = get_excel_columns()
                internal_fields = list(cols_map.values())

                # Ensure all expected columns exist in the DataFrame, adding empty ones if needed
                for field in internal_fields:
                    if field not in df_final.columns:
                        if field == 'rating': df_final[field] = 0.0
                        elif field in ['is_featured', 'version_checked']: df_final[field] = False
                        else: df_final[field] = '' # Default to empty string for others

                cols_to_export = [col for col in internal_fields if col in df_final.columns] # Select in desired order
                df_final_excel = df_final[cols_to_export].copy()

                # Convert boolean fields back to '是'/'' for Excel output
                for col in ['is_featured', 'version_checked']: # Removed manual_checked as it should remain string
                    if col in df_final_excel.columns:
                        # Apply conversion carefully, handling potential non-boolean values if any slipped through
                         df_final_excel[col] = df_final_excel[col].apply(
                             lambda x: '是' if x is True or str(x).strip().lower() in ['true', '是', 'yes', '1'] else ''
                         )
                # Ensure manual_checked remains string (it should be already)
                if 'manual_checked' in df_final_excel.columns:
                     df_final_excel['manual_checked'] = df_final_excel['manual_checked'].astype(str).fillna('')


                df_final_excel.rename(columns={v: k for k, v in cols_map.items()}, inplace=True)
                df_final_excel.to_excel(master_excel_file, index=False, engine='openpyxl')
                logging.info(f"最终数据已覆盖保存到 Excel: {master_excel_file}")
            except ImportError: logging.error("需要安装 'pandas' 和 'openpyxl' 才能导出 Excel。")
            except Exception as e: logging.error(f"导出最终 Excel 数据时出错: {e}", exc_info=True)
        elif execution_successful and not final_games_list_unprocessed:
             logging.warning("处理流程成功但最终列表为空，不执行保存操作。")
        elif not execution_successful:
             logging.info("处理流程未成功完成，跳过保存操作。") # Already logged error in except block

        # Log end time
        logging.info(f"任务结束，总耗时: {time.time() - start_time:.2f} 秒。")
        logging.info("="*50 + "\n")


# --- 主程序入口 ---
def main():
    try:
        import pandas; import openpyxl; import glob # Add glob back here
    except ImportError:
        logging.error("运行此脚本需要安装 pandas, openpyxl: pip install pandas openpyxl")
        sys.exit(1)

    # (User input logic remains the same)
    print("请选择运行模式:")
    print("1: 根据历史数据整理并匹配版号 (不爬取新数据)")
    print("2: 爬取今日新数据并整理")
    mode_choice = ""
    while mode_choice not in ['1', '2']: mode_choice = input("请输入选项 (1 或 2): ").strip()

    if mode_choice == '1':
        collect_all_game_data(process_history_only=True)
    elif mode_choice == '2':
        print("\n请选择爬取范围:")
        print("1: TapTap 和 16p 都爬取")
        print("2: 只爬取 TapTap")
        print("3: 只爬取 16p") # Added option 3
        fetch_choice = ""
        while fetch_choice not in ['1', '2', '3']: fetch_choice = input("请输入选项 (1, 2 或 3): ").strip() # Updated prompt
        fetch_taptap = (fetch_choice == '1' or fetch_choice == '2')
        fetch_16p = (fetch_choice == '1' or fetch_choice == '3') # Updated logic
        if not fetch_taptap_func and fetch_taptap: logging.warning("TapTap 模块未加载，无法爬取。"); fetch_taptap = False
        if not fetch_16p_func and fetch_16p: logging.warning("16p 模块未加载，无法爬取。"); fetch_16p = False
        if not fetch_taptap and not fetch_16p: logging.error("没有可用的爬虫模块或未选择任何源。"); sys.exit(1)
        collect_all_game_data(fetch_taptap=fetch_taptap, fetch_16p=fetch_16p, process_history_only=False)

if __name__ == "__main__":
    main() 