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
import unicodedata # 添加 unicodedata 用于规范化

# --- 配置日志 ---
log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_filename = os.path.join(log_dir, f'collect_games_{datetime.now().strftime("%Y%m%d")}.log')
logging.basicConfig(
    level=logging.INFO, # Changed to INFO for clearer console output
    format='%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s', # Added function name and line number
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# --- 脚本及数据目录 --- 
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
data_dir = os.path.join(root_dir, 'data')
config_dir = os.path.join(root_dir, 'config') # Added config directory
os.makedirs(data_dir, exist_ok=True)
os.makedirs(config_dir, exist_ok=True) # Ensure config dir exists

# --- 全局配置变量 ---
CONFIG = {}

def load_config(config_path=os.path.join(config_dir, 'collect_games_config.json')):
    """加载 JSON 配置文件"""
    global CONFIG
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            CONFIG = json.load(f)
        logging.info(f"成功从 {config_path} 加载配置。")
    except FileNotFoundError:
        logging.error(f"配置文件未找到: {config_path}。请确保配置文件存在。")
        CONFIG = {} # 使用空配置继续，可能导致错误
    except json.JSONDecodeError as e:
        logging.error(f"解析配置文件 {config_path} 时出错: {e}。请检查 JSON 格式。")
        CONFIG = {}
    except Exception as e:
        logging.error(f"加载配置文件 {config_path} 时发生未知错误: {e}")
        CONFIG = {}

# --- 动态导入爬虫和匹配器模块 ---
if script_dir not in sys.path:
    sys.path.append(script_dir)

fetch_taptap_func = None
fetch_16p_func = None
match_versions_func = None

try: from taptap_selenium import get_taptap_games_for_date; fetch_taptap_func = get_taptap_games_for_date; logging.info("成功导入 taptap_selenium 模块。")
except ImportError as e: logging.error(f"导入 taptap_selenium 失败: {e}")
try:
    from p16_selenium import get_16p_data
    fetch_16p_func = get_16p_data
    logging.info("成功导入 p16_selenium 模块。")
except ImportError as e:
     logging.error(f"导入 p16_selenium 失败: {e} - 请确保文件已重命名为 p16_selenium.py")
try: from version_matcher import match_version_numbers_for_games; match_versions_func = match_version_numbers_for_games; logging.info("成功导入 version_matcher 模块。")
except ImportError as e: logging.error(f"导入 version_matcher 失败: {e}")


# --- 辅助函数 ---
def clean_game_name(name):
    """根据配置清理游戏名称"""
    if not name: return "未知名称"
    
    cfg = CONFIG.get('game_name_cleaning', {})
    norm_form = cfg.get('normalize_unicode_form', 'NFKC')
    remove_patterns = cfg.get('remove_patterns_regex', [])
    
    # 1. Unicode 规范化
    try:
        normalized_name = unicodedata.normalize(norm_form, str(name))
    except (TypeError, ValueError) as e:
        logging.warning(f"Unicode规范化失败 ('{name}', form='{norm_form}'): {e}")
        normalized_name = str(name) # Fallback
        
    cleaned = normalized_name
    # 2. 应用正则表达式移除模式
    for pattern in remove_patterns:
        try:
            # Check if pattern ends with flags like '$i' (case-insensitive)
            flags = 0
            if pattern.endswith('$'): # Assume case-insensitive if ends with $
                 flags = re.IGNORECASE
                 # Remove flag marker if present (simple check)
                 if len(pattern) > 1 and pattern[-2] == 'i': pattern = pattern[:-2]
                 else: pattern = pattern[:-1] # Just remove $
            
            cleaned = re.sub(pattern, '', cleaned, flags=flags)
        except re.error as e:
             logging.warning(f"应用名称清理正则失败 ('{pattern}'): {e}")
             
    # 3. 替换多个空格为单个空格
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # 4. 去除首尾空格
    cleaned = cleaned.strip()
    
    # 如果清理后为空，返回原始名称（规范化后）
    return cleaned if cleaned else normalized_name.strip()

def standardize_status(status):
    """根据配置标准化游戏状态"""
    if not isinstance(status, str):
        status = str(status)
    
    status_trimmed = status.strip()
    if not status_trimmed: # Handle empty status
        return "未知状态"
        
    status_lower = status_trimmed.lower()
    
    cfg = CONFIG.get('status_standardization', {})

    # 按优先级检查配置中的关键词
    # 1. 招募
    if any(keyword in status_trimmed for keyword in cfg.get('keywords_recruit', [])):
        return cfg.get('status_recruit', status_trimmed) # Default to trimmed if status not in cfg
        
    # 2. 不删档
    if any(keyword in status_lower for keyword in cfg.get('keywords_no_delete', [])):
        return cfg.get('status_no_delete', status_trimmed)
        
    # 3. 其他测试
    if any(keyword in status_lower for keyword in cfg.get('keywords_test', [])):
        return cfg.get('status_test', status_trimmed)
        
    # 4. 预约
    if any(keyword in status_lower for keyword in cfg.get('keywords_preorder', [])):
        return cfg.get('status_preorder', status_trimmed)
        
    # 5. 上线
    if any(keyword in status_lower for keyword in cfg.get('keywords_online', [])):
        return cfg.get('status_online', status_trimmed)
        
    # 6. 更新
    if any(keyword in status_lower for keyword in cfg.get('keywords_update', [])):
        return cfg.get('status_update', status_trimmed)

    # 7. 默认返回
    logging.debug(f"状态 '{status_trimmed}' 未匹配任何标准化规则，返回原始值。")
    return status_trimmed

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
        # Calculate cleaned name once
        cleaned_name_val = game.get("cleaned_name") or clean_game_name(game.get("name", "未知名称"))
        std_game["name"] = cleaned_name_val # Use the cleaned name for 'name'
        std_game["cleaned_name"] = cleaned_name_val # Explicitly add the 'cleaned_name' field
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

def _filter_appstore_games(games_list, is_history_data=False):
    """根据配置过滤 AppStore 特定记录"""
    cfg = CONFIG.get('appstore_filter', {})
    if not cfg.get('enabled', False):
        logging.info("AppStore 过滤已禁用。")
        return games_list
        
    filter_type = "历史数据" if is_history_data else "新数据"
    logging.info(f"--- 开始过滤 {filter_type} 中的 AppStore 特定记录 --- ")
    
    max_spaces = cfg.get('max_spaces_in_name', 1)
    max_len = cfg.get('max_cleaned_name_length', 10)
    major_keywords = set(cfg.get('major_publisher_keywords', [])) # Use set for faster lookup
    blocked_publishers = set(p.lower() for p in cfg.get('blocked_publishers', [])) # Lowercase blocked publishers
    
    filtered_games = []
    removed_count = 0
    
    for game in games_list:
        # Ensure cleaned_name exists (important for filtering logic)
        if 'cleaned_name' not in game:
             game['cleaned_name'] = clean_game_name(game.get('name'))
             
        source = game.get('source', '').strip().lower()
        original_name = game.get('name', '')
        cleaned_name = game.get('cleaned_name', '')
        publisher_lower = game.get('publisher', '').strip().lower()

        # Check blocked publishers first (applies to all sources potentially)
        if publisher_lower in blocked_publishers:
            logging.info(f"  过滤 {filter_type} (阻止的发行商): '{original_name}' [发行: {game.get('publisher')}] ")
            removed_count += 1
            continue

        # Apply specific AppStore filter rules
        if source == 'appstore':
            too_many_spaces = original_name.count(' ') > max_spaces
            too_long = len(cleaned_name) > max_len
            is_major_publisher = any(keyword in publisher_lower for keyword in major_keywords)

            if (too_many_spaces or too_long) and not is_major_publisher:
                reason = []
                if too_many_spaces: reason.append(f"空格多于{max_spaces}")
                if too_long: reason.append(f"名称长于{max_len}")
                logging.info(f"  过滤 {filter_type} AppStore 记录: '{original_name}' [发行: {game.get('publisher')}] (原因: { '/'.join(reason) })")
                removed_count += 1
                continue # Skip this game
                
        # If not filtered, add to the list
        filtered_games.append(game)

    logging.info(f"{filter_type} AppStore 过滤完成，移除了 {removed_count} 条记录。剩余记录: {len(filtered_games)}")
    return filtered_games

def _calculate_richness(game_dict):
    """计算字典中非空/非False值的数量，用于比较丰富度"""
    return sum(1 for v in game_dict.values() if v not in [None, '', False, 0, 0.0])

def _deduplicate_games(combined_games, locked_records):
    """根据配置对合并后的游戏列表进行去重"""
    logging.info("--- 开始处理重复项 --- ")
    cfg = CONFIG.get('deduplication', {})
    source_priority_list = [src.lower() for src in cfg.get('source_priority', [])]
    compare_richness = cfg.get('compare_richness', True)
    
    unique_milestones = {}
    duplicates_info = {'skipped_locked_conflict': 0, 'replaced_by_source': 0, 'replaced_by_richness': 0, 'kept_existing': 0}
    
    # 1. Locked records have highest priority
    processed_keys = set(locked_records.keys())
    unique_milestones.update(locked_records)
    logging.info(f"保留 {len(locked_records)} 条锁定记录。")
    
    # 2. Process remaining games
    games_to_process = [g for g in combined_games if (g.get('cleaned_name'), g.get('date', '0000-00-00')) not in processed_keys]
    logging.info(f"处理 {len(games_to_process)} 条非锁定记录... ")
    
    for game in games_to_process:
        # Ensure cleaned_name exists
        if 'cleaned_name' not in game:
            game['cleaned_name'] = clean_game_name(game.get('name'))
            
        name = game.get('cleaned_name')
        date = game.get('date', '0000-00-00')
        key = (name, date)
        
        # Should not happen based on pre-filtering, but double-check
        if key in processed_keys: 
             duplicates_info['skipped_locked_conflict'] += 1
             logging.warning(f"发现非锁定记录 {key} 与已处理的锁定键冲突，跳过。这不应发生。")
             continue 
             
        if key not in unique_milestones:
            unique_milestones[key] = game
            processed_keys.add(key)
        else:
            existing_game = unique_milestones[key]
            new_source = game.get('source', '').strip().lower()
            existing_source = existing_game.get('source', '').strip().lower()
            
            logging.debug(f"去重检查: Key={key}")
            logging.debug(f"  新记录: source='{new_source}', status='{game.get('status')}'")
            logging.debug(f"  旧记录: source='{existing_source}', status='{existing_game.get('status')}'")
            
            replaced = False
            reason = "Kept Existing"

            # Apply Source Priority
            new_priority = -1
            existing_priority = -1
            try: new_priority = source_priority_list.index(new_source) 
            except ValueError: pass
            try: existing_priority = source_priority_list.index(existing_source) 
            except ValueError: pass

            if new_priority != -1 and (existing_priority == -1 or new_priority < existing_priority):
                logging.debug(f"  决策: 按来源优先级替换 (新: {new_source} @{new_priority}, 旧: {existing_source} @{existing_priority})")
                unique_milestones[key] = game
                replaced = True
                reason = "Replaced by Source Priority"
                duplicates_info['replaced_by_source'] += 1
            elif existing_priority != -1 and (new_priority == -1 or existing_priority < new_priority):
                 logging.debug(f"  决策: 按来源优先级保留旧记录 (新: {new_source} @{new_priority}, 旧: {existing_source} @{existing_priority})")
                 replaced = False # Kept existing based on source priority
                 reason = "Kept Existing (Source Priority)"
                 duplicates_info['kept_existing'] += 1
            # If sources don't decide or compare_richness is False, keep existing unless richness comparison applies
            elif compare_richness:
                new_richness = _calculate_richness(game)
                existing_richness = _calculate_richness(existing_game)
                logging.debug(f"  比较丰富度: 新={new_richness}, 旧={existing_richness}")
                if new_richness > existing_richness:
                    logging.debug("  决策: 按丰富度替换")
                    unique_milestones[key] = game
                    replaced = True
                    reason = "Replaced by Richness"
                    duplicates_info['replaced_by_richness'] += 1
                else:
                    logging.debug("  决策: 按丰富度保留旧记录")
                    replaced = False # Keep existing due to richness
                    reason = "Kept Existing (Richness or Equal)"
                    duplicates_info['kept_existing'] += 1
            else:
                 # Keep existing if source didn't decide and richness comparison disabled
                 logging.debug("  决策: 来源未定且丰富度比较已禁用，保留旧记录")
                 replaced = False
                 reason = "Kept Existing (No Deciding Rule)"
                 duplicates_info['kept_existing'] += 1
                 
            # logging.debug(f"  最终: {reason}") # Simplified log below

    final_list = list(unique_milestones.values())
    total_processed_duplicates = duplicates_info['replaced_by_source'] + duplicates_info['replaced_by_richness'] + duplicates_info['kept_existing']
    logging.info(f"去重完成。最终保留 {len(final_list)} 条记录。")
    logging.info(f"  去重统计: 因锁定跳过={duplicates_info['skipped_locked_conflict']}, 按来源替换={duplicates_info['replaced_by_source']}, 按丰富度替换={duplicates_info['replaced_by_richness']}, 保留旧记录={duplicates_info['kept_existing']} (总冲突处理={total_processed_duplicates})" )
    
    return final_list

def _resolve_online_conflicts(games_list):
    """根据配置处理同一个游戏有多个'上线'状态记录的冲突"""
    logging.info("--- 开始处理上线日期冲突 --- ")
    cfg = CONFIG.get('online_conflict', {})
    strategy = cfg.get('strategy', 'log_only') # Default to just logging if not specified
    note_latest = cfg.get('note_for_latest', '冲突-最新上线')
    note_old = cfg.get('note_for_old', '历史上线(冲突)')
    # status_old = cfg.get('change_status_for_old') # Optional: change status instead of note

    if strategy == 'disabled':
        logging.info("上线冲突处理已禁用。")
        return games_list

    # Group games by name (assuming name is the primary identifier for a game)
    games_grouped = {}
    for game in games_list:
        # Use cleaned_name if available, otherwise clean again
        name = game.get('cleaned_name') or clean_game_name(game.get('name'))
        if 'cleaned_name' not in game: game['cleaned_name'] = name # Ensure it exists
        
        if name not in games_grouped:
            games_grouped[name] = []
        games_grouped[name].append(game)

    conflict_resolved_count = 0
    processed_list_after_conflict = [] # Build the final list here

    for name, group in games_grouped.items():
        # Find records with '上线' status within the group
        # Use configured status value for online
        status_online = CONFIG.get('status_standardization', {}).get('status_online', '上线')
        online_records = [g for g in group if g.get('status') == status_online]

        if len(online_records) > 1:
            logging.warning(f"游戏 '{name}' 发现 {len(online_records)} 条上线记录冲突: {[g.get('date') for g in online_records]}")
            conflict_resolved_count += 1

            if strategy == 'log_only':
                logging.info(f"  策略 '{strategy}': 仅记录冲突，不修改记录。")
                # Add all records from the group to the final list without modification
                processed_list_after_conflict.extend(group)
                continue # Move to the next group
            
            elif strategy == 'add_note_keep_latest':
                logging.info(f"  策略 '{strategy}': 保留最新日期记录，为冲突记录添加备注。")
                # Sort online records by date, latest first
                online_records.sort(key=lambda g: g.get('date', '0000-00-00'), reverse=True)
                
                latest_online_record = online_records[0]
                logging.info(f"    保留最新上线记录: {latest_online_record.get('date')}")
                # Add note to the latest record's manual_checked field
                # Append note if field already has content, otherwise set it
                existing_note_latest = latest_online_record.get('manual_checked', '')
                if existing_note_latest and note_latest not in existing_note_latest:
                     latest_online_record['manual_checked'] = f"{existing_note_latest}; {note_latest}"
                elif not existing_note_latest:
                     latest_online_record['manual_checked'] = note_latest
                
                # Process older online records
                for old_record in online_records[1:]:
                    logging.info(f"    处理旧上线记录: {old_record.get('date')}")
                    # Option 1: Add note to manual_checked (current default in config)
                    existing_note_old = old_record.get('manual_checked', '')
                    if existing_note_old and note_old not in existing_note_old:
                         old_record['manual_checked'] = f"{existing_note_old}; {note_old}"
                    elif not existing_note_old:
                         old_record['manual_checked'] = note_old
                    
                    # Option 2: Change status (if status_old is defined in config)
                    # status_old_cfg = cfg.get('change_status_for_old') 
                    # if status_old_cfg:
                    #     logging.info(f"      状态从 '{status_online}' 修改为 '{status_old_cfg}'")
                    #     old_record['status'] = status_old_cfg
                
                # Add all records from the group (potentially modified) to the final list
                processed_list_after_conflict.extend(group)
            
            # Add other strategies here if needed
            # elif strategy == 'other_strategy':
            #     ...
            
            else:
                 logging.warning(f"  未知的上线冲突处理策略: '{strategy}'。不修改记录。")
                 processed_list_after_conflict.extend(group)
                 
        else:
            # No conflict in this group, add all its records to the final list
            processed_list_after_conflict.extend(group)

    if conflict_resolved_count > 0:
        logging.info(f"处理了 {conflict_resolved_count} 个游戏的上线日期冲突。")
    else:
        logging.info("未发现上线日期冲突。")
        
    return processed_list_after_conflict

# --- Data Loading Functions ---

def _load_excel_data(master_excel_file, excel_columns_map):
    """加载主 Excel 文件，返回所有记录列表、锁定记录字典和重点标记字典"""
    all_excel_records = [] # List to store all records read
    locked_records = {}
    excel_feature_flags = {}
    if not os.path.exists(master_excel_file):
        logging.info(f"主 Excel 文件 {master_excel_file} 不存在。")
        return all_excel_records, locked_records, excel_feature_flags
        
    try:
        logging.info(f"读取主 Excel 文件: {master_excel_file}")
        df_excel = pd.read_excel(master_excel_file, engine='openpyxl', dtype=str)
        excel_rename_map_reverse = {v: k for k, v in excel_columns_map.items()}
        df_excel.rename(columns=lambda c: excel_rename_map_reverse.get(c, c), inplace=True)

        if 'rating' in df_excel.columns: 
             df_excel['rating'] = pd.to_numeric(df_excel['rating'], errors='coerce').fillna(0.0)
        is_featured_col = '是否重点'
        version_checked_col = '版号已查'
        manual_checked_col = '是否人工校对'
        
        excel_records_list = df_excel.to_dict('records')

        for record in excel_records_list:
            # Create a dictionary for the current record using internal field names
            current_game_record = {}
            name = clean_game_name(record.get('名称', ''))
            date_raw = record.get('日期')
            try:
                if isinstance(date_raw, datetime): date_str = date_raw.strftime('%Y-%m-%d')
                elif isinstance(date_raw, str): date_str = pd.to_datetime(date_raw).strftime('%Y-%m-%d')
                else: date_str = "0000-00-00"
            except Exception:
                 date_str = str(date_raw)[:10] 
                 logging.warning(f"无法标准化Excel日期 '{date_raw}' for game '{name}', 使用 '{date_str}'")
            key = (name, date_str)

            is_featured_excel = str(record.get(is_featured_col, '')).strip().lower() in ['true', '是', 'yes', '1']
            is_manually_checked = str(record.get(manual_checked_col, '')).strip().lower() in ['true', '是', 'yes', '1']

            # Populate the record dict with all fields
            for excel_field, internal_field in excel_columns_map.items():
                value = record.get(excel_field)
                if internal_field == 'rating': current_game_record[internal_field] = float(value) if pd.notna(value) else 0.0
                elif internal_field == 'is_featured': current_game_record[internal_field] = is_featured_excel
                elif internal_field == 'version_checked': current_game_record[internal_field] = str(record.get(version_checked_col, '')).strip().lower() in ['true', '是', 'yes', '1'] if version_checked_col in record else False
                elif internal_field == 'manual_checked': current_game_record[internal_field] = str(record.get(manual_checked_col, '')).strip() # Keep original string
                else: current_game_record[internal_field] = str(value).strip() if pd.notna(value) else ""
            
            current_game_record['name'] = name # Ensure cleaned name is used
            current_game_record['date'] = date_str # Ensure standardized date is used
            current_game_record['cleaned_name'] = name # Add cleaned_name field
            
            all_excel_records.append(current_game_record) # Add to the full list
            excel_feature_flags[key] = is_featured_excel # Store feature flag
            
            if is_manually_checked:
                locked_records[key] = current_game_record # Add to locked records if checked

        featured_count = sum(1 for flag in excel_feature_flags.values() if flag)
        logging.info(f"从主 Excel 加载了 {len(all_excel_records)} 条记录，其中 {len(locked_records)} 条为人工校对记录，{featured_count} 条标记为重点。")
        
    except Exception as e:
        logging.error(f"读取或处理主 Excel 文件 ({master_excel_file}) 时出错: {e}", exc_info=True)
        return [], {}, {} # Return empty on error
        
    return all_excel_records, locked_records, excel_feature_flags

def _fetch_new_data(fetch_taptap, fetch_16p):
    """根据选择调用爬虫并加载新数据"""
    newly_fetched_games = []
    current_date_str = datetime.now().strftime("%Y-%m-%d")

    if fetch_taptap and fetch_taptap_func:
        logging.info("--- 开始获取 TapTap 数据 --- ")
        try:
            taptap_new_count = fetch_taptap_func(current_date_str)
            if taptap_new_count > 0:
                taptap_file = os.path.join(data_dir, f'taptap_games_{current_date_str}.jsonl')
                if os.path.exists(taptap_file):
                    with open(taptap_file, 'r', encoding='utf-8') as f_tap:
                        tap_games_list = [json.loads(line) for line in f_tap]
                    logging.info(f"成功从 TapTap ({current_date_str}) 获取 {len(tap_games_list)} 条新数据。")
                    newly_fetched_games.extend(tap_games_list)
                else: logging.warning(f"TapTap 脚本报告成功，但未找到文件: {taptap_file}")
            else: logging.info(f"TapTap ({current_date_str}) 未获取到新数据或脚本返回0。")
        except Exception as e: logging.error(f"获取 TapTap 数据时出错: {e}", exc_info=True)
    elif fetch_taptap: logging.warning("TapTap 模块未加载，跳过爬取。")
    else: logging.info("根据用户选择，跳过 TapTap 数据获取。")

    if fetch_16p and fetch_16p_func:
        logging.info("--- 开始获取 16p (好游快爆/AppStore) 数据 --- ")
        try:
            p16_new_count = fetch_16p_func()
            if p16_new_count > 0:
                # Find the latest p16 file (assuming naming convention)
                p16_files = sorted([f for f in os.listdir(data_dir) if f.startswith('p16_games_') and f.endswith('.jsonl')], reverse=True)
                if p16_files:
                    latest_p16_file = os.path.join(data_dir, p16_files[0])
                    with open(latest_p16_file, 'r', encoding='utf-8') as f_16p:
                         p16_games_list = [json.loads(line) for line in f_16p]
                    logging.info(f"成功从 16p ({p16_files[0]}) 获取 {len(p16_games_list)} 条新数据。")
                    # Ensure date field is present (using status_date or current as fallback)
                    for game in p16_games_list:
                        if 'date' not in game or not game['date']: 
                             game['date'] = game.get('status_date') or current_date_str
                    newly_fetched_games.extend(p16_games_list)
                else: logging.warning(f"16p 脚本报告成功，但未在 data 目录找到 p16_games 文件。")
            else: logging.info("16p 未获取到新数据或脚本返回0。")
        except Exception as e: logging.error(f"获取 16p 数据时出错: {e}", exc_info=True)
    elif fetch_16p: logging.warning("16p 模块未加载，跳过爬取。")
    else: logging.info("根据用户选择，跳过 16p 数据获取。")

    logging.info(f"总共获取到 {len(newly_fetched_games)} 条新游戏数据。")
    return newly_fetched_games
    
def _run_version_matching(games_list, locked_records, description="数据"):
    """对未锁定的游戏运行版号匹配并合并结果"""
    if not match_versions_func or not games_list:
        if not match_versions_func: logging.warning(f"版号匹配模块未导入，跳过 {description} 匹配。")
        else: logging.info(f"没有需要进行版号匹配的 {description}。")
        return games_list # Return original list if no matching needed/possible
        
    games_to_match = []
    original_indices = {} 
    skipped_locked_count = 0
    
    for i, game in enumerate(games_list):
         if 'cleaned_name' not in game: game['cleaned_name'] = clean_game_name(game.get('name'))
         name = game['cleaned_name']
         date = game.get('date', '0000-00-00')
         key = (name, date)
         
         # --- Check against locked_records --- 
         if key in locked_records:
             skipped_locked_count += 1
             continue # Skip locked records
             
         matcher_index = len(games_to_match)
         original_indices[matcher_index] = i
         games_to_match.append({"name": name, "_original_index": matcher_index})

    if skipped_locked_count > 0:
         logging.info(f"版号匹配：跳过 {skipped_locked_count} 条已锁定记录 ({description})。")

    if not games_to_match:
        logging.info(f"没有需要进行版号匹配的未锁定 {description}。")
        return games_list
        
    logging.info(f"--- 开始对 {len(games_to_match)} 条未锁定 {description} 进行版号匹配 --- ")
    try:
        match_versions_func(games_to_match) # Modifies games_to_match in place
        
        matched_count = 0
        for matched_info in games_to_match:
            matcher_idx = matched_info.get("_original_index", -1)
            original_idx = original_indices.get(matcher_idx, -1)
            
            if original_idx != -1 and original_idx < len(games_list):
                target_game = games_list[original_idx]
                update_data = {k: v for k, v in matched_info.items() if k not in ['name', '_original_index']}
                target_game.update(update_data)
                target_game['version_checked'] = True 
                if update_data.get('approval_num'):
                     matched_count += 1
            else:
                 logging.warning(f"无法将版号匹配结果合并回索引 {original_idx} (匹配器索引 {matcher_idx}) 的原始记录。")
                 
        logging.info(f"{description} 版号匹配完成，成功匹配 {matched_count} 条。")
    except Exception as e:
        logging.error(f"{description} 版号匹配过程中出错: {e}", exc_info=True)

    return games_list
    
def _save_results(final_games_list, master_json_file, master_excel_file, excel_columns_map):
    """保存最终结果到 JSON 和 Excel 文件"""
    logging.info("--- 保存最终结果 (覆盖主文件) --- ")
    # Save JSON
    try:
        with open(master_json_file, 'w', encoding='utf-8') as f:
            json.dump(final_games_list, f, ensure_ascii=False, indent=2)
        logging.info(f"最终数据已覆盖保存到 {master_json_file}")
    except Exception as e: 
        logging.error(f"保存最终 JSON 数据时出错: {e}", exc_info=True)

    # Save Excel
    try:
        df_final = pd.DataFrame(final_games_list)
        internal_fields = list(excel_columns_map.values())

        # Ensure all expected columns exist
        for field in internal_fields:
            if field not in df_final.columns:
                if field == 'rating': df_final[field] = 0.0
                elif field in ['is_featured', 'version_checked']: df_final[field] = False
                else: df_final[field] = ''

        cols_to_export = [col for col in internal_fields if col in df_final.columns]
        df_final_excel = df_final[cols_to_export].copy()

        # Format boolean columns for Excel
        for col in ['is_featured', 'version_checked']:
            if col in df_final_excel.columns:
                 df_final_excel[col] = df_final_excel[col].apply(
                     lambda x: '是' if x is True or str(x).strip().lower() in ['true', '是', 'yes', '1'] else ''
                 )
        # Handle manual_checked notes correctly
        if 'manual_checked' in df_final_excel.columns:
             df_final_excel['manual_checked'] = df_final_excel['manual_checked'].astype(str).fillna('')
             # Only convert simple True/Yes/1 to '是', keep other notes
             df_final_excel['manual_checked'] = df_final_excel['manual_checked'].apply(
                 lambda x: '是' if x.lower() in ['true', 'yes', '1'] else x
             )

        df_final_excel.rename(columns={v: k for k, v in excel_columns_map.items()}, inplace=True)
        df_final_excel.to_excel(master_excel_file, index=False, engine='openpyxl')
        logging.info(f"最终数据已覆盖保存到 Excel: {master_excel_file}")
    except ImportError:
        logging.error("需要安装 'pandas' 和 'openpyxl' 才能导出 Excel。")
    except Exception as e: 
        logging.error(f"导出最终 Excel 数据时出错: {e}", exc_info=True)

# --- Refactored Core Data Processing (Excel-Centric) ---
def collect_all_game_data(fetch_taptap=True, fetch_16p=True, process_history_only=False):
    load_config()
    if not CONFIG:
        logging.error("无法加载配置, 脚本无法继续运行。")
        return

    start_time = time.time()
    task_description = "基于Excel历史整理与版号匹配" if process_history_only else "爬取新数据并与Excel整合"
    logging.info(f"{'='*20} 开始执行任务: {task_description} {'='*20}")

    master_excel_file = os.path.join(data_dir, "all_games_data.xlsx")
    master_json_file = os.path.join(data_dir, "all_games.json") # Still used for output
    excel_columns_map = get_excel_columns()

    final_games_list = []
    execution_successful = False

    try:
        # 1. Load Base Data From Excel
        base_data_from_excel, locked_records, excel_feature_flags = _load_excel_data(master_excel_file, excel_columns_map)
        # JSON history is no longer loaded as input
        # existing_games_from_json = _load_json_history(...) # REMOVED

        if process_history_only:
            logging.info("模式: 只处理 Excel 数据。")
            games_to_process = base_data_from_excel # Start with all Excel data
            if not games_to_process:
                logging.warning("Excel 数据为空，无法处理。")
                temp_final_list = []
            else:
                # Clean names (ensure cleaned_name exists)
                # Note: _load_excel_data already does cleaning and adds cleaned_name
                logging.info("--- 对 Excel 数据进行过滤和匹配 --- ")
                
                # Separate locked/unlocked from Excel data
                unlocked_excel_data = [g for g in games_to_process if (g.get('cleaned_name'), g.get('date', '0000-00-00')) not in locked_records]
                
                # Filter unlocked Excel data
                filtered_unlocked_excel = _filter_appstore_games(unlocked_excel_data, is_history_data=True)
                
                # Run version matching on filtered, unlocked Excel data
                # Pass locked_records to allow skipping inside the function
                matched_unlocked_excel = _run_version_matching(filtered_unlocked_excel, locked_records, description="Excel历史数据")
                
                # Combine locked + matched unlocked for deduplication (handles potential duplicates within Excel)
                combined_excel_for_dedup = list(locked_records.values()) + matched_unlocked_excel
                deduplicated_list = _deduplicate_games(combined_excel_for_dedup, locked_records)
                
                # Standardize the deduplicated list
                logging.info("--- 标准化最终 Excel 数据 --- ")
                temp_final_list = standardize_game_data(deduplicated_list, excel_columns_map)
                # Re-apply feature flags (should be preserved from _load_excel_data, but safe check)
                for game in temp_final_list: 
                    key = (game.get('cleaned_name'), game.get('date'))
                    game['is_featured'] = excel_feature_flags.get(key, False)
                        
        else: # Fetch new data mode
            logging.info("模式: 爬取新数据并与 Excel 数据整合。")
            # 2. Fetch New Data
            newly_fetched_games = _fetch_new_data(fetch_taptap, fetch_16p)
            
            # 3. Process New Data
            logging.info("--- 处理新获取的数据 --- ")
            processed_new_games = []
            if newly_fetched_games:
                # Clean names
                for game in newly_fetched_games: 
                     if 'cleaned_name' not in game: game['cleaned_name'] = clean_game_name(game.get('name'))
                # Filter 
                filtered_new_games = _filter_appstore_games(newly_fetched_games, is_history_data=False)
                # Match versions (non-locked only)
                processed_new_games = _run_version_matching(filtered_new_games, locked_records, description="新数据")
                # Standardize 
                processed_new_games = standardize_game_data(processed_new_games, excel_columns_map)
                # Apply feature flags to standardized new data based on Excel flags (if name/date matches)
                for std_game in processed_new_games:
                    key = (std_game['cleaned_name'], std_game['date'])
                    if key not in locked_records: # Only apply if not locked
                        std_game['is_featured'] = excel_feature_flags.get(key, False)
                            
            # 4. Merge & Deduplicate All (Base Excel + Processed New)
            logging.info("--- 开始合并 Excel 基础数据和处理后的新数据 --- ")
            # Use base_data_from_excel which contains ALL original excel rows (locked and unlocked)
            # Use processed_new_games which contains standardized, matched, filtered new games
            combined_games = base_data_from_excel + processed_new_games 
            logging.info(f"合并后共 {len(combined_games)} 条数据待去重。")
            temp_final_list = _deduplicate_games(combined_games, locked_records)

        # --- Common Post-Processing Steps --- #
        if not temp_final_list:
            logging.warning("最终数据列表为空，流程结束。")
        else:
            # 5. Resolve Online Conflicts (Applied to the deduplicated list)
            resolved_list = _resolve_online_conflicts(temp_final_list)
            
            # 6. Sort
            logging.info("--- 按日期倒序排列数据 ---")
            resolved_list.sort(key=lambda x: x.get('date', '0000-00-00'), reverse=True)
            
            final_games_list = resolved_list
            execution_successful = True

    except Exception as main_error:
        logging.error("="*20 + " 数据处理流程中发生严重错误 " + "="*20, exc_info=True)
        logging.error("由于发生错误，将不会更新主数据文件。")
        # execution_successful remains False

    finally:
        # Save results if successful
        if execution_successful and final_games_list:
            _save_results(final_games_list, master_json_file, master_excel_file, excel_columns_map)
        elif execution_successful and not final_games_list:
             logging.warning("处理流程成功但最终列表为空，不执行保存操作。")
        elif not execution_successful:
             logging.info("处理流程未成功完成，跳过保存操作。")

        logging.info(f"任务结束，总耗时: {time.time() - start_time:.2f} 秒。")
        logging.info("="*50 + "\n")


# --- Main Execution Guard ---
def main():
    """主函数，解析命令行参数并调用核心处理函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='游戏数据收集工具')
    parser.add_argument('--no-taptap', action='store_true', help='跳过 TapTap 数据获取')
    parser.add_argument('--no-16p', action='store_true', help='跳过 16p (好游快爆/AppStore) 数据获取')
    parser.add_argument('--history-only', action='store_true', help='只处理历史数据，不爬取新数据')
    
    args = parser.parse_args()
    
    # 调用核心处理函数
    collect_all_game_data(
        fetch_taptap=not args.no_taptap,
        fetch_16p=not args.no_16p,
        process_history_only=args.history_only
    )

if __name__ == "__main__":
    main() # main function itself remains unchanged 