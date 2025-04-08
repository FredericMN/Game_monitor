# scripts/taptap_selenium.py
# 基于 crawler.py 更新，用于抓取 TapTap 日历页面的游戏信息

import os
import time
import random
import json # Ensure json is imported
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
# 注意：这里使用 Edge，如果你想用 Chrome，需要改为 ChromeDriverManager 和 webdriver.Chrome
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# 保存结果的文件夹
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

def random_delay(min_sec=0.5, max_sec=1.5):
    """避免爬取过快"""
    time.sleep(random.uniform(min_sec, max_sec))

def setup_driver(headless=True):
    """
    配置并初始化 Edge 浏览器
    """
    options = webdriver.EdgeOptions()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36")
    
    try:
        service = EdgeService(EdgeChromiumDriverManager().install())
        driver = webdriver.Edge(service=service, options=options)
        print("Edge WebDriver 初始化成功。")
        return driver
    except Exception as e:
        print(f"初始化 Edge WebDriver 时出错: {e}")
        return None

def load_existing_links(filepath):
    """从 JSONL 文件加载已存在的游戏链接"""
    existing_links = set()
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if 'link' in data and data['link']:
                            existing_links.add(data['link'])
                    except json.JSONDecodeError:
                        print(f"警告: 无法解析行: {line.strip()}")
            print(f"从 {filepath} 加载了 {len(existing_links)} 个已存在的游戏链接。")
        except Exception as e:
            print(f"读取已存在链接文件时出错 ({filepath}): {e}")
    return existing_links

def get_taptap_games_for_date(target_date_str):
    """
    获取指定日期的 TapTap 游戏信息, 支持增量保存和断点续爬。
    """
    print(f"开始抓取 TapTap 日期 {target_date_str} 的游戏信息 (增量模式)...")
    
    output_filename = f'taptap_games_{target_date_str}.jsonl'
    output_path = os.path.join(DATA_DIR, output_filename)
    
    # 1. 加载已存在的链接
    existing_links = load_existing_links(output_path)
    
    driver = setup_driver(headless=True)
    if not driver:
        return 0 # 返回新增数量 0

    url = f"https://www.taptap.cn/app-calendar/{target_date_str}"
    newly_scraped_count = 0
    processed_count = 0

    try:
        driver.get(url)
        print(f"已访问: {url}")

        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.daily-event-list__content"))
            )
            print("页面主要内容加载完成。")
        except TimeoutException:
            print("等待页面主要内容超时或未找到元素。")
            # 即使超时也尝试继续，可能只是部分加载
        except Exception as e:
             print(f"等待页面元素时发生错误: {e}")
             driver.quit()
             return 0

        game_elements = driver.find_elements(By.CSS_SELECTOR, "div.daily-event-list__content > a.tap-router")

        if not game_elements:
            print(f"日期 {target_date_str} 未找到游戏条目。")
            driver.quit()
            return 0

        print(f"找到 {len(game_elements)} 个潜在的游戏条目。开始处理...")

        original_window = driver.current_window_handle
        
        # 2. 打开文件准备追加
        with open(output_path, 'a', encoding='utf-8') as outfile:
            for index, g_element in enumerate(game_elements):
                processed_count += 1
                print(f"\n-- 检查第 {index + 1}/{len(game_elements)} 个条目 --")
                
                # --- 3. 提前提取链接并检查是否已存在 ---
                current_link = ""
                game_name_for_skip_log = "未知名称" # 用于跳过日志
                try:
                    # 尝试先获取名字用于日志
                    try:
                        name_el = g_element.find_element(By.CSS_SELECTOR, "div.daily-event-app-info__title")
                        game_name_for_skip_log = name_el.get_attribute("content").strip()
                    except: pass # 获取名字失败不影响核心逻辑

                    href = g_element.get_attribute("href")
                    if href:
                        if not href.startswith("http"):
                            current_link = "https://www.taptap.cn" + href
                        else:
                            current_link = href
                        
                        if current_link in existing_links:
                            print(f"链接 {current_link} (游戏名: {game_name_for_skip_log}) 已存在于 {output_filename}，跳过。")
                            continue # 跳到下一个游戏
                        else:
                            print(f"新链接: {current_link} (游戏名: {game_name_for_skip_log})，准备处理...")
                    else:
                        print("警告: 未能从此条目提取 href 链接，跳过处理。")
                        continue

                except Exception as link_check_e:
                    print(f"提取或检查链接时出错: {link_check_e}，跳过此条目。")
                    continue
                    
                # --- 4. 如果是新链接，则开始完整爬取 ---
                random_delay()
                name, status, publisher, category, rating = "未知名称", "未知状态", "未知厂商", "未知类型", "未知评分"
                platform, description, icon_url = "未知平台", "", "" # link 已在上面获取

                # 标记此游戏的数据是否完整获取成功
                scrape_successful = False
                game_data = {}

                try:
                    # --- 在列表页提取信息 ---
                    # (名称已尝试在上面获取，这里可以再次获取或使用上面的)
                    try:
                        name_el = g_element.find_element(By.CSS_SELECTOR, "div.daily-event-app-info__title")
                        name = name_el.get_attribute("content").strip()
                    except Exception as e: name = game_name_for_skip_log # 使用前面获取的
                    print(f"  名称: {name}")
                    
                    # (其他列表页信息提取 - 类型、评分、状态)
                    try:
                        tag_elements = g_element.find_elements(By.CSS_SELECTOR, "div.daily-event-app-info__tag div.tap-label-tag")
                        category = "/".join([t.text.strip() for t in tag_elements]) if tag_elements else "未知类型"
                        print(f"  类型: {category}")
                    except Exception as e: print(f"  提取类型时出错: {e}")

                    try:
                        rating_el = g_element.find_element(By.CSS_SELECTOR, "div.daily-event-app-info__rating .tap-rating__number")
                        rating = rating_el.text.strip()
                        print(f"  评分: {rating}")
                    except NoSuchElementException:
                        rating = "暂无评分"
                        print("  未找到评分元素 (可能是暂无评分)")
                    except Exception as e: print(f"  提取评分时出错: {e}")

                    try:
                        try:
                            status_el = g_element.find_element(By.CSS_SELECTOR, "span.event-type-label__title")
                            status = status_el.text.strip()
                        except NoSuchElementException:
                            status_el = g_element.find_element(By.CSS_SELECTOR, "div.event-recommend-label__title")
                            status = status_el.text.strip()
                        print(f"  状态: {status}")
                    except NoSuchElementException:
                        print("  未找到状态元素")
                        status = "未知状态"
                    except Exception as e: print(f"  提取状态时出错: {e}")

                    # --- 访问详情页和 all-info 页 ---
                    print(f"  访问详情页: {current_link}")
                    driver.execute_script("window.open(arguments[0]);", current_link)
                    WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
                    detail_window = [window for window in driver.window_handles if window != original_window][0]
                    driver.switch_to.window(detail_window)
                    print(f"  已切换到详情页窗口: {driver.current_url}")
                    random_delay(1, 2)

                    # 在详情页提取 厂商, 平台, 图标
                    try:
                        intro_present_locator = (By.CSS_SELECTOR, "div.app-intro, div.row-card.app-intro")
                        WebDriverWait(driver, 10).until(EC.presence_of_element_located(intro_present_locator))
                        print("  详情页主要内容容器已加载。")

                        # 图标 URL
                        try:
                           icon_img_element = driver.find_element(By.CSS_SELECTOR, "div.app-info-board__img > img")
                           icon_url = icon_img_element.get_attribute('src')
                           print(f"  提取到图标 URL: {icon_url[:60]}..." if icon_url else "无 src")
                        except Exception as icon_e: print(f"  提取图标时出错: {icon_e}")

                        # 厂商
                        publisher = "未知厂商" # Reset before extraction attempt
                        try:
                           info_elements = driver.find_elements(By.CSS_SELECTOR, "div.flex-center--y a.tap-router")
                           possible_publishers = {}
                           for elem in info_elements:
                               try:
                                   label_element = elem.find_element(By.CSS_SELECTOR, "div.gray-06.mr-6")
                                   label = label_element.text.strip()
                                   value_element = elem.find_element(By.CSS_SELECTOR, "div.tap-text.tap-text__one-line")
                                   value = value_element.text.strip()
                                   if label and value: possible_publishers[label] = value
                               except Exception: continue
                           priority = ["厂商", "发行", "开发"]
                           found_publisher = False
                           for key in priority:
                               if key in possible_publishers:
                                   publisher = possible_publishers[key]
                                   print(f"  厂商: {publisher}")
                                   found_publisher = True
                                   break
                           if not found_publisher: print("  未能根据优先级找到厂商信息。")
                        except Exception as pub_e: print(f"  提取厂商时出错: {pub_e}")

                        # 平台
                        platform = "未知平台" # Reset before extraction attempt
                        try:
                            platform_elements = driver.find_elements(By.CSS_SELECTOR, ".platform-picker-switch__item div")
                            platforms = [elem.text.strip() for elem in platform_elements if elem.text.strip()]
                            if platforms:
                                platform = "/".join(platforms)
                                print(f"  平台: {platform}")
                            else: print("  未找到平台信息文本。")
                        except Exception as plat_e: print(f"  提取平台信息时出错: {plat_e}")

                        # 访问 all-info 页提取简介
                        description = "" # Reset before extraction attempt
                        full_info_link = current_link.split('?')[0] + '/all-info'
                        print(f"  尝试访问完整信息页: {full_info_link}")
                        try:
                            driver.execute_script("window.open(arguments[0]);", full_info_link)
                            WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(3))
                            all_info_window = [w for w in driver.window_handles if w != original_window and w != detail_window][0]
                            driver.switch_to.window(all_info_window)
                            print(f"  已切换到完整信息页窗口: {driver.current_url}")
                            random_delay(1, 2)

                            try:
                                description_container_selector = "div.text-modal"
                                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, description_container_selector)))
                                desc_container = driver.find_element(By.CSS_SELECTOR, description_container_selector)
                                full_description_text = desc_container.text.strip()
                                if full_description_text.endswith("收起"): full_description_text = full_description_text[:-2].strip()
                                elif full_description_text.endswith("更多"): full_description_text = full_description_text[:-2].strip()
                                description = full_description_text
                                print(f"  已获取完整简介: {description[:50]}...")
                            except Exception as desc_extract_e:
                                print(f"  在完整信息页提取简介时出错: {desc_extract_e}")

                            # 关闭 all-info 窗口并切回详情页
                            driver.close()
                            driver.switch_to.window(detail_window)
                            WebDriverWait(driver, 5).until(EC.number_of_windows_to_be(2))
                            print("  已切回详情页窗口。")

                        except Exception as all_info_nav_e:
                            print(f"  访问或处理完整信息页 ({full_info_link}) 时出错: {all_info_nav_e}. 简介可能不完整。")
                            if driver.current_window_handle != detail_window and detail_window in driver.window_handles:
                                try: driver.switch_to.window(detail_window)
                                except Exception: pass

                    except Exception as detail_e:
                        print(f"  在详情页提取信息时出错: {detail_e}")
                        # 即使详情页出错，仍然尝试关闭窗口并继续

                    # 关闭详情页窗口并切回原始窗口
                    print("  关闭详情页窗口。")
                    if driver.current_window_handle == detail_window:
                         driver.close()
                    driver.switch_to.window(original_window)
                    WebDriverWait(driver, 5).until(EC.number_of_windows_to_be(1))
                    print("  已切回原始窗口。")

                    # 标记成功，准备写入
                    scrape_successful = True
                    
                except Exception as main_scrape_e:
                    print(f"处理游戏 {name} ({current_link}) 时发生严重错误: {main_scrape_e}")
                    # 尝试恢复窗口状态
                    active_handles = driver.window_handles
                    if original_window in active_handles and driver.current_window_handle != original_window:
                        try:
                            for handle in active_handles:
                                if handle != original_window:
                                    driver.switch_to.window(handle)
                                    driver.close()
                            driver.switch_to.window(original_window)
                            print("  已尝试关闭多余窗口并切回原始窗口。")
                        except Exception as recovery_e:
                            print(f"  尝试恢复窗口时出错: {recovery_e}. 可能需要重启驱动.")
                            # 在这种严重错误下，可能最好退出
                            raise main_scrape_e 
                    scrape_successful = False # 标记失败，不写入

                # --- 5. 如果成功，立即写入文件 ---
                if scrape_successful:
                    game_data = {
                        "name": name,
                        "platform": platform,
                        "status": status,
                        "publisher": publisher,
                        "category": category,
                        "rating": rating,
                        "description": description,
                        "link": current_link, # 使用检查时确认的链接
                        "icon_url": icon_url,
                        "date": target_date_str,
                        "source": "TapTap"
                    }
                    try:
                        json.dump(game_data, outfile, ensure_ascii=False)
                        outfile.write('\n')
                        newly_scraped_count += 1
                        # 将链接添加到内存中的集合，以防万一同一批次内有完全重复的条目
                        existing_links.add(current_link) 
                        print(f"成功处理并保存游戏 {name} 到 {output_filename}")
                    except Exception as write_e:
                         print(f"写入游戏 {name} 数据到文件时出错: {write_e}")
                else:
                     print(f"处理游戏 {name} ({current_link}) 未成功，未写入文件。")

            # 循环结束
            print("\n所有列表条目处理完毕。")

    except Exception as e:
        print(f"抓取过程中发生未预料的错误: {e}")
        # 可以考虑保存错误页面等调试信息
    finally:
        if driver:
            driver.quit()
            print("浏览器已关闭。")

    print(f"\nTapTap 日期 {target_date_str} 抓取完成。")
    print(f"总共检查 {processed_count} 个列表条目。")
    print(f"本次运行新增 {newly_scraped_count} 条游戏数据到 {output_filename}。")
    
    return newly_scraped_count # 返回本次新增的数量

# --- 主程序入口 (用于测试) --- #
if __name__ == "__main__":
    # 测试获取特定日期的数据
    test_date = datetime.now().strftime("%Y-%m-%d") # 默认测试当天
    # test_date = "2024-05-15" # 或者指定一个日期进行测试

    print(f"\n === 开始测试 TapTap 增量抓取 ({test_date}) === \n")
    new_games_count = get_taptap_games_for_date(test_date)
    
    print(f"\n === 测试完成 ({test_date}) === ")
    print(f"本次运行新增 {new_games_count} 条数据。")
    print(f"完整数据（包括历史和新增）保存在 data/taptap_games_{test_date}.jsonl 文件中。") 