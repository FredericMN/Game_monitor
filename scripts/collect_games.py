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
    if not isinstance(status, str): status = str(status)
    status_lower = status.lower()
    if "删档" in status_lower: return "删档测试"
    if "不删档" in status_lower: return "不删档测试"
    if any(keyword in status_lower for keyword in ["测试", "test", "beta", "限量"]): return "测试" # Updated as per user edit
    if any(keyword in status_lower for keyword in ["预约", "预定", "pre", "待上线", "即将上线"]): return "可预约"
    if any(keyword in status_lower for keyword in ["上线", "公测", "首发"]): return "上线"
    if any(keyword in status_lower for keyword in ["更新", "新版本"]): return "更新"
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

        # 0. Read Excel for locked records
        locked_records = {}
        if os.path.exists(master_excel_file):
            try:
                logging.info(f"读取主 Excel 文件: {master_excel_file}")
                df_excel = pd.read_excel(master_excel_file, engine='openpyxl', dtype=str) # Read all as string initially
                excel_rename_map_reverse = {v: k for k, v in excel_columns_map.items()}
                df_excel.rename(columns=lambda c: excel_rename_map_reverse.get(c, c), inplace=True)

                if 'manual_checked' in df_excel.columns:
                    # Convert relevant columns back to expected types after reading as string
                    df_excel['rating'] = pd.to_numeric(df_excel['rating'], errors='coerce').fillna(0.0)
                    for bool_col in ['is_featured', 'version_checked']:
                         if bool_col in df_excel.columns:
                             df_excel[bool_col] = df_excel[bool_col].apply(lambda x: True if str(x).strip().lower() == '是' else False)

                    checked_df = df_excel[df_excel['manual_checked'].notna() & df_excel['manual_checked'].ne('') & df_excel['manual_checked'].astype(str).str.strip().ne('')]
                    checked_records_list = checked_df.to_dict('records')

                    for record in checked_records_list:
                        name = clean_game_name(record.get('name'))
                        date_raw = record.get('date')
                        if isinstance(date_raw, datetime): date_str = date_raw.strftime('%Y-%m-%d')
                        elif isinstance(date_raw, str):
                            try: date_str = pd.to_datetime(date_raw).strftime('%Y-%m-%d')
                            except: date_str = date_raw; logging.warning(f"无法标准化Excel日期: {date_raw}")
                        else: date_str = "0000-00-00"
                        key = (name, date_str)
                        # Ensure record has all fields, converting types where needed
                        full_record = {}
                        for field in internal_excel_fields:
                            value = record.get(field)
                            if field == 'rating': full_record[field] = float(value) if value is not None else 0.0
                            elif field in ['is_featured', 'version_checked']: full_record[field] = bool(value) if value is not None else False
                            elif field == 'manual_checked': full_record[field] = str(value).strip() if value is not None else "" # Keep as string
                            else: full_record[field] = str(value).strip() if value is not None else "" # Default to string
                        full_record['name'] = name # Use cleaned name
                        full_record['date'] = date_str # Use standardized date
                        locked_records[key] = full_record
                    logging.info(f"从主 Excel 加载了 {len(locked_records)} 条人工校对过的记录。")
                else:
                    logging.warning(f"主 Excel 文件 {master_excel_file} 中缺少 '是否人工校对' 列，无法加载锁定状态。")
            except Exception as e:
                logging.error(f"读取或处理主 Excel 文件 ({master_excel_file}) 时出错: {e}", exc_info=True)
                # Allow continuing without locked records, but log error
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
                            existing_games_from_json.append(game)
                logging.info(f"成功从 {master_json_file} 加载 {len(existing_games_from_json)} 条未被锁定的历史数据。")
            except Exception as e:
                logging.error(f"加载或处理历史 JSON 数据 ({master_json_file}) 时出错: {e}") # Log error, continue
        else:
            logging.info(f"主 JSON 文件 {master_json_file} 不存在。")

        # --- Branch based on mode ---
        temp_final_list = [] # Store results of processing within try block
        if process_history_only:
            logging.info("模式: 只处理历史数据。跳过新数据爬取。")
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
                    key = (game.get('cleaned_name'), game.get('date', '0000-00-00'))
                    if key in locked_records:
                        filtered_games_to_process.append(game)
                        continue

                    source = game.get('source', '').lower()
                    original_name = game.get('name', '')
                    cleaned_name = game.get('cleaned_name', '')
                    publisher_lower = game.get('publisher', '').lower()

                    # --- 新增: 检查是否为阻止的发行商 ---
                    if publisher_lower in blocked_publishers:
                        logging.info(f"  过滤历史记录 (阻止的发行商): '{original_name}' [发行: {game.get('publisher')}]")
                        removed_appstore_hist_count += 1 # 计数也包含在此
                        continue # 直接跳过此游戏
                    # --- 结束阻止发行商检查 ---

                    is_appstore = (source == 'appstore')
                    too_many_spaces = original_name.count(' ') >= 2
                    too_long = len(cleaned_name) > 10

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

                # Derieve unlocked_history_games from the *filtered* list
                unlocked_history_games = [g for g in filtered_games_to_process if (g.get('cleaned_name'), g.get('date', '0000-00-00')) not in locked_records]

                if match_versions_func and unlocked_history_games:
                    logging.info(f"--- 开始对 {len(unlocked_history_games)} 条未锁定历史数据进行版号匹配 ---")
                    try:
                         # Add index for reliable update during version matching
                         for i, game in enumerate(unlocked_history_games): game['_original_index'] = i # Use consistent index key
                         match_versions_func(unlocked_history_games) # Modifies in place
                         logging.info("历史数据版号匹配完成。")
                    except Exception as e: logging.error(f"历史数据版号匹配过程中出错: {e}", exc_info=True) # Log, don't raise
                elif not match_versions_func: logging.warning("版号匹配模块未导入，跳过历史数据匹配。")
                else: logging.info("没有需要进行版号匹配的未锁定历史数据。")

                # Combine locked records with the (potentially version-matched) filtered unlocked history
                final_processed_list = list(locked_records.values()) + unlocked_history_games
                logging.info("--- 开始标准化最终历史数据 ---")
                temp_final_list = standardize_game_data(final_processed_list, excel_columns_map)
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
                        logging.info(f"完成 {len(standardized_new_games)} 条新数据的标准化。")
                    except Exception as e:
                        logging.error(f"新数据标准化过程中出错: {e}", exc_info=True)
                        raise # Critical error

                # 6. Merge & Deduplicate
                logging.info("--- 开始合并数据并处理重复项 ---")
                combined_games = list(locked_records.values()) + existing_games_from_json + standardized_new_games
                logging.info(f"合并后共 {len(combined_games)} 条数据（已锁定+历史+新增）待去重。")
                unique_milestones = {}
                duplicates_handled = 0
                processed_keys = set(locked_records.keys())
                unique_milestones.update(locked_records)

                for game in existing_games_from_json + standardized_new_games:
                    # Use name from standardization (already cleaned)
                    name = game.get("name", "未知名称")
                    date = game.get("date", "0000-00-00")
                    key = (name, date)
                    if key in processed_keys: duplicates_handled += 1; continue
                    # Ensure manual_checked field exists
                    game['manual_checked'] = game.get('manual_checked', '')
                    if key not in unique_milestones:
                        unique_milestones[key] = game; processed_keys.add(key)
                    else:
                        duplicates_handled += 1; existing_game = unique_milestones[key]
                        if game.get('source') == 'TapTap' and existing_game.get('source') != 'TapTap': unique_milestones[key] = game; logging.debug(f"重复(未锁定):{key}-TapTap优先")
                        elif sum(1 for v in game.values() if v) > sum(1 for v in existing_game.values() if v): unique_milestones[key] = game; logging.debug(f"重复(未锁定):{key}-新记录更完整")
                        else: logging.debug(f"重复(未锁定):{key}-保留原有")
                temp_final_list = list(unique_milestones.values()) # Store in temp list
                logging.info(f"处理重复项后剩余 {len(temp_final_list)} 条记录 (处理了 {duplicates_handled} 个重复项)。")

        # --- Common steps within try block ---
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
                cols_to_export = [col for col in internal_fields if col in df_final.columns]
                df_final_excel = df_final[cols_to_export].copy()
                for col in ['manual_checked', 'version_checked', 'is_featured']:
                    if col in df_final_excel.columns:
                         df_final_excel[col] = df_final_excel[col].apply(lambda x: '是' if x is True or str(x).strip().lower() == '是' else '')
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
        fetch_choice = ""
        while fetch_choice not in ['1', '2']: fetch_choice = input("请输入选项 (1 或 2): ").strip()
        fetch_taptap = (fetch_choice == '1' or fetch_choice == '2')
        fetch_16p = (fetch_choice == '1')
        if not fetch_taptap_func and fetch_taptap: logging.warning("TapTap 模块未加载，无法爬取。"); fetch_taptap = False
        if not fetch_16p_func and fetch_16p: logging.warning("16p 模块未加载，无法爬取。"); fetch_16p = False
        if not fetch_taptap and not fetch_16p: logging.error("没有可用的爬虫模块或未选择任何源。"); sys.exit(1)
        collect_all_game_data(fetch_taptap=fetch_taptap, fetch_16p=fetch_16p, process_history_only=False)

if __name__ == "__main__":
    main() 