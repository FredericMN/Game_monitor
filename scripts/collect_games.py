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
import shutil # Added for backup before analysis

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
# --- Add import for the analysis script --- 
try:
    from analyze_game_updates import analyze_and_remove_old_tests
    logging.info("成功导入 analyze_game_updates 模块。")
except ImportError as e:
    analyze_and_remove_old_tests = None # Set to None if import fails
    logging.warning(f"导入 analyze_game_updates 失败，无法执行测试间隔清理: {e}")


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
    processed_keys = set(locked_records.keys()) # Keys from locked records
    unique_milestones.update(locked_records)    # Add locked records first
    logging.info(f"保留 {len(locked_records)} 条锁定记录。")
    
    # 2. Process remaining games - Refined Filtering
    # Filter out games whose keys ALREADY match a locked key more explicitly
    games_to_process = []
    keys_added_to_process = set() # Track keys of non-locked items we decide to process

    for g in combined_games:
        # Ensure cleaned_name exists for key calculation, especially for new data
        name_for_key = g.get('cleaned_name')
        if not name_for_key:
             name_for_key = clean_game_name(g.get('name'))
             if 'cleaned_name' not in g: # Store back if newly calculated
                 g['cleaned_name'] = name_for_key

        date_for_key = g.get('date', '0000-00-00')
        current_key = (name_for_key, date_for_key)

        is_locked_key = current_key in processed_keys

        # Only add if the key doesn't belong to a locked record
        # AND we haven't already added another non-locked record with the same key
        if not is_locked_key:
            if current_key not in keys_added_to_process:
                games_to_process.append(g)
                keys_added_to_process.add(current_key)
            # else: # Debugging log (optional): Found another non-locked item with the same key, skipping.
            #    logging.debug(f"过滤步骤：跳过重复的非锁定键 {current_key} 来自记录: {g.get('name')}")

    logging.info(f"筛选后准备处理 {len(games_to_process)} 条候选记录 (非锁定且键唯一)。") # Log count after filtering

    # 3. Process the filtered list
    for game in games_to_process:
        # We no longer need to check if 'key in processed_keys' here,
        # because the filtering step above should have removed all conflicts with locked keys.
        # Ensure cleaned_name exists (might be redundant but safe)
        if 'cleaned_name' not in game:
            game['cleaned_name'] = clean_game_name(game.get('name'))

        name = game.get('cleaned_name')
        date = game.get('date', '0000-00-00')
        key = (name, date)

        # The key should either be new or already exist from another non-locked record added in this loop
        if key not in unique_milestones:
            unique_milestones[key] = game
        else:
            # This is the intended deduplication for non-locked items with the same key
            existing_game = unique_milestones[key]
            new_source = game.get('source', '').strip().lower()
            existing_source = existing_game.get('source', '').strip().lower()

            logging.debug(f"去重检查 (非锁定间): Key={key}")
            logging.debug(f"  新记录: source='{new_source}', status='{game.get('status')}'")
            logging.debug(f"  旧记录 (已保留的非锁定): source='{existing_source}', status='{existing_game.get('status')}'")

            replaced = False
            reason = "Kept Existing Non-Locked"

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

    final_list = list(unique_milestones.values())
    # Note: 'skipped_locked_conflict' count is no longer relevant with the new filtering logic
    total_processed_duplicates = duplicates_info['replaced_by_source'] + duplicates_info['replaced_by_richness'] + duplicates_info['kept_existing']
    logging.info(f"去重完成。最终保留 {len(final_list)} 条记录。")
    # Removed skipped_locked_conflict from the final log message
    logging.info(f"  去重统计 (非锁定记录间): 按来源替换={duplicates_info['replaced_by_source']}, 按丰富度替换={duplicates_info['replaced_by_richness']}, 保留旧记录={duplicates_info['kept_existing']} (总冲突处理={total_processed_duplicates})" )

    return final_list

def _resolve_online_conflicts(games_list):
    """根据配置处理同一个游戏有多个'上线'状态记录的冲突"""
    logging.info("--- 开始处理上线日期冲突 --- ")
    cfg = CONFIG.get('online_conflict', {})
    strategy = cfg.get('strategy', 'log_only') # Default to just logging if not specified
    note_latest = cfg.get('note_for_latest', '冲突-最新上线')
    note_old = cfg.get('note_for_old', '历史上线(冲突)')
    appstore_source_name = cfg.get('appstore_source_identifier', 'appstore').lower() # Configurable AppStore source name

    if strategy == 'disabled':
        logging.info("上线冲突处理已禁用。")
        return games_list

    games_grouped = {}
    for game in games_list:
        name = game.get('cleaned_name') or clean_game_name(game.get('name'))
        if 'cleaned_name' not in game: game['cleaned_name'] = name
        if name not in games_grouped:
            games_grouped[name] = []
        games_grouped[name].append(game)

    conflict_resolved_count = 0
    final_processed_list = [] # Use a new list for the final output

    for name, original_group in games_grouped.items():
        status_online = CONFIG.get('status_standardization', {}).get('status_online', '上线')
        
        # Make a copy of the group to potentially modify
        current_group = list(original_group)
        
        # Initial check for online records in the current group state
        online_records = [g for g in current_group if g.get('status') == status_online]

        if len(online_records) > 1:
            logging.warning(f"游戏 '{name}' 发现 {len(online_records)} 条上线记录冲突: {[g.get('date') for g in online_records]}")
            conflict_resolved_count += 1

            # --- 新增逻辑: 处理 AppStore 来源冲突 --- 
            appstore_online_records = [g for g in online_records if g.get('source', '').lower() == appstore_source_name]
            non_appstore_online_records = [g for g in online_records if g.get('source', '').lower() != appstore_source_name]
            appstore_removed_count = 0

            if appstore_online_records and non_appstore_online_records:
                 logging.info(f"  检测到 AppStore 与其他来源的上线冲突。正在移除 {len(appstore_online_records)} 条 AppStore 上线记录。")
                 # Create a new group excluding the conflicting AppStore records
                 indices_to_remove = {current_group.index(g) for g in appstore_online_records if g in current_group}
                 new_group = [g for i, g in enumerate(current_group) if i not in indices_to_remove]
                 appstore_removed_count = len(current_group) - len(new_group)
                 current_group = new_group # Update the group being processed
                 # Re-evaluate online records after removal
                 online_records = [g for g in current_group if g.get('status') == status_online]
                 logging.info(f"  移除 AppStore 记录后，剩余 {len(online_records)} 条上线记录待处理。")
            # --- AppStore 逻辑结束 ---

            # --- 继续处理剩余的上线冲突 (如果还有 > 1条) --- 
            if len(online_records) > 1: 
                 # Check strategy only if there's still a conflict after potential AppStore removal
                 if strategy == 'log_only':
                     logging.info(f"  策略 '{strategy}': 仅记录剩余冲突，不修改记录。")
                     # Add the potentially modified group (with AppStore removed) to the final list
                     final_processed_list.extend(current_group)
                     continue # Move to the next group
                 
                 elif strategy == 'add_note_keep_latest':
                     logging.info(f"  策略 '{strategy}': 保留剩余冲突中最新日期记录，为其他冲突记录添加备注/改状态。")
                     # Sort remaining online records by date, latest first
                     online_records.sort(key=lambda g: g.get('date', '0000-00-00'), reverse=True)
                     
                     latest_online_record = online_records[0]
                     logging.info(f"    保留剩余冲突中的最新上线记录: {latest_online_record.get('date')}")
                     # Add note to the latest record
                     existing_note_latest = latest_online_record.get('manual_checked', '')
                     if existing_note_latest and note_latest not in existing_note_latest:
                         latest_online_record['manual_checked'] = f"{existing_note_latest}; {note_latest}"
                     elif not existing_note_latest:
                         latest_online_record['manual_checked'] = note_latest
                     
                     # Process older online records among the remaining ones
                     for old_record in online_records[1:]:
                         logging.info(f"    处理剩余冲突中的旧上线记录: {old_record.get('date')}")
                         # Add note
                         existing_note_old = old_record.get('manual_checked', '')
                         if existing_note_old and note_old not in existing_note_old:
                             old_record['manual_checked'] = f"{existing_note_old}; {note_old}"
                         elif not existing_note_old:
                             old_record['manual_checked'] = note_old
                         # Change status
                         old_record['status'] = "未知状态"
                         logging.info(f"      状态已修改为 '未知状态'")
                     
                     # Add the modified group (including non-online records and updated online ones) to the final list
                     final_processed_list.extend(current_group)
                 
                 else:
                     logging.warning(f"  未知的上线冲突处理策略: '{strategy}'。不修改剩余冲突记录。")
                     final_processed_list.extend(current_group)
            
            else: # <= 1 online record after potential AppStore removal, conflict resolved
                 if appstore_removed_count > 0:
                      logging.info(f"  移除 AppStore 记录后，上线冲突已解决。")
                 else: # This case shouldn't be reached if the initial check found > 1, but included for safety
                      logging.info(f"  冲突检查后无需进一步操作。")
                 final_processed_list.extend(current_group) # Add the potentially modified group

        else:
            # No initial conflict in this group, add all its records to the final list
            final_processed_list.extend(current_group)

    if conflict_resolved_count > 0:
        logging.info(f"处理了 {conflict_resolved_count} 个游戏的上线日期冲突。")
    else:
        logging.info("未发现上线日期冲突。")
        
    return final_processed_list # Return the newly built list

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
        # Use internal names directly if possible, otherwise map from Excel headers
        internal_to_excel = {v: k for k, v in excel_columns_map.items()}
        excel_cols_present = list(df_excel.columns)
        rename_map = {}
        for internal_name, excel_name in internal_to_excel.items():
            if excel_name in excel_cols_present:
                 rename_map[excel_name] = internal_name
            # Keep columns not in map as is for potential extra data
            # else:
            #     if internal_name not in excel_cols_present: # Avoid renaming if internal name already exists
            #         # If internal name isn't present either, we can't map easily, log?
            #         pass

        df_excel.rename(columns=rename_map, inplace=True)


        # Standardize specific columns after potential rename
        if 'rating' in df_excel.columns:
             df_excel['rating'] = pd.to_numeric(df_excel['rating'], errors='coerce').fillna(0.0)

        # Use internal names now for lookup
        is_featured_col = 'is_featured'
        version_checked_col = 'version_checked'
        manual_checked_col = 'manual_checked'
        name_col = 'name'
        date_col = 'date'
        cleaned_name_col = 'cleaned_name' # Assume cleaned_name might exist in Excel

        excel_records_list = df_excel.to_dict('records')

        for record in excel_records_list:
            # Create a dictionary for the current record using internal field names
            current_game_record = {}
            # Prioritize existing cleaned_name, else clean the 'name'
            original_name = record.get(name_col, '')
            if cleaned_name_col in record and pd.notna(record[cleaned_name_col]) and record[cleaned_name_col].strip():
                 name = record[cleaned_name_col].strip()
                 logging.debug(f"Using existing cleaned_name '{name}' from Excel for '{original_name}'")
            else:
                 name = clean_game_name(original_name)
                 if not name: name = str(original_name).strip() # Fallback if cleaning results in empty string
                 logging.debug(f"Cleaned name '{original_name}' to '{name}'")


            date_raw = record.get(date_col)
            try:
                # Handle various date representations
                if pd.isna(date_raw): date_str = "0000-00-00"
                elif isinstance(date_raw, datetime): date_str = date_raw.strftime('%Y-%m-%d')
                else: # Try converting string or number
                    date_str = pd.to_datetime(str(date_raw)).strftime('%Y-%m-%d')
            except Exception:
                 # Fallback: try to extract YYYY-MM-DD if possible, else keep raw
                 date_str = str(date_raw)[:10] if isinstance(date_raw, str) and len(date_raw) >= 10 else "0000-00-00"
                 logging.warning(f"无法标准化Excel日期 '{date_raw}' for game '{name}', 使用 '{date_str}'")
            key = (name, date_str)

            # Use internal column names now
            is_featured_excel = str(record.get(is_featured_col, '')).strip().lower() in ['true', '是', 'yes', '1']
            is_manually_checked = str(record.get(manual_checked_col, '')).strip() # Keep the string value for checking

            # Populate the record dict using internal field names mapped from config
            for internal_field in excel_columns_map.values():
                value = record.get(internal_field) # Direct access using internal name
                if internal_field == 'rating': current_game_record[internal_field] = float(value) if pd.notna(value) else 0.0
                elif internal_field == 'is_featured': current_game_record[internal_field] = is_featured_excel
                elif internal_field == 'version_checked': current_game_record[internal_field] = str(value).strip().lower() in ['true', '是', 'yes', '1'] if pd.notna(value) else False
                elif internal_field == 'manual_checked': current_game_record[internal_field] = str(value).strip() if pd.notna(value) else "" # Keep original string note
                else: current_game_record[internal_field] = str(value).strip() if pd.notna(value) else ""

            # Ensure essential fields are correctly set
            current_game_record[name_col] = name # Use the determined cleaned/existing name
            current_game_record[date_col] = date_str # Use standardized date
            current_game_record[cleaned_name_col] = name # Explicitly add/overwrite cleaned_name field

            all_excel_records.append(current_game_record) # Add to the full list
            excel_feature_flags[key] = is_featured_excel # Store feature flag

            # Check manual check status using the stored string value
            if is_manually_checked.lower() in ['true', '是', 'yes', '1']:
                 locked_records[key] = current_game_record # Add to locked records if checked

        featured_count = sum(1 for flag in excel_feature_flags.values() if flag)
        logging.info(f"从主 Excel 加载了 {len(all_excel_records)} 条记录，其中 {len(locked_records)} 条为人工校对记录，{featured_count} 条标记为重点。")

    except Exception as e:
        logging.error(f"读取或处理主 Excel 文件 ({master_excel_file}) 时出错: {e}", exc_info=True)
        return [], {}, {} # Return empty on error

    return all_excel_records, locked_records, excel_feature_flags

def _fetch_new_data(fetch_taptap, fetch_16p, process_history_only=False):
    """根据选择调用爬虫(如果不是 history_only 模式)并加载新数据"""
    newly_fetched_games = []
    current_date_str = datetime.now().strftime("%Y-%m-%d")
    taptap_output_file = os.path.join(data_dir, 'taptap_games.jsonl')
    p16_output_file = os.path.join(data_dir, 'p16_games.jsonl')

    # --- TapTap ---
    if fetch_taptap and fetch_taptap_func:
        if not process_history_only: # Only run scraper if not in history-only mode
             logging.info("--- (在线) 开始获取 TapTap 数据 --- ")
             try:
                 taptap_new_count_reported = fetch_taptap_func(current_date_str)
                 logging.info(f"TapTap 爬虫完成，报告新增 {taptap_new_count_reported} 条记录到文件。")
             except Exception as e:
                 logging.error(f"在线获取 TapTap 数据时出错: {e}", exc_info=True)
                 taptap_new_count_reported = 0 # Assume failure means 0 new
        else:
             logging.info("--- (本地) 跳过在线获取 TapTap 数据 (history-only模式) ---")
             taptap_new_count_reported = "(未执行)" # Indicate scraper didn't run

        # Always try to load from file
        logging.info(f"--- (本地) 开始加载 TapTap 文件: {taptap_output_file} ---")
        if os.path.exists(taptap_output_file):
            tap_all_games = []
            with open(taptap_output_file, 'r', encoding='utf-8') as f_tap:
                for line in f_tap:
                    try:
                        game = json.loads(line)
                        tap_all_games.append(game)
                    except json.JSONDecodeError:
                         logging.warning(f"解析 {os.path.basename(taptap_output_file)} 时跳过无效行: {line.strip()}")
            if tap_all_games:
                 logging.info(f"从 TapTap 文件加载了 {len(tap_all_games)} 条数据。")
                 newly_fetched_games.extend(tap_all_games)
            else:
                 logging.info(f"TapTap 文件为空或无法解析。爬虫报告新增 {taptap_new_count_reported} 条。")
        else:
            logging.warning(f"TapTap 数据文件 {taptap_output_file} 不存在。即使爬虫报告成功({taptap_new_count_reported}条)，也无法加载数据。")

    elif fetch_taptap: logging.warning("TapTap 模块未加载，跳过 TapTap 处理。")
    else: logging.info("根据用户选择，跳过 TapTap 数据处理。")


    # --- 16p ---
    if fetch_16p and fetch_16p_func:
        if not process_history_only: # Only run scraper if not in history-only mode
             logging.info("--- (在线) 开始获取 16p (好游快爆/AppStore) 数据 --- ")
             try:
                 p16_new_count_reported = fetch_16p_func()
                 logging.info(f"16p 爬虫完成，报告新增 {p16_new_count_reported} 条记录到文件。")
             except Exception as e:
                 logging.error(f"在线获取 16p 数据时出错: {e}", exc_info=True)
                 p16_new_count_reported = 0
        else:
             logging.info("--- (本地) 跳过在线获取 16p 数据 (history-only模式) ---")
             p16_new_count_reported = "(未执行)"

        # Always try to load from file
        logging.info(f"--- (本地) 开始加载 16p 文件: {p16_output_file} ---")
        if os.path.exists(p16_output_file):
            try: # Add try-except for file reading/parsing
                 with open(p16_output_file, 'r', encoding='utf-8') as f_16p:
                      p16_all_games = []
                      for line in f_16p:
                          try:
                               game = json.loads(line)
                               # Ensure date exists (maybe redundant now but safe)
                               if 'date' not in game or not game['date']:
                                   game['date'] = game.get('status_date') or current_date_str
                               p16_all_games.append(game)
                          except json.JSONDecodeError:
                               logging.warning(f"解析 {os.path.basename(p16_output_file)} 时跳过无效行: {line.strip()}")
                 if p16_all_games:
                      logging.info(f"从 16p 文件加载了 {len(p16_all_games)} 条数据。")
                      newly_fetched_games.extend(p16_all_games)
                 else:
                      logging.info(f"16p 文件为空或无法解析。爬虫报告新增 {p16_new_count_reported} 条。")
            except Exception as e:
                 logging.error(f"读取或解析 16p 文件 {p16_output_file} 时出错: {e}", exc_info=True)
        else:
             logging.warning(f"16p 数据文件 {p16_output_file} 不存在。即使爬虫报告成功({p16_new_count_reported}条)，也无法加载数据。")

    elif fetch_16p: logging.warning("16p 模块未加载，跳过 16p 处理。")
    else: logging.info("根据用户选择，跳过 16p 数据处理。")

    log_mode = "本地文件" if process_history_only else "在线爬取+本地文件"
    logging.info(f"通过 '{log_mode}' 模式，总共获取到 {len(newly_fetched_games)} 条来自 JSONL 文件的数据待处理。")
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
    # Updated task description logic
    if process_history_only:
        task_description = "处理本地文件 (Excel + JSONL), 不执行在线爬取"
    else:
        task_description = "在线爬取新数据并整合本地文件 (Excel + JSONL)"
    logging.info(f"{'='*20} 开始执行任务: {task_description} {'='*20}")

    master_excel_file = os.path.join(data_dir, "all_games_data.xlsx")
    master_json_file = os.path.join(data_dir, "all_games.json")
    excel_columns_map = get_excel_columns()

    final_games_list = []
    execution_successful = False

    try:
        # 1. Load Base Data From Excel (Always)
        base_data_from_excel, locked_records, excel_feature_flags = _load_excel_data(master_excel_file, excel_columns_map)

        # 2. Fetch/Load Data from JSONL files (Calls scraper only if not history_only)
        # Pass process_history_only flag to the function
        data_from_jsonl = _fetch_new_data(fetch_taptap, fetch_16p, process_history_only)

        # 3. Process Data from JSONL files
        logging.info("--- 处理来自 JSONL 文件的数据 --- ")
        processed_jsonl_data = []
        if data_from_jsonl:
            # Clean names first
            for game in data_from_jsonl:
                 # Ensure cleaned_name exists for key calculation/filtering
                 name_for_key = game.get('cleaned_name')
                 if not name_for_key:
                      name_for_key = clean_game_name(game.get('name'))
                      game['cleaned_name'] = name_for_key # Store back if newly calculated

            # Filter JSONL data (use process_history_only to decide if it's "history")
            # Treat loaded JSONL data as "new" unless in history_only mode
            is_history_filter = process_history_only
            logging.info(f"对 JSONL 数据应用 AppStore 过滤规则 (is_history_data={is_history_filter})")
            filtered_jsonl = _filter_appstore_games(data_from_jsonl, is_history_data=is_history_filter)

            # Run version matching on filtered, non-locked JSONL data
            logging.info(f"对 {len(filtered_jsonl)} 条过滤后的 JSONL 数据进行版号匹配 (跳过锁定记录)")
            # Pass locked_records for skipping check inside
            matched_jsonl = _run_version_matching(filtered_jsonl, locked_records, description="JSONL数据")

            # Standardize the matched JSONL data
            logging.info("标准化匹配后的 JSONL 数据")
            processed_jsonl_data = standardize_game_data(matched_jsonl, excel_columns_map)

            # Apply feature flags from Excel to standardized JSONL data if name/date matches & not locked
            logging.info("尝试从 Excel 历史记录应用 '是否重点' 标记到 JSONL 数据 (如果匹配且未锁定)")
            applied_flag_count = 0
            for std_game in processed_jsonl_data:
                key = (std_game.get('cleaned_name'), std_game.get('date'))
                if key in excel_feature_flags and key not in locked_records:
                    std_game['is_featured'] = excel_feature_flags[key]
                    if excel_feature_flags[key]: # Only count if flag was True
                         applied_flag_count +=1
            logging.info(f"已将 {applied_flag_count} 个 '重点' 标记从 Excel 应用到匹配的 JSONL 记录。")
        else:
             logging.info("未从 JSONL 文件加载到数据，跳过处理步骤。")


        # 4. Merge All Data (Base Excel + Processed JSONL)
        logging.info("--- 开始合并 Excel 基础数据和处理后的 JSONL 数据 --- ")
        # Use base_data_from_excel (all original excel rows)
        # Use processed_jsonl_data (standardized, matched, filtered JSONL data)
        combined_games = base_data_from_excel + processed_jsonl_data
        logging.info(f"合并后共 {len(combined_games)} 条数据待去重。")

        # 5. Deduplicate Combined List
        # Pass the combined list and locked records dictionary
        temp_final_list = _deduplicate_games(combined_games, locked_records)


        # --- Common Post-Processing Steps --- #
        if not temp_final_list:
            logging.warning("最终数据列表为空，流程结束。")
        else:
            # 6. Resolve Online Conflicts (Applied to the deduplicated list)
            resolved_list = _resolve_online_conflicts(temp_final_list)

            # 7. Sort
            logging.info("--- 按日期倒序排列数据 ---")
            resolved_list.sort(key=lambda x: (x.get('date', '0000-00-00'), x.get('name', '')), reverse=True) # Sort by date then name

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

            # 8. Backup and Run analysis/cleanup on the saved Excel file
            if analyze_and_remove_old_tests: # Check if function was imported successfully
                logging.info("--- 开始执行测试日期间隔分析和清理 --- ")
                
                # --- Backup before analysis --- 
                backup_file = os.path.join(data_dir, f"all_games_data.xlsx.bak") 
                try:
                    if os.path.exists(master_excel_file):
                        shutil.copy2(master_excel_file, backup_file)
                        logging.info(f"已创建/覆盖分析前备份文件: {backup_file}")
                    else:
                         logging.warning(f"无法创建备份，因为主文件 {master_excel_file} 不存在。")
                except Exception as e:
                    logging.error(f"创建分析前备份文件失败: {e}。请注意！")

                # --- Get parameters for analysis --- 
                status_config = CONFIG.get('status_standardization', {})
                # Determine the standardized name for 'test' status
                status_test_name = '测试' # Default
                test_keys_to_check = ['status_test', '测试', 'Test'] # Keys to check in config
                for key in test_keys_to_check:
                    if key in status_config:
                         status_test_name = status_config[key]
                         break
                logging.info(f"将使用状态名 '{status_test_name}' 进行测试间隔分析。")
                
                # Get min_days from config, default to 7 if not found
                min_days = CONFIG.get('analysis_min_interval_days', 7)
                logging.info(f"将使用最小间隔天数: {min_days} 进行分析。")
                
                # --- Run the analysis function --- 
                try:
                     analysis_modified = analyze_and_remove_old_tests(
                         master_excel_file,
                         status_test_name,
                         min_days
                     )
                     if analysis_modified:
                          logging.info("测试日期间隔分析完成，旧记录已根据规则删除。")
                     else:
                          logging.info("测试日期间隔分析完成，未进行修改（未发现需删除的记录或操作失败）。")
                except Exception as analysis_error:
                     logging.error(f"执行测试日期间隔分析时发生错误: {analysis_error}", exc_info=True)
                     logging.error("Excel 文件可能未被清理，请检查。")
        elif execution_successful and not final_games_list:
             logging.warning("处理流程成功但最终列表为空，不执行保存和分析操作。")
        elif not execution_successful:
             logging.info("处理流程未成功完成，跳过保存和分析操作。")

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