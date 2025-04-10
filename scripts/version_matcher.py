# scripts/version_matcher.py
# 用于从 NPPA 网站匹配游戏版号信息

import os
import time
import random
import re
import json # Added for caching
import threading # Added for cache lock
from datetime import datetime # 添加用于月份记录
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from concurrent.futures import ThreadPoolExecutor, as_completed
import collections # Add this import at the top

# 并发工作线程数 (可以根据机器性能调整)
MAX_MATCH_WORKERS = 1 # Adjusted for potentially longer individual queries

# --- 缓存配置 ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)
CACHE_FILE = os.path.join(DATA_DIR, 'version_match_cache.jsonl')
cache_lock = threading.Lock() # Lock for writing to cache file

def get_current_month():
    """获取当前月份，格式为YYYY-MM"""
    return datetime.now().strftime("%Y-%m")

def load_version_cache():
    """Loads the version match cache from the JSONL file."""
    cache = {}
    if not os.path.exists(CACHE_FILE):
        return cache
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    # Store result keyed by name
                    if 'name' in data:
                        # 新结构：包含结果和查询月份
                        cache_entry = {
                            'result': data.get('result'),
                            'query_month': data.get('query_month', get_current_month())  # 默认为当前月份
                        }
                        cache[data['name']] = cache_entry
                except json.JSONDecodeError:
                    print(f"[缓存警告] 无法解析缓存行: {line.strip()}")
        print(f"[缓存] 从 {CACHE_FILE} 加载了 {len(cache)} 条记录。")
    except Exception as e:
        print(f"[缓存错误] 读取缓存文件时出错: {e}")
    return cache

def update_version_cache(game_name, result, cache_dict):
    """Appends a result to the cache file and updates the in-memory cache, thread-safely."""
    current_month = get_current_month()
    
    with cache_lock:
        try:
            # Update in-memory cache first
            cache_dict[game_name] = {
                'result': result,
                'query_month': current_month
            }
            
            # Append to file
            with open(CACHE_FILE, 'a', encoding='utf-8') as f:
                json.dump({
                    "name": game_name, 
                    "result": result,
                    "query_month": current_month
                }, f, ensure_ascii=False)
                f.write('\n')
            # print(f"[缓存] 已更新缓存: {game_name} -> {'有结果' if result else '无结果'} (查询月份: {current_month})")
        except Exception as e:
            print(f"[缓存错误] 写入缓存时出错 ({game_name}): {e}")


def random_delay(min_sec=0.5, max_sec=1.5):
    """避免爬取过快"""
    time.sleep(random.uniform(min_sec, max_sec))

def setup_matcher_driver(headless=True):
    """
    配置并初始化用于版号匹配的 Edge 浏览器
    """
    options = webdriver.EdgeOptions()
    if headless:
        options.add_argument("--headless")
    # 性能优化选项
    options.add_argument('--disable-extensions')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36")
    
    try:
        service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=options)
        print("[版号匹配] WebDriver 初始化成功。")
        # 设置超时
        driver.set_page_load_timeout(40) 
        driver.set_script_timeout(40)
        return driver
    except Exception as e:
        print(f"[版号匹配] 初始化 WebDriver 时出错: {e}")
        return None

def _perform_nppa_query(query_name):
    """
    Performs the actual NPPA query using Selenium for a given name.
    Returns the result dict or None.
    (This encapsulates the core Selenium logic from the previous fetch_single_game_version_info)
    """
    if not query_name:
        return None

    print(f"[版号查询] 查询: '{query_name}'...") # Log the name being queried
    driver = setup_matcher_driver(headless=True)
    if not driver:
        return None # Driver setup failed

    result_info = None
    try:
        # Clean name for URL (though NPPA site might handle spaces)
        url_query_name = query_name # Use the name directly for now
        url = f"https://www.nppa.gov.cn/bsfw/jggs/cxjg/index.html?mc={url_query_name}&cbdw=&yydw=&wh=undefined&description=#"
        # print(f"[版号查询] 访问 URL: {url}") # Less verbose

        max_retries = 2 # Reduced retries as cache handles some failures
        page_loaded = False
        for retry in range(max_retries):
            try:
                driver.get(url)
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#dataCenter")))
                # print("[版号查询] 查询结果页面加载成功。")
                page_loaded = True
                break
            except TimeoutException:
                # print(f"[版号查询] '{query_name}' 页面加载超时 (尝试 {retry+1}/{max_retries})。")
                if retry == max_retries - 1: print(f"[版号查询] '{query_name}' 页面加载多次超时。")
            except Exception as load_e:
                 print(f"[版号查询] 加载页面时出错 ({query_name}, 尝试 {retry+1}/{max_retries}): {load_e}")
            if not page_loaded and retry < max_retries - 1: time.sleep(1.5)

        if not page_loaded:
            raise TimeoutException("页面加载失败")

        try:
             WebDriverWait(driver, 8).until(lambda d: len(d.find_elements(By.CSS_SELECTOR, "#dataCenter tr")) > 0)
             result_rows = driver.find_elements(By.CSS_SELECTOR, "#dataCenter tr")
             # print(f"[版号查询] 找到 {len(result_rows)} 条结果 for '{query_name}'.")
        except TimeoutException:
             # print(f"[版号查询] 未查询到 '{query_name}' 的版号信息。")
             result_rows = []
        except Exception as find_e:
             print(f"[版号查询] 查找结果行时出错 ({query_name}): {find_e}")
             result_rows = []

        if result_rows:
            multiple_results_flag = "是" if len(result_rows) > 1 else "否"
            target_row_element = None
            # Try to find exact match first (case-insensitive might be better?)
            for row in result_rows:
                try:
                    row_game_name_elem = row.find_element(By.CSS_SELECTOR, "td:nth-child(2) a")
                    row_game_name = row_game_name_elem.text.strip()
                    # Use cleaned names for comparison? Or exact match? Sticking to exact for now.
                    if row_game_name == query_name:
                        target_row_element = row
                        # print(f"[版号查询] 找到与 '{query_name}' 完全匹配的结果行。")
                        break
                except NoSuchElementException: continue

            if not target_row_element:
                target_row_element = result_rows[0]
                # print(f"[版号查询] 未找到完全匹配 '{query_name}'，使用第一条结果。")

            result_info = extract_info_from_row(target_row_element, multiple_results_flag, driver)

    except Exception as e:
        # Don't print full timeout error if it's just timeout
        if not isinstance(e, TimeoutException):
             print(f"[版号查询] 查询 '{query_name}' 时发生错误: {e}")
        result_info = None
    finally:
        if driver:
            driver.quit()
            # print(f"[版号查询] '{query_name}' 查询结束，浏览器关闭。")

    return result_info


def fetch_single_game_version_info_with_cache(game_name, cache_dict):
    """
    Fetches version info for a single game, using cache and handling spaces.
    Updates cache after query.
    """
    if not game_name or game_name == "未知名称":
        return None

    current_month = get_current_month()
    
    # 1. 缓存检查 - 现在考虑月份信息
    cached_entry = cache_dict.get(game_name)
    if cached_entry is not None:
        cached_result = cached_entry.get('result')
        cached_month = cached_entry.get('query_month', '2000-01')  # 设定一个很旧的默认月份
        
        # 如果有结果，直接使用
        if cached_result is not None:
            # print(f"[缓存命中] 使用缓存结果 for '{game_name}'.")
            return cached_result
        
        # 如果没有结果，检查月份是否需要更新
        if cached_result is None and cached_month == current_month:
            # 本月已查询过且无结果，不再查询
            print(f"[版号匹配] '{game_name}' 本月已查询过无结果 ({cached_month})，跳过查询。")
            return None
        
        # 如果是跨月无结果的缓存，需要重新查询
        print(f"[版号匹配] '{game_name}' 上次查询月份为 {cached_month}，当前为 {current_month}，重新查询。")
    else:
        print(f"[版号匹配] '{game_name}' 缓存未命中，进行查询。")

    # 2. 执行查询 (包含空格处理)
    final_result = None
    if " " in game_name:
        result1 = _perform_nppa_query(game_name) # Query full name
        if result1 is None:
            truncated_name = game_name.split(" ", 1)[0]
            if truncated_name != game_name: # Avoid re-querying if space was at the end
                 print(f"[版号匹配] 完整名称 '{game_name}' 无结果，尝试截断名称: '{truncated_name}'")
                 result2 = _perform_nppa_query(truncated_name) # Query truncated name
                 final_result = result2
            else:
                 final_result = None # Space was at end, still no result
        else:
            final_result = result1 # Use result from full name query
    else:
        # No space, direct query
        final_result = _perform_nppa_query(game_name)

    # 3. 更新缓存 (带月份信息)
    update_version_cache(game_name, final_result, cache_dict)

    return final_result


def extract_info_from_row(row_element, multiple_flag, driver):
    """从 NPPA 查询结果的一行中提取详细版号信息 (基本保持不变, 减少打印)"""
    try:
        tds = row_element.find_elements(By.TAG_NAME, "td")
        if len(tds) < 7: return None # Cell count check

        # Extract the name found on NPPA site
        nppa_name = ""
        try:
            nppa_name_element = tds[1].find_element(By.CSS_SELECTOR, "a")
            nppa_name = nppa_name_element.text.strip()
        except NoSuchElementException:
            nppa_name = tds[1].text.strip() # Fallback if no link

        publisher_unit = tds[2].text.strip()
        operator_unit = tds[3].text.strip()
        approval_num = tds[4].text.strip()
        publication_num = tds[5].text.strip()
        approval_date = tds[6].text.strip()

        detail_url = ""
        try:
            link_element = tds[1].find_element(By.TAG_NAME, "a")
            detail_url = link_element.get_attribute("href")
        except NoSuchElementException: pass

        game_type = ""
        declaration_category = ""
        if detail_url:
            original_window = driver.current_window_handle
            new_window = None
            try:
                driver.execute_script("window.open(arguments[0]);", detail_url)
                WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
                new_window = [window for window in driver.window_handles if window != original_window][0]
                driver.switch_to.window(new_window)
                random_delay(0.5, 1)
                try:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".cFrame.nFrame table")))
                    detail_rows = driver.find_elements(By.CSS_SELECTOR, ".cFrame.nFrame table tr")
                    for ln in detail_rows:
                        try:
                            label = ln.find_element(By.XPATH, "./td[1]").text.strip()
                            value = ln.find_element(By.XPATH, "./td[2]").text.strip()
                            if label == "游戏类型": game_type = value
                            elif label == "申报类别": declaration_category = value
                        except NoSuchElementException: continue
                        except Exception as cell_e: print(f"[版号信息] 处理详情单元格时出错: {cell_e}")
                except TimeoutException: pass
                except Exception as detail_table_e: print(f"[版号信息] 处理版号详情表格时出错: {detail_table_e}")
            finally:
                try:
                    if new_window and new_window in driver.window_handles and driver.current_window_handle == new_window:
                        driver.close()
                    if original_window in driver.window_handles:
                         driver.switch_to.window(original_window)
                except Exception as switch_e: print(f"[版号信息] 关闭或切换窗口时出错: {switch_e}")

        return {
            "nppa_name": nppa_name, # Include the name found on NPPA site
            "publisher_unit": publisher_unit,
            "operator_unit": operator_unit,
            "approval_num": approval_num,
            "publication_num": publication_num,
            "approval_date": approval_date,
            "game_type_version": game_type,
            "declaration_category": declaration_category,
            "multiple_results": multiple_flag
        }

    except Exception as e:
        print(f"[版号信息] 从行元素提取信息时出错: {e}")
        return None

def worker_task(game_info, cache_dict):
    """Worker function for ThreadPoolExecutor."""
    # game_info contains the cleaned name from collect_games under the 'name' key
    query_name = game_info.get('name')
    result = fetch_single_game_version_info_with_cache(query_name, cache_dict)

    # Create the update dictionary
    update_data = {}
    if result:
        # Merge all fields from the successful result (including nppa_name)
        update_data.update(result)
        update_data['version_checked'] = True
        # DO NOT update game_info['name'] here. Let collect_games handle the primary name.
    else:
        update_data['version_checked'] = False # Mark as checked, even if no result

    # Return a dictionary containing only the updates to be applied
    # to the original game_info in the main thread/process
    # We also need a way to identify which original game_info this corresponds to
    # Let's assume game_info has a unique identifier, e.g., '_original_index'
    return {
        "_original_index": game_info.get("_original_index"), # Pass index back
        "update_data": update_data
    }

def cleanup_version_cache(cache_file_path):
    """
    Cleans up the version match cache file by consolidating results per game name.

    Rules:
    - If only None results exist for a game, keep one None entry.
    - If non-None results exist, keep only the unique non-None results (discard Nones).
    - If multiple *different* non-None results exist (based on approval_num),
      keep all unique non-None results and print a warning.
    """
    print(f"\n[缓存清理] 开始清理缓存文件: {cache_file_path}") # Add newline for better formatting
    if not os.path.exists(cache_file_path):
        print("[缓存清理] 缓存文件不存在，无需清理。")
        return

    grouped_results = collections.defaultdict(list)
    raw_lines = []
    try:
        # Read all existing lines first
        with cache_lock: # Use lock for reading as well to be safe
             # Check if file is empty before reading
             if os.path.getsize(cache_file_path) == 0:
                 print("[缓存清理] 缓存文件为空，无需清理。")
                 return
             with open(cache_file_path, 'r', encoding='utf-8') as f:
                 raw_lines = f.readlines()

        # Parse lines and group results
        for line in raw_lines:
            line = line.strip()
            if not line: continue
            try:
                data = json.loads(line)
                if 'name' in data:
                    # 保存完整记录，包括查询月份
                    entry = {
                        'result': data.get('result'),
                        'query_month': data.get('query_month', get_current_month())
                    }
                    grouped_results[data['name']].append(entry)
                else:
                    print(f"[缓存清理警告] 跳过格式无效的行: {line}")
            except json.JSONDecodeError:
                print(f"[缓存清理警告] 跳过无法解析JSON的行: {line}")

    except FileNotFoundError:
         print("[缓存清理] 缓存文件在读取过程中消失，跳过清理。")
         return
    except Exception as e:
        print(f"[缓存清理错误] 读取或解析缓存文件时出错: {e}")
        print("[缓存清理] 由于读取错误，将中止清理过程以避免数据丢失。")
        return # Abort cleanup if reading failed

    if not grouped_results:
        print("[缓存清理] 未从缓存文件中解析出有效数据，无需清理。")
        return

    cleaned_cache_entries = []
    multiple_results_warnings = 0

    for name, entries_list in grouped_results.items():
        # 按照结果分组
        non_none_entries = [e for e in entries_list if e['result'] is not None]
        
        if non_none_entries:
            # 有效结果处理，确保唯一性
            unique_results = {}
            
            for entry in non_none_entries:
                result = entry['result']
                approval_num = result.get('approval_num', '')
                
                if approval_num and str(approval_num).strip():
                    result_key = str(approval_num).strip()
                else:
                    try:
                        result_key = frozenset(sorted(result.items()))
                    except TypeError:
                        result_key = id(result)
                        print(f"[缓存清理警告] 游戏 '{name}' 的结果包含无法哈希的类型，将基于对象ID判断唯一性。")
                
                # 保存最新的月份记录
                if result_key not in unique_results or entry['query_month'] > unique_results[result_key]['query_month']:
                    unique_results[result_key] = entry
            
            unique_entries = list(unique_results.values())
            
            if len(unique_entries) > 1:
                print(f"[缓存清理警告] 游戏 '{name}' 发现 {len(unique_entries)} 个不同的版号结果，将全部保留。")
                multiple_results_warnings += 1
            
            # 保存所有唯一的非空结果，带月份
            for entry in unique_entries:
                cleaned_cache_entries.append({
                    "name": name, 
                    "result": entry['result'],
                    "query_month": entry['query_month']
                })
        else:
            # 只有空结果的情况，保留最新的月份记录
            latest_entry = max(entries_list, key=lambda e: e['query_month'])
            cleaned_cache_entries.append({
                "name": name, 
                "result": None,
                "query_month": latest_entry['query_month']
            })

    # Write cleaned results back, overwriting the file
    try:
        with cache_lock: # Ensure exclusive write access
            with open(cache_file_path, 'w', encoding='utf-8') as f:
                for entry in cleaned_cache_entries:
                    json.dump(entry, f, ensure_ascii=False)
                    f.write('\n')
        print(f"[缓存清理] 清理完成。处理了 {len(grouped_results)} 个游戏名称，最终保留 {len(cleaned_cache_entries)} 条缓存记录。")
        if multiple_results_warnings > 0:
            print(f"[缓存清理] 共发现 {multiple_results_warnings} 个游戏存在多个不同版号。")
    except Exception as e:
        print(f"[缓存清理错误] 写入清理后的缓存时出错: {e}")


def match_version_numbers_for_games(games_list):
    """
    为游戏列表批量匹配版号信息（并发执行, 带缓存和空格处理）。
    修改传入的列表中的字典。
    参数:
        games_list (list): 包含游戏信息字典的列表。每个字典至少需要有 'name' 键 (应为清洗后的名称)。
                         It's recommended to add a unique index, e.g., '_original_index'
                         to each dict before calling this function.
    返回:
        list: 返回传入的列表，但其内容已被修改。
    """
    if not games_list:
        return []

    print(f"\n[版号匹配] 开始为 {len(games_list)} 个游戏批量匹配版号 (并发: {MAX_MATCH_WORKERS})...")
    start_time = time.time()

    version_cache_dict = load_version_cache()
    total_tasks = len(games_list)
    completed_count = 0

    # Ensure each game has an index if not provided
    for i, game in enumerate(games_list):
        if "_original_index" not in game:
            game["_original_index"] = i

    with ThreadPoolExecutor(max_workers=MAX_MATCH_WORKERS) as executor:
        future_map = {executor.submit(worker_task, game_info, version_cache_dict): game_info["_original_index"] for game_info in games_list}

        for future in as_completed(future_map):
            original_index = future_map[future]
            try:
                # Get the result dict containing index and update_data
                worker_result = future.result()
                if worker_result and worker_result.get("_original_index") is not None:
                    idx = worker_result["_original_index"]
                    update_data = worker_result.get("update_data", {})
                    # Find the correct dict in the original list and update it
                    # This assumes the original list order is preserved or indices are reliable
                    # A safer way might be to build a new list, but for in-place modification:
                    target_dict = next((g for g in games_list if g.get("_original_index") == idx), None)
                    if target_dict:
                        target_dict.update(update_data)
                    else:
                         print(f"\n[版号匹配警告] 无法找到索引 {idx} 的原始记录进行更新。")
                else:
                    print(f"\n[版号匹配警告] Worker 返回无效结果: {worker_result}")

                completed_count += 1
                progress = int(completed_count * 100 / total_tasks)
                if completed_count % 10 == 0 or completed_count == total_tasks:
                     print(f"[版号匹配] 进度: {progress}% ({completed_count}/{total_tasks})", end='\r', flush=True)

            except Exception as e:
                # Find the game name corresponding to the failed future's index
                failed_game_name = "未知"
                target_dict = next((g for g in games_list if g.get("_original_index") == original_index), None)
                if target_dict:
                    failed_game_name = target_dict.get('name', '未知')
                    target_dict['version_checked'] = False # Mark as failed

                print(f"\n[版号匹配] 处理游戏 '{failed_game_name}' (索引 {original_index}) 时线程出错: {e}")

    print(f"\n[版号匹配] 批量匹配完成，耗时: {time.time() - start_time:.2f} 秒。")

    # --- 新增: 任务结束后清理缓存 --- #
    try:
        cleanup_version_cache(CACHE_FILE)
    except Exception as cleanup_e:
         print(f"\n[缓存清理错误] 调用缓存清理函数时发生意外错误: {cleanup_e}")
    # --- 结束缓存清理调用 --- #

    return games_list

# --- 主程序入口 (用于测试) --- #
if __name__ == "__main__":
    print("[测试模式] 开始...")
    # Keep the test logic, but it will now use the cache
    import json
    import os
    # Need clean_game_name for testing
    def clean_game_name(name):
        """清理游戏名称，移除常见的宣传后缀和括号内容"""
        if not name: return "未知名称"
        cleaned = re.sub(r'[（(].*?[)）]', '', name)
        cleaned = re.sub(r'[-–—]\s*[^-\s]+$', '', cleaned)
        cleaned = cleaned.strip()
        return cleaned if cleaned else name

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
    target_file = os.path.join(data_dir, "taptap_games_2025-04-08.jsonl") # Example test file

    test_games = []
    if os.path.exists(target_file):
        print(f"[测试模式] 读取测试文件: {target_file}")
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        game_data = json.loads(line.strip())
                        # IMPORTANT: Use the CLEANED name for testing match function
                        cleaned_name = clean_game_name(game_data.get("name"))
                        # Pass other info if needed by worker_task structure
                        test_games.append({"name": cleaned_name, "source": game_data.get("source", "TapTap"), "_original_index_test": len(test_games)})
                    except json.JSONDecodeError:
                        print(f"[测试警告] 无法解析行: {line.strip()}")
            print(f"[测试模式] 从 {target_file} 加载了 {len(test_games)} 个游戏进行测试。")
        except Exception as e:
            print(f"[测试错误] 读取测试文件时出错 ({target_file}): {e}")
            test_games = []
    else:
        print(f"[测试错误] 测试文件未找到 {target_file}")

    # Add a specific test case for space handling
    test_games.append({"name": "地下城与勇士", "source": "Test", "_original_index_test": len(test_games)}) # Name with space
    test_games.append({"name": "泡泡龙 ", "source": "Test", "_original_index_test": len(test_games)}) # Space at end
    test_games.append({"name": "鸣潮", "source": "Test", "_original_index_test": len(test_games)}) # Known game

    if test_games:
        print("\n[测试模式] === 开始测试版号匹配 (带缓存和空格逻辑) === \n")
        # The function modifies the list in place
        match_version_numbers_for_games(test_games)

        print("\n[测试模式] === 测试结果 (列表已被修改) === ")
        print(json.dumps(test_games, indent=2, ensure_ascii=False))

        # Optional: Clear cache for next clean run if needed (for testing purposes only)
        # if os.path.exists(CACHE_FILE):
        #     print("\n[测试模式] 清理缓存文件...")
        #     os.remove(CACHE_FILE)
    else:
        print("\n[测试模式] 未能加载测试数据，跳过版号匹配测试。") 