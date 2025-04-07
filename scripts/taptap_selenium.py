# scripts/taptap_selenium.py
# 基于 crawler.py 更新，用于抓取 TapTap 日历页面的游戏信息

import os
import time
import random
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
# 注意：这里使用 Edge，如果你想用 Chrome，需要改为 ChromeDriverManager 和 webdriver.Chrome
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# 保存结果的文件夹 (如果需要调试保存页面)
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

def get_taptap_games_for_date(target_date_str):
    """
    获取指定日期的 TapTap 游戏信息。
    参考自 crawler.py 中的 crawl_one_day。

    参数:
        target_date_str (str): 目标日期，格式 "YYYY-MM-DD"

    返回:
        list: 包含游戏信息字典的列表 [{'name': ..., 'status': ..., 'publisher': ..., 'category': ..., 'rating': ..., 'date': ...}]，如果出错则返回空列表。
    """
    print(f"开始抓取 TapTap 日期 {target_date_str} 的游戏信息...")
    driver = setup_driver(headless=True) # 默认使用无头模式
    if not driver:
        return []

    results = []
    url = f"https://www.taptap.cn/app-calendar/{target_date_str}"

    try:
        driver.get(url)
        print(f"已访问: {url}")

        # 等待页面主要内容加载
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.daily-event-list__content"))
            )
            print("页面主要内容加载完成。")
        except TimeoutException:
            print("等待页面主要内容超时或未找到元素。可能是该日期无游戏或页面结构改变。")
            # 即使超时，也尝试查找游戏元素，可能只是部分加载
            pass
        except Exception as e:
             print(f"等待页面元素时发生错误: {e}")
             # 发生其他异常，可能无法继续
             driver.quit()
             return []

        # 查找游戏元素
        # 使用 find_elements 以防当天没有游戏
        game_elements = driver.find_elements(By.CSS_SELECTOR, "div.daily-event-list__content > a.tap-router")

        if not game_elements:
            print(f"日期 {target_date_str} 未找到游戏信息。")
            driver.quit()
            return []

        print(f"找到 {len(game_elements)} 个潜在的游戏条目。开始提取信息...")

        # 记录原始窗口句柄
        original_window = driver.current_window_handle

        for index, g_element in enumerate(game_elements):
            print(f"-- 处理第 {index + 1} 个游戏 --")
            random_delay()
            # Initialize all fields
            name, status, publisher, category, rating = "未知名称", "未知状态", "未知厂商", "未知类型", "未知评分"
            platform, description, link = "未知平台", "", ""

            # --- 在列表页提取信息 --- 
            try:
                # 名称
                name_el = g_element.find_element(By.CSS_SELECTOR, "div.daily-event-app-info__title")
                name = name_el.get_attribute("content").strip()
                print(f"  名称: {name}")
            except NoSuchElementException:
                print("  未找到名称元素")
            except Exception as e:
                 print(f"  提取名称时出错: {e}")

            try:
                # 类型/标签
                tag_elements = g_element.find_elements(By.CSS_SELECTOR, "div.daily-event-app-info__tag div.tap-label-tag")
                category = "/".join([t.text.strip() for t in tag_elements]) if tag_elements else "未知类型"
                print(f"  类型: {category}")
            except NoSuchElementException:
                 print("  未找到类型标签元素")
            except Exception as e:
                 print(f"  提取类型时出错: {e}")

            try:
                # 评分
                rating_el = g_element.find_element(By.CSS_SELECTOR, "div.daily-event-app-info__rating .tap-rating__number")
                rating = rating_el.text.strip()
                print(f"  评分: {rating}")
            except NoSuchElementException:
                # 评分可能不存在，是正常情况
                rating = "暂无评分"
                print("  未找到评分元素 (可能是暂无评分)")
            except Exception as e:
                 print(f"  提取评分时出错: {e}")

            try:
                # 状态 (尝试两种可能的选择器)
                try:
                    status_el = g_element.find_element(By.CSS_SELECTOR, "span.event-type-label__title")
                    status = status_el.text.strip()
                except NoSuchElementException:
                    status_el = g_element.find_element(By.CSS_SELECTOR, "div.event-recommend-label__title")
                    status = status_el.text.strip()
                print(f"  状态: {status}")
            except NoSuchElementException:
                print("  未找到状态元素")
                status = "未知状态" # 确保有默认值
            except Exception as e:
                 print(f"  提取状态时出错: {e}")

            # --- 访问详情页提取厂商、平台、简介、链接 --- 
            publisher = "未知厂商"
            try:
                href = g_element.get_attribute("href")
                if href:
                    if not href.startswith("http"):
                        link = "https://www.taptap.cn" + href
                    else:
                        link = href # Store the detail page URL
                        
                    print(f"  尝试访问详情页: {link}")
                    
                    # 在新标签页打开
                    driver.execute_script("window.open(arguments[0]);", link)
                    WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
                    
                    new_window = [window for window in driver.window_handles if window != original_window][0]
                    driver.switch_to.window(new_window)
                    print(f"  已切换到新窗口: {driver.current_url}")
                    random_delay(1, 2) # 给详情页加载时间

                    # --- 在详情页提取 厂商, 平台, 简介 --- 
                    try:
                        # --- 提取厂商 (逻辑不变) ---
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.row-card.app-intro"))
                        )
                        print("  详情页介绍容器已加载。")
                        info_elements = driver.find_elements(By.CSS_SELECTOR, "div.flex-center--y a.tap-router")
                        possible_publishers = {}
                        for elem in info_elements:
                            try:
                                label_element = elem.find_element(By.CSS_SELECTOR, "div.gray-06.mr-6")
                                label = label_element.text.strip()
                                value_element = elem.find_element(By.CSS_SELECTOR, "div.tap-text.tap-text__one-line")
                                value = value_element.text.strip()
                                if label and value:
                                    possible_publishers[label] = value
                                    print(f"    找到标签: {label}, 值: {value}")
                            except Exception:
                                continue
                                
                        priority = ["厂商", "发行", "开发"]
                        found_publisher = False
                        for key in priority:
                            if key in possible_publishers:
                                publisher = possible_publishers[key]
                                print(f"  根据优先级 '{key}' 确定厂商为: {publisher}")
                                found_publisher = True
                                break
                        if not found_publisher:
                             print("  未能根据优先级找到厂商信息，保留 '未知厂商'。")
                             
                        # --- 提取平台 --- 
                        try:
                            platform_elements = driver.find_elements(By.CSS_SELECTOR, ".platform-picker-switch__item div")
                            # Filter out potential empty divs or other non-platform text
                            platforms = [elem.text.strip() for elem in platform_elements if elem.text.strip()]
                            if platforms:
                                platform = "/".join(platforms) # Join all found platforms
                                print(f"  平台: {platform}")
                            else:
                                print("  未找到有效的平台信息文本。")
                                platform = "未知平台"
                        except NoSuchElementException:
                            print("  未找到平台信息元素。")
                            platform = "未知平台" # Default if not found
                        except Exception as plat_e:
                            print(f"  提取平台信息时出错: {plat_e}")
                            platform = "未知平台"
                            
                        # --- 提取简介 --- 
                        try:
                            description_element = driver.find_element(By.CSS_SELECTOR, "div.app-intro__summary span")
                            description = description_element.text.strip()
                            print(f"  简介: {description[:50]}..." if description else "无简介") # Print first 50 chars
                        except NoSuchElementException:
                            print("  未找到简介元素。")
                            description = ""
                        except Exception as desc_e:
                            print(f"  提取简介时出错: {desc_e}")
                            description = ""
                            
                    except TimeoutException:
                        print("  等待详情页介绍容器超时。")
                    except Exception as detail_e:
                        print(f"  在详情页提取信息时出错: {detail_e}")

                    # 关闭新标签页并切回
                    print("  关闭详情页窗口并切回列表页。")
                    driver.close()
                    driver.switch_to.window(original_window)
                    # 确认切换成功
                    WebDriverWait(driver, 5).until(EC.number_of_windows_to_be(1))
                    print(f"  已切回原始窗口: {driver.current_url}")
                else:
                    print("  未找到游戏详情页链接。")

            except Exception as href_e:
                print(f"  处理详情页链接或切换窗口时出错: {href_e}")
                # 如果窗口切换出错，尝试恢复到原始窗口
                try:
                    if len(driver.window_handles) > 1:
                         driver.close() # 关闭可能残留的窗口
                    driver.switch_to.window(original_window)
                except Exception as recovery_e:
                    print(f"  尝试恢复窗口时出错: {recovery_e}")
                    # 如果无法恢复，可能需要退出并清理
                    raise # 重新抛出异常，让外部知道出错了

            results.append({
                "name": name,
                "platform": platform, # 新增平台
                "status": status,
                "publisher": publisher,
                "category": category,
                "rating": rating,
                "description": description, # 新增简介
                "link": link, # 新增链接
                "date": target_date_str, 
                "source": "TapTap" 
            })
            print(f"-- 第 {index + 1} 个游戏处理完毕 --\n")

    except Exception as e:
        print(f"抓取过程中发生未预料的错误: {e}")
        # 可以考虑保存当前页面源码供调试
        # try:
        #     with open(os.path.join(DATA_DIR, f'taptap_error_{target_date_str}.html'), 'w', encoding='utf-8') as f:
        #         f.write(driver.page_source)
        #     print("错误页面源码已保存。")
        # except Exception as save_e:
        #      print(f"保存错误页面源码失败: {save_e}")

    finally:
        if driver:
            driver.quit()
            print("浏览器已关闭。")

    print(f"TapTap 日期 {target_date_str} 抓取完成，共获取 {len(results)} 条有效数据。")
    return results

# --- 主程序入口 (用于测试) --- #
if __name__ == "__main__":
    # 测试获取特定日期的数据
    # test_date = datetime.now().strftime("%Y-%m-%d") # 默认测试当天
    test_date = "2025-04-07" # 或者指定一个日期进行测试
    
    print(f"\n === 开始测试 TapTap 抓取 ({test_date}) === \n")
    games_data = get_taptap_games_for_date(test_date)
    
    if games_data:
        print(f"\n === 测试结果 ({len(games_data)} 条) === ")
        # 打印所有获取到的游戏信息，包含新字段
        for i, game in enumerate(games_data):
            print(f"[{i+1}] 名称: {game.get('name', 'N/A')}")
            print(f"    平台: {game.get('platform', 'N/A')}")
            print(f"    状态: {game.get('status', 'N/A')}")
            print(f"    厂商: {game.get('publisher', 'N/A')}")
            print(f"    评分: {game.get('rating', 'N/A')}")
            print(f"    链接: {game.get('link', 'N/A')}")
            desc = game.get('description', '')
            print(f"    简介: {desc[:30]}..." if desc else "无")
            print("---")
        # 可以选择保存到 JSON 文件
        # import json
        # test_output_path = os.path.join(DATA_DIR, f'taptap_test_{test_date}.json')
        # with open(test_output_path, 'w', encoding='utf-8') as f:
        #     json.dump(games_data, f, ensure_ascii=False, indent=2)
        # print(f"\n测试结果已保存到: {test_output_path}")
    else:
        print("\n === 测试未获取到数据 ===") 