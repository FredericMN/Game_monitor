# analyze_game_updates.py (Enhanced)

import pandas as pd
import os
import logging
import json
from datetime import datetime, timedelta
import shutil # Import shutil for backup
import re # Added import
import unicodedata # Added import

# --- 配置 ---
# NOTE_SHORT_INTERVAL = "注意：测试日期间隔过近(<=7天)"
# MIN_INTERVAL_DAYS = 7

# Global config dictionary needed for clean_game_name
CONFIG = {}

# --- 日志设置 (可以在 main 函数中详细配置) ---
# setup_logging()

# --- Utility functions copied/adapted from collect_games.py ---
def get_excel_columns():
    """Returns the mapping from Chinese Excel headers to internal field names."""
    # We need the reverse map (Excel Header -> Internal Name) for reading
    # And the original map (Internal Name -> Excel Header) might be useful too
    return {
        "名称": "name", "日期": "date", "状态": "status", "平台": "platform",
        "分类": "category", "评分": "rating", "厂商": "publisher", "来源": "source",
        "是否重点": "is_featured", "链接": "link", "图标": "icon_url", "简介": "description",
        "版号已查": "version_checked", "版号名称": "nppa_name", "批准文号": "approval_num",
        "出版物号": "publication_num", "批准日期": "approval_date", "出版单位": "publisher_unit",
        "运营单位": "operator_unit", "版号游戏类型": "game_type_version",
        "申报类别": "declaration_category", "版号多结果": "multiple_results",
        "是否人工校对": "manual_checked" # Important for this script
    }

def clean_game_name(name):
    """根据配置清理游戏名称 (Adapted from collect_games.py)"""
    global CONFIG # Use the global CONFIG dictionary
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
            flags = 0
            if pattern.endswith('$'): # Basic check for case-insensitive flag marker
                 flags = re.IGNORECASE
                 pattern = pattern.rstrip('$i') # Remove potential flag markers
            
            cleaned = re.sub(pattern, '', cleaned, flags=flags)
        except re.error as e:
             logging.warning(f"应用名称清理正则失败 ('{pattern}'): {e}")
             
    # 3. 替换多个空格为单个空格
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # 4. 去除首尾空格
    cleaned = cleaned.strip()
    
    # 如果清理后为空，返回原始名称（规范化后）
    return cleaned if cleaned else normalized_name.strip()

# --- Core Script Functions ---
def load_config(config_path):
    """加载配置，返回包含状态名称和名称清理配置的字典"""
    global CONFIG # Load into the global CONFIG
    config_data = {
        'status_online': '上线',
        'status_test': '测试',
        'game_name_cleaning': {} # Add game_name_cleaning config
    } # Defaults
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
            CONFIG = loaded_config # Store full config globally for clean_game_name

            std_cfg = loaded_config.get('status_standardization', {})
            config_data['status_online'] = std_cfg.get('status_online', '上线')
            test_keys_to_check = ['status_test', '测试', 'Test']
            found_test_status = False
            for key in test_keys_to_check:
                 if key in std_cfg:
                     config_data['status_test'] = std_cfg[key]
                     found_test_status = True
                     break
            if not found_test_status:
                 logging.warning(f"未在配置中找到明确的 '测试' 状态映射 (尝试的键: {test_keys_to_check}), 将使用默认值 '测试'")
                 config_data['status_test'] = '测试'

            # Load game name cleaning config
            config_data['game_name_cleaning'] = loaded_config.get('game_name_cleaning', {})
            logging.info("成功加载游戏名称清理配置。")

            logging.info(f"从配置加载状态: Online='{config_data['status_online']}', Test='{config_data['status_test']}'")
    except FileNotFoundError:
         logging.warning(f"配置文件 {config_path} 未找到，使用默认状态名和清理配置。")
    except json.JSONDecodeError:
         logging.warning(f"解析配置文件 {config_path} 出错，使用默认状态名和清理配置。")
    except Exception as e:
        logging.warning(f"加载配置时出错，使用默认状态名和清理配置: {e}")
    
    # Ensure global CONFIG has defaults if loading failed
    if not CONFIG:
        CONFIG = {'game_name_cleaning': config_data['game_name_cleaning']}
    elif 'game_name_cleaning' not in CONFIG:
         CONFIG['game_name_cleaning'] = config_data['game_name_cleaning']
         
    return config_data

# (通用日期变化检测函数可以保留在这里，如果需要的话)
# def find_date_changes(excel_path, status_online_name): ...
# def report_anomalies(anomalies, output_file=None): ...

def analyze_and_remove_old_tests(excel_path, status_test_name, min_days):
    """分析测试日期间隔，如果过短则删除日期较早的未锁定记录，保留最新的。"""
    excel_modified = False
    rows_to_delete_indices = set()
    df = None
    excel_columns_map = get_excel_columns()
    excel_name_col = "名称"
    excel_status_col = "状态"
    excel_date_col = "日期"
    excel_manual_check_col = "是否人工校对"
    internal_cleaned_name_col = "cleaned_name_generated"

    try:
        try:
            df = pd.read_excel(excel_path, dtype={excel_manual_check_col: str}, engine='openpyxl')
        except Exception as read_err:
             logging.warning(f"使用 openpyxl 读取Excel时出错: {read_err}. 尝试不指定引擎...")
             df = pd.read_excel(excel_path, dtype={excel_manual_check_col: str})

        df['original_index'] = df.index

        required_excel_cols = [excel_name_col, excel_status_col, excel_date_col, excel_manual_check_col]
        if not all(col in df.columns for col in required_excel_cols):
            missing_cols = [col for col in required_excel_cols if col not in df.columns]
            logging.error(f"Excel 文件 {excel_path} 缺少必要的列: {missing_cols}")
            return False

        df[excel_name_col] = df[excel_name_col].fillna('未知名称').astype(str)
        df[internal_cleaned_name_col] = df[excel_name_col].apply(clean_game_name)
        logging.info(f"已从 '{excel_name_col}' 列生成内部使用的 '{internal_cleaned_name_col}' 列。")

        df['parsed_date'] = pd.to_datetime(df[excel_date_col], errors='coerce')
        df[excel_manual_check_col] = df[excel_manual_check_col].fillna('').astype(str)

        test_records = df[
            (df[excel_status_col] == status_test_name) &
            (df[internal_cleaned_name_col].notna()) & (df[internal_cleaned_name_col] != '') &
            (df['parsed_date'].notna())
        ].copy()

        logging.info(f"筛选出 {len(test_records)} 条有效的 '{status_test_name}' 记录进行间隔分析。")

    except FileNotFoundError:
        logging.error(f"Excel 文件未找到: {excel_path}")
        return False
    except Exception as e:
        logging.error(f"读取或预处理 Excel 文件 {excel_path} 时出错: {e}", exc_info=True)
        return False

    # --- 分析间隔并确定删除项 --- 
    if test_records.empty:
        logging.info("没有有效的测试记录可供分析间隔。")
    else:
        grouped_by_game_test = test_records.groupby(internal_cleaned_name_col)
        for name, group in grouped_by_game_test:
            if len(group) < 2: continue

            # Sort by date, keep original index
            sorted_group = group.sort_values(by='parsed_date').reset_index(drop=True)
            
            i = 0
            while i < len(sorted_group):
                # Find the end of the current conflict block
                block_end_index = i
                while block_end_index < len(sorted_group) - 1:
                    date1 = sorted_group.iloc[block_end_index]['parsed_date']
                    date2 = sorted_group.iloc[block_end_index + 1]['parsed_date']
                    if pd.notna(date1) and pd.notna(date2) and (date2 - date1) <= timedelta(days=min_days):
                        block_end_index += 1
                    else:
                        break # End of block
                
                # If a block of conflicts (more than 1 record) is found
                if block_end_index > i:
                    conflict_block_indices = list(range(i, block_end_index + 1))
                    conflict_block_df = sorted_group.iloc[conflict_block_indices]
                    
                    # Find the latest date within this block
                    latest_date_in_block = conflict_block_df['parsed_date'].max()
                    
                    block_dates = [d.strftime('%Y-%m-%d') if pd.notna(d) else 'NaT' for d in conflict_block_df['parsed_date']]
                    logging.info(f"处理冲突块: 游戏='{name}', 状态='{status_test_name}', 块内日期={block_dates}, 最新日期={latest_date_in_block:%Y-%m-%d if pd.notna(latest_date_in_block) else 'NaT'}")

                    # Identify records to potentially delete within this block
                    records_to_keep_indices_in_block = set(conflict_block_df[conflict_block_df['parsed_date'] == latest_date_in_block].index)
                    
                    # Ensure we keep at least one if multiple share the latest date (arbitrarily the first one)
                    if len(records_to_keep_indices_in_block) > 1:
                         first_latest_index = min(records_to_keep_indices_in_block)
                         records_to_keep_indices_in_block = {first_latest_index}
                    
                    for block_idx in conflict_block_indices:
                        row = sorted_group.iloc[block_idx]
                        original_df_index = row['original_index']
                        
                        # Check if this record is NOT the one chosen to be kept
                        if block_idx not in records_to_keep_indices_in_block:
                            # Check if it's manually checked (locked)
                            manual_check_val = str(row[excel_manual_check_col]).strip().lower()
                            is_locked = manual_check_val in ['true', '是', 'yes', '1']
                            
                            if not is_locked:
                                logging.info(f"  标记删除 (非最新且未锁定): Index={original_df_index}, 日期={row['parsed_date']:%Y-%m-%d if pd.notna(row['parsed_date']) else 'NaT'}")
                                rows_to_delete_indices.add(original_df_index)
                            else:
                                logging.info(f"  跳过删除 (非最新但已锁定): Index={original_df_index}, 日期={row['parsed_date']:%Y-%m-%d if pd.notna(row['parsed_date']) else 'NaT'}")
                        # else:
                             # logging.info(f"  保留 (最新或锁定): Index={original_df_index}, 日期={row['parsed_date']:%Y-%m-%d if pd.notna(row['parsed_date']) else 'NaT'}")
                             
                    # Move the main loop index past this processed block
                    i = block_end_index + 1
                else: # No conflict starting at index i, move to next record
                    i += 1

    # --- 删除记录 --- 
    if rows_to_delete_indices:
        logging.info(f"准备从 DataFrame 删除 {len(rows_to_delete_indices)} 条记录...")
        try:
            df.drop(index=list(rows_to_delete_indices), inplace=True)
            excel_modified = True
            logging.info(f"成功删除 {len(rows_to_delete_indices)} 条记录。")
        except KeyError as key_err:
             logging.error(f"尝试删除记录时发生 KeyError: {key_err}。可能索引已失效。跳过删除。", exc_info=True)
             # Continue without modification if drop fails partially
        except Exception as drop_err:
             logging.error(f"删除记录时发生未知错误: {drop_err}。跳过删除。", exc_info=True)
             # Continue without modification
    else:
        logging.info("未发现需要删除的短间隔测试记录（或所有待删记录均已锁定）。")

    # --- 保存回 Excel --- 
    if excel_modified:
        try:
            df_to_save = df.drop(columns=['original_index', 'parsed_date', internal_cleaned_name_col], errors='ignore')
            df_to_save.to_excel(excel_path, index=False, engine='openpyxl')
            logging.info(f"修改后的数据（已删除旧记录）已覆盖保存回: {excel_path}")
            return True
        except ImportError:
             logging.error("保存失败：需要安装 'openpyxl' 库才能写入 .xlsx 文件。请运行 'pip install openpyxl'")
             return False
        except Exception as e:
            logging.error(f"保存修改后的 Excel 文件时出错: {e}", exc_info=True)
            return False
    else:
        logging.info("未对 Excel 文件进行修改。")
        return False

# --- Main Execution Guard ---
def main():
    # --- 设置 ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    data_dir = os.path.join(root_dir, 'data')
    config_dir = os.path.join(root_dir, 'config')
    log_dir = os.path.join(root_dir, 'logs')
    reports_dir = os.path.join(root_dir, 'reports')

    excel_file = os.path.join(data_dir, 'all_games_data.xlsx')
    config_file = os.path.join(config_dir, 'collect_games_config.json')
    # note_for_short_interval removed as we are deleting now
    min_interval_days = 7

    # --- 确保目录存在 ---
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(reports_dir, exist_ok=True)

    # --- 日志配置 ---
    log_filename = os.path.join(log_dir, f'analyze_updates_{datetime.now().strftime("%Y%m%d")}.log')
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
                        handlers=[logging.FileHandler(log_filename, encoding='utf-8'),
                                  logging.StreamHandler()])

    logging.info("--- 开始分析并移除旧的短间隔测试记录 ---")

    status_config = load_config(config_file)
    
    if not os.path.exists(excel_file):
        logging.error(f"目标 Excel 文件不存在: {excel_file}")
        logging.info("--- 分析更新流程结束 (因文件不存在) ---")
        return

    # --- 备份 --- 
    backup_file = os.path.join(data_dir, f"all_games_data.xlsx.bak") 
    try:
        shutil.copy2(excel_file, backup_file)
        logging.info(f"已创建/覆盖备份文件: {backup_file}")
    except Exception as e:
        logging.error(f"创建备份文件失败: {e}。请手动备份后继续！")
        # return # Safer option

    # --- 执行分析与删除 --- 
    # Renamed function call
    modified = analyze_and_remove_old_tests(excel_file,
                                             status_config['status_test'],
                                             min_interval_days)

    if modified:
        logging.info("分析完成，Excel 文件已根据短间隔测试结果更新（旧记录已删除）。")
    else:
        logging.info("分析完成，未对 Excel 文件进行修改（未发现需删除的记录或删除操作失败）。")

    logging.info("--- 分析更新流程结束 ---")

if __name__ == "__main__":
    main() 