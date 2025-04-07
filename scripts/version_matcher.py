# scripts/version_matcher.py
# 用于从 NPPA 网站匹配游戏版号信息

import os
import time
import random
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from concurrent.futures import ThreadPoolExecutor, as_completed

# 并发工作线程数 (可以根据机器性能调整)
MAX_MATCH_WORKERS = 2

# 用于缓存查询结果，避免重复查询同一个游戏
version_cache = {}

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

def fetch_single_game_version_info(game_name):
    """
    从 NPPA 网站获取单个游戏的版号信息。
    参考自 crawler.py 中的 fetch_game_info。

    参数:
        game_name (str): 游戏名称。

    返回:
        dict: 包含版号信息的字典，如果未找到或出错则返回 None。
              字典结构: {'publisher_unit': ..., 'operator_unit': ..., 'approval_num': ..., 
                       'publication_num': ..., 'approval_date': ..., 'game_type': ..., 
                       'declaration_category': ..., 'multiple_results': '是'/'否'}
    """
    if not game_name or game_name == "未知名称":
        return None
        
    # 检查缓存
    if game_name in version_cache:
        print(f"[版号匹配] 游戏 '{game_name}' 使用缓存结果。")
        return version_cache[game_name]

    print(f"[版号匹配] 开始查询游戏 '{game_name}' 的版号信息...")
    driver = setup_matcher_driver(headless=True)
    if not driver:
        version_cache[game_name] = None # 记录查询失败
        return None

    result_info = None
    try:
        # 清理游戏名称中的括号等内容
        query_name = re.sub(r'（[^）]*）', '', game_name)
        query_name = re.sub(r'\([^)]*\)', '', query_name).strip()
        if not query_name:
             print(f"[版号匹配] 游戏名 '{game_name}' 清理后为空，跳过查询。")
             version_cache[game_name] = None
             driver.quit()
             return None
             
        url = f"https://www.nppa.gov.cn/bsfw/jggs/cxjg/index.html?mc={query_name}&cbdw=&yydw=&wh=undefined&description=#"
        print(f"[版号匹配] 访问查询 URL: {url}")

        # 添加重试机制访问页面
        max_retries = 3
        page_loaded = False
        for retry in range(max_retries):
            try:
                driver.get(url)
                # 等待核心表格数据区域出现
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#dataCenter"))
                )
                print("[版号匹配] 查询结果页面加载成功。")
                page_loaded = True
                break # 成功加载则跳出重试
            except TimeoutException:
                print(f"[版号匹配] 游戏 '{game_name}' 页面加载超时 (尝试 {retry+1}/{max_retries})。")
                if retry == max_retries - 1:
                    print("[版号匹配] 多次尝试加载页面失败。")
            except Exception as load_e:
                 print(f"[版号匹配] 加载页面时发生错误 (尝试 {retry+1}/{max_retries}): {load_e}")
                 if retry == max_retries - 1:
                      print("[版号匹配] 多次尝试加载页面失败。")
            # 重试前稍作等待
            if not page_loaded and retry < max_retries - 1:
                 time.sleep(2)
                 
        if not page_loaded:
            raise TimeoutException("页面加载失败") # 如果最终加载失败，则抛出异常

        # 查找结果表格行
        try:
             # 等待至少一行数据出现 (使用更灵活的等待条件)
             WebDriverWait(driver, 10).until(
                 lambda d: len(d.find_elements(By.CSS_SELECTOR, "#dataCenter tr")) > 0
             )
             result_rows = driver.find_elements(By.CSS_SELECTOR, "#dataCenter tr")
             print(f"[版号匹配] 找到 {len(result_rows)} 条结果。")
        except TimeoutException:
             print(f"[版号匹配] 未查询到游戏 '{game_name}' 的版号信息。")
             result_rows = [] # 确保 result_rows 是列表
        except Exception as find_e:
             print(f"[版号匹配] 查找结果行时出错: {find_e}")
             result_rows = [] # 确保 result_rows 是列表

        if result_rows:
            multiple_results_flag = "是" if len(result_rows) > 1 else "否"
            target_row_element = None
            
            # 尝试寻找完全匹配游戏名的行
            for row in result_rows:
                try:
                    row_game_name = row.find_element(By.CSS_SELECTOR, "td:nth-child(2) a").text.strip()
                    if row_game_name == game_name:
                        target_row_element = row
                        print(f"[版号匹配] 找到与 '{game_name}' 完全匹配的结果行。")
                        break
                except NoSuchElementException:
                    continue # 跳过没有链接的行或结构异常的行
            
            # 如果没有完全匹配的，取第一行作为结果
            if not target_row_element:
                target_row_element = result_rows[0]
                print("[版号匹配] 未找到完全匹配结果，使用第一条结果。")
            
            # 从目标行提取信息
            result_info = extract_info_from_row(target_row_element, multiple_results_flag, driver)
        
        else:
            # 没有找到结果行
            result_info = None

    except TimeoutException as e:
        print(f"[版号匹配] 处理游戏 '{game_name}' 时发生超时: {e}")
        result_info = None # 超时也标记为查询失败
    except Exception as e:
        print(f"[版号匹配] 查询游戏 '{game_name}' 版号时发生未预料错误: {e}")
        result_info = None # 其他异常也标记为查询失败
    finally:
        if driver:
            driver.quit()
            print(f"[版号匹配] 游戏 '{game_name}' 查询结束，浏览器已关闭。")
            
    # 存入缓存
    version_cache[game_name] = result_info
    return result_info

def extract_info_from_row(row_element, multiple_flag, driver):
    """
    从 NPPA 查询结果的一行中提取详细版号信息。
    参考自 crawler.py 中的 extract_game_info。
    """
    try:
        tds = row_element.find_elements(By.TAG_NAME, "td")
        if len(tds) < 7:
            print("[版号匹配] 结果行单元格数量不足 (< 7)。")
            return None
            
        # 列表页信息
        game_name_in_row = tds[1].text.strip() # 实际查到的游戏名
        publisher_unit = tds[2].text.strip()
        operator_unit = tds[3].text.strip()
        approval_num = tds[4].text.strip()
        publication_num = tds[5].text.strip()
        approval_date = tds[6].text.strip()
        print(f"[版号匹配] 从列表页提取: 出版={publisher_unit}, 运营={operator_unit}, 文号={approval_num}, 时间={approval_date}")

        detail_url = ""
        try:
            link_element = tds[1].find_element(By.TAG_NAME, "a")
            detail_url = link_element.get_attribute("href")
        except NoSuchElementException:
            print("[版号匹配] 未找到详情页链接。")

        # 详情页信息
        game_type = "未知类型"
        declaration_category = "未知类别"
        if detail_url:
            print(f"[版号匹配] 尝试访问版号详情页: {detail_url}")
            original_window = driver.current_window_handle
            try:
                driver.execute_script("window.open(arguments[0]);", detail_url)
                WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
                new_window = [window for window in driver.window_handles if window != original_window][0]
                driver.switch_to.window(new_window)
                print(f"[版号匹配] 已切换到详情页窗口: {driver.current_url}")
                random_delay(1, 2)

                try:
                    # 等待详情表格加载
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".cFrame.nFrame table"))
                    )
                    print("[版号匹配] 版号详情表格已加载。")
                    detail_rows = driver.find_elements(By.CSS_SELECTOR, ".cFrame.nFrame table tr")
                    for ln in detail_rows:
                        try:
                            label = ln.find_element(By.XPATH, "./td[1]").text.strip()
                            value = ln.find_element(By.XPATH, "./td[2]").text.strip()
                            if label == "游戏类型":
                                game_type = value
                                print(f"[版号匹配] 找到游戏类型: {game_type}")
                            elif label == "申报类别":
                                declaration_category = value
                                print(f"[版号匹配] 找到申报类别: {declaration_category}")
                        except NoSuchElementException:
                            continue # 跳过不符合结构的行
                        except Exception as cell_e:
                             print(f"[版号匹配] 处理详情单元格时出错: {cell_e}")
                except TimeoutException:
                    print("[版号匹配] 等待版号详情表格超时。")
                except Exception as detail_table_e:
                    print(f"[版号匹配] 处理版号详情表格时出错: {detail_table_e}")

            finally:
                # 确保关闭窗口并切回
                try:
                    if len(driver.window_handles) > 1:
                         driver.close()
                    driver.switch_to.window(original_window)
                    WebDriverWait(driver, 5).until(EC.number_of_windows_to_be(1))
                    print(f"[版号匹配] 已切回原始窗口。")
                except Exception as switch_e:
                    print(f"[版号匹配] 关闭或切换窗口时出错: {switch_e}")
                    # 如果切换失败，可能影响后续操作，但尝试继续
                    pass
        
        # 组装结果字典
        return {
            "publisher_unit": publisher_unit,
            "operator_unit": operator_unit,
            "approval_num": approval_num,
            "publication_num": publication_num,
            "approval_date": approval_date,
            "game_type": game_type,
            "declaration_category": declaration_category,
            "multiple_results": multiple_flag
        }

    except Exception as e:
        print(f"[版号匹配] 从行元素提取信息时出错: {e}")
        return None

def match_version_numbers_for_games(games_list):
    """
    为游戏列表批量匹配版号信息（并发执行）。
    直接修改传入的列表中的字典。

    参数:
        games_list (list): 包含游戏信息字典的列表。每个字典至少需要有 'name' 键。

    返回:
        list: 更新了版号信息后的游戏列表。
    """
    if not games_list:
        return []

    print(f"\n开始为 {len(games_list)} 个游戏批量匹配版号信息 (使用最多 {MAX_MATCH_WORKERS} 个并发线程)...")
    start_time = time.time()
    
    # 创建需要查询的游戏列表（去重，避免重复查询）
    games_to_query = list(set([g.get('name') for g in games_list if g.get('name') and g.get('name') != "未知名称"]))
    print(f"需要查询 {len(games_to_query)} 个独立的游戏名称。")
    
    results_map = {}
    completed_count = 0
    total_query_count = len(games_to_query)

    with ThreadPoolExecutor(max_workers=MAX_MATCH_WORKERS) as executor:
        future_map = {executor.submit(fetch_single_game_version_info, name): name for name in games_to_query}

        for future in as_completed(future_map):
            game_name = future_map[future]
            try:
                version_info = future.result()
                results_map[game_name] = version_info # 存储结果，包括 None
                if version_info:
                     print(f"[版号匹配] 游戏 '{game_name}' 匹配成功。")
                else:
                     print(f"[版号匹配] 游戏 '{game_name}' 未找到版号或查询出错。")
            except Exception as e:
                print(f"[版号匹配] 处理游戏 '{game_name}' 的查询结果时出错: {e}")
                results_map[game_name] = None # 标记为失败
            
            completed_count += 1
            progress = int(completed_count * 100 / total_query_count)
            print(f"[版号匹配] 查询进度: {progress}% ({completed_count}/{total_query_count})", end='\r')
            
    print("\n[版号匹配] 所有查询任务完成。开始将结果合并回游戏列表...")

    # 将查询结果合并回原始列表
    for game_dict in games_list:
        game_name = game_dict.get('name')
        if game_name in results_map:
            version_data = results_map[game_name]
            if version_data:
                # 将版号信息字段添加到游戏字典中
                game_dict.update(version_data)
                # 可以选择添加一个标记，表示版号已查询
                game_dict['version_checked'] = True
            else:
                 # 版号未找到或查询失败
                 game_dict['version_checked'] = False # 标记为已检查但未找到
                 # 可以选择填充默认值
                 game_dict['publisher_unit'] = ""
                 game_dict['operator_unit'] = ""
                 game_dict['approval_num'] = ""
                 # ... 其他版号字段
        else:
            # 游戏名称未查询（例如"未知名称"）
            game_dict['version_checked'] = False

    end_time = time.time()
    print(f"[版号匹配] 批量匹配完成，耗时: {end_time - start_time:.2f} 秒。")
    return games_list

# --- 主程序入口 (用于测试) --- #
if __name__ == "__main__":
    # 构造一些测试游戏数据
    test_games = [
        {"name": "鸣潮", "source": "TapTap"}, # 应该能查到
        {"name": "绝区零", "source": "TapTap"}, # 应该能查到
        {"name": "王者荣耀", "source": "TapTap"}, # 应该能查到
        {"name": "一个不存在的游戏XXX", "source": "TapTap"}, # 查不到
        {"name": "", "source": "TapTap"}, # 空名字
        {"name": "未知名称", "source": "TapTap"}
    ]
    
    print("\n === 开始测试版号匹配 === \n")
    updated_games = match_version_numbers_for_games(test_games)
    
    print("\n === 测试结果 === ")
    import json
    print(json.dumps(updated_games, indent=2, ensure_ascii=False)) 