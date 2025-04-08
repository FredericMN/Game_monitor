# scripts/haoyou_selenium.py
# 基于 taptap_selenium.py 创建，用于抓取好游快爆的游戏信息

import os
import time
import random
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# 保存结果的文件夹
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 好游快爆基础URL
BASE_URL = "https://www.3839.com"
CALENDAR_BASE_URL = "https://www.3839.com/hao/yxzt/kaice"

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

def get_haoyou_games():
    """
    获取好游快爆开测表的游戏信息，支持增量保存
    """
    # 构建输出文件名（基于运行日期）
    current_date = datetime.now().strftime("%Y%m%d")
    output_filename = f'haoyou_games_{current_date}.jsonl'
    output_path = os.path.join(DATA_DIR, output_filename)
    
    print(f"开始抓取好游快爆开测表游戏信息 (增量模式)...")
    
    # 加载已存在的链接
    existing_links = load_existing_links(output_path)
    
    driver = setup_driver(headless=True)
    if not driver:
        return 0 # 返回新增数量 0

    url = CALENDAR_BASE_URL  # 开测表页面URL
    newly_scraped_count = 0
    processed_count = 0

    try:
        driver.get(url)
        print(f"已访问: {url}")

        # 等待主要内容加载完成
        try:
            # 下面的选择器需要根据好游快爆网站的实际结构调整
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.open-test-list"))  # 假设的选择器
            )
            print("页面主要内容加载完成。")
        except TimeoutException:
            print("等待页面主要内容超时或未找到元素。")
        except Exception as e:
            print(f"等待页面元素时发生错误: {e}")
            driver.quit()
            return 0

        # 查找所有游戏条目
        # 以下选择器需要根据好游快爆网站实际结构调整
        game_elements = driver.find_elements(By.CSS_SELECTOR, "div.game-item")  # 假设的选择器

        if not game_elements:
            print("未找到游戏条目。")
            driver.quit()
            return 0

        print(f"找到 {len(game_elements)} 个潜在的游戏条目。开始处理...")

        original_window = driver.current_window_handle
        
        # 打开文件准备追加
        with open(output_path, 'a', encoding='utf-8') as outfile:
            for index, g_element in enumerate(game_elements):
                processed_count += 1
                print(f"\n-- 检查第 {index + 1}/{len(game_elements)} 个条目 --")
                
                # 定义要抓取的字段
                name, status, publisher, category = "未知名称", "未知状态", "未知厂商", "未知类型"
                platform, description, icon_url, link = "未知平台", "", "", ""
                date = current_date  # 使用当前日期作为日期字段

                # 提前提取链接并检查是否已存在
                try:
                    # 根据好游快爆网站结构调整以下选择器
                    link_element = g_element.find_element(By.CSS_SELECTOR, "a.game-link")  # 假设的选择器
                    href = link_element.get_attribute("href")
                    if href:
                        link = href
                        if link in existing_links:
                            print(f"链接 {link} 已存在于 {output_filename}，跳过。")
                            continue
                        else:
                            print(f"新链接: {link}，准备处理...")
                    else:
                        print("警告: 未能从此条目提取链接，跳过处理。")
                        continue
                except Exception as e:
                    print(f"提取或检查链接时出错: {e}，跳过此条目。")
                    continue

                # 标记此游戏的数据是否完整获取成功
                scrape_successful = False
                game_data = {}

                try:
                    # 从列表页提取基本信息
                    try:
                        # 名称 - 根据实际网站结构调整选择器
                        name_element = g_element.find_element(By.CSS_SELECTOR, "div.game-name")  # 假设的选择器
                        name = name_element.text.strip()
                        print(f"  名称: {name}")
                    except Exception as e:
                        print(f"  提取名称时出错: {e}")

                    try:
                        # 状态 - 根据实际网站结构调整选择器
                        status_element = g_element.find_element(By.CSS_SELECTOR, "div.game-status")  # 假设的选择器
                        status = status_element.text.strip()
                        print(f"  状态: {status}")
                    except Exception as e:
                        print(f"  提取状态时出错: {e}")

                    try:
                        # 游戏图标 - 根据实际网站结构调整选择器
                        icon_element = g_element.find_element(By.CSS_SELECTOR, "img.game-icon")  # 假设的选择器
                        icon_url = icon_element.get_attribute("src")
                        print(f"  图标URL: {icon_url}")
                    except Exception as e:
                        print(f"  提取图标URL时出错: {e}")

                    # 访问详情页获取更多信息
                    print(f"  访问详情页: {link}")
                    driver.execute_script("window.open(arguments[0]);", link)
                    WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
                    detail_window = [window for window in driver.window_handles if window != original_window][0]
                    driver.switch_to.window(detail_window)
                    print(f"  已切换到详情页窗口: {driver.current_url}")
                    random_delay(1, 2)

                    # 在详情页提取更多信息
                    try:
                        # 等待详情页加载
                        # 根据好游快爆网站结构调整选择器
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "div.game-detail"))  # 假设的选择器
                        )

                        # 提取厂商信息
                        try:
                            # 根据实际网站结构调整选择器
                            publisher_element = driver.find_element(By.CSS_SELECTOR, "div.game-publisher")  # 假设的选择器
                            publisher = publisher_element.text.strip()
                            print(f"  厂商: {publisher}")
                        except Exception as e:
                            print(f"  提取厂商信息时出错: {e}")

                        # 提取平台信息
                        try:
                            # 根据实际网站结构调整选择器
                            platform_element = driver.find_element(By.CSS_SELECTOR, "div.game-platform")  # 假设的选择器
                            platform = platform_element.text.strip()
                            print(f"  平台: {platform}")
                        except Exception as e:
                            print(f"  提取平台信息时出错: {e}")

                        # 提取类别信息
                        try:
                            # 根据实际网站结构调整选择器
                            category_elements = driver.find_elements(By.CSS_SELECTOR, "div.game-category span")  # 假设的选择器
                            if category_elements:
                                category = "/".join([cat.text.strip() for cat in category_elements])
                            print(f"  类别: {category}")
                        except Exception as e:
                            print(f"  提取类别信息时出错: {e}")

                        # 提取游戏描述
                        try:
                            # 根据实际网站结构调整选择器
                            description_element = driver.find_element(By.CSS_SELECTOR, "div.game-description")  # 假设的选择器
                            description = description_element.text.strip()
                            print(f"  描述: {description[:50]}..." if len(description) > 50 else f"  描述: {description}")
                        except Exception as e:
                            print(f"  提取游戏描述时出错: {e}")

                    except Exception as e:
                        print(f"  在详情页提取信息时出错: {e}")

                    # 提取游戏开测日期（如果列表页没有）
                    try:
                        # 根据实际网站结构调整选择器
                        date_element = driver.find_element(By.CSS_SELECTOR, "div.test-date")  # 假设的选择器
                        test_date = date_element.text.strip()
                        if test_date:
                            date = test_date
                        print(f"  开测日期: {date}")
                    except Exception as e:
                        print(f"  提取开测日期时出错: {e}")

                    # 关闭详情页窗口并切回原始窗口
                    driver.close()
                    driver.switch_to.window(original_window)
                    WebDriverWait(driver, 5).until(EC.number_of_windows_to_be(1))
                    print("  已切回原始窗口。")

                    # 标记成功，准备写入
                    scrape_successful = True

                except Exception as e:
                    print(f"处理游戏 {name} ({link}) 时发生严重错误: {e}")
                    # 尝试恢复窗口状态
                    try:
                        for handle in driver.window_handles:
                            if handle != original_window:
                                driver.switch_to.window(handle)
                                driver.close()
                        driver.switch_to.window(original_window)
                    except Exception as recovery_e:
                        print(f"  尝试恢复窗口时出错: {recovery_e}")
                    scrape_successful = False

                # 如果成功，立即写入文件
                if scrape_successful:
                    game_data = {
                        "name": name,
                        "platform": platform,
                        "status": status,
                        "publisher": publisher,
                        "category": category,
                        "description": description,
                        "link": link,
                        "icon_url": icon_url,
                        "date": date,
                        "source": "好游快爆"
                    }
                    try:
                        json.dump(game_data, outfile, ensure_ascii=False)
                        outfile.write('\n')
                        newly_scraped_count += 1
                        # 将链接添加到内存中的集合，避免同一批次内有重复条目
                        existing_links.add(link)
                        print(f"成功处理并保存游戏 {name} 到 {output_filename}")
                    except Exception as write_e:
                        print(f"写入游戏 {name} 数据到文件时出错: {write_e}")
                else:
                    print(f"处理游戏 {name} ({link}) 未成功，未写入文件。")

            # 循环结束
            print("\n所有列表条目处理完毕。")

    except Exception as e:
        print(f"抓取过程中发生未预料的错误: {e}")
    finally:
        if driver:
            driver.quit()
            print("浏览器已关闭。")

    print(f"\n好游快爆抓取完成。")
    print(f"总共检查 {processed_count} 个列表条目。")
    print(f"本次运行新增 {newly_scraped_count} 条游戏数据到 {output_filename}。")
    
    return newly_scraped_count

# --- 主程序入口 (用于测试) --- #
if __name__ == "__main__":
    print("\n === 开始测试好游快爆开测表抓取 === \n")
    new_games_count = get_haoyou_games()
    print("\n === 测试完成 === ")
    print(f"本次运行新增 {new_games_count} 条数据。")
    current_date = datetime.now().strftime("%Y%m%d")
    print(f"完整数据保存在 data/haoyou_games_{current_date}.jsonl 文件中。") 