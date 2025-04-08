# scripts/16p_selenium.py
# 用于抓取 16p 网站的开测表信息 (国内游戏)

import os
import time
import random
import json
import re # 导入 re 用于解析样式字符串
from datetime import datetime
from urllib.parse import urljoin # 用于合并基础 URL 和相对路径
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

# 16p 基础 URL
BASE_URL = "https://www.16p.com"

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
    """从 JSONL 文件加载已存在的游戏详情页链接"""
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
            print(f"从 {filepath} 加载了 {len(existing_links)} 个已存在的链接。")
        except Exception as e:
            print(f"读取已存在链接文件时出错 ({filepath}): {e}")
    return existing_links

def get_16p_data(target_url): 
    """
    获取指定 URL (16p 开测表) 的国内游戏信息, 支持增量保存。
    """
    print(f"开始抓取 16p 页面 {target_url} 的国内游戏信息 (增量模式)...")
    
    # 输出文件名格式调整 (基于运行日期)
    output_filename = f'16p_games_{datetime.now().strftime("%Y%m%d")}.jsonl' 
    output_path = os.path.join(DATA_DIR, output_filename)
    
    # 1. 加载已存在的链接 (基于详情页链接)
    existing_links = load_existing_links(output_path)
    
    driver = setup_driver(headless=True)
    if not driver:
        return 0 

    newly_scraped_count = 0
    processed_count = 0

    try:
        driver.get(target_url)
        print(f"已访问: {target_url}")

        # --- 2. 确保选中 "国内游戏" ---
        try:
            domestic_game_tab_xpath = "//div[contains(@class, 'type-rang-item') and contains(text(), '国内游戏')]"
            domestic_tab = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, domestic_game_tab_xpath))
            )
            # 检查是否已经激活
            if "active" not in domestic_tab.get_attribute('class').split():
                print("  未选中 '国内游戏', 正在点击...")
                domestic_tab.click()
                random_delay(1, 2) # 等待页面可能的变化
                print("  已点击 '国内游戏'.")
            else:
                print("  已选中 '国内游戏'.")
        except TimeoutException:
            print("错误: 找不到或无法点击 '国内游戏' 标签。")
            driver.quit()
            return 0
        except Exception as e:
            print(f"点击 '国内游戏' 时出错: {e}")
            driver.quit()
            return 0

        # --- 3. 等待游戏列表区域加载 --- 
        try:
            # 假设所有 date-item 的父容器有一个特定的 ID 或类，例如 'schedule-list' (需要验证或替换)
            # 或者直接等待第一个 date-item 出现
            content_container_selector = "div.date-item" # 等待第一个日期项目出现
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, content_container_selector)) 
            )
            print("页面主要内容 (日期项目) 加载完成。")
        except TimeoutException:
            print("等待页面主要内容超时或未找到元素。")
            # 即使超时也尝试继续，可能页面结构允许
        except Exception as e:
            print(f"等待页面元素时发生错误: {e}")
            driver.quit()
            return 0

        # --- 4. 定位并遍历所有日期区块 --- 
        daily_blocks = driver.find_elements(By.CSS_SELECTOR, "div.date-item")
        print(f"找到 {len(daily_blocks)} 个日期区块。开始处理...")

        if not daily_blocks:
            print("警告：未找到任何日期区块。")
            driver.quit()
            return 0
        
        # 5. 打开文件准备追加
        with open(output_path, 'a', encoding='utf-8') as outfile:
            for day_block in daily_blocks:
                # --- 提取日期 ---
                current_date_str = "未知日期"
                try:
                    date_element = day_block.find_element(By.CSS_SELECTOR, "div.date_panel span:first-child")
                    current_date_str = date_element.text.strip()
                    print(f"\n处理日期: {current_date_str} ---")
                except NoSuchElementException:
                    print("警告: 未能在此区块找到日期信息。")
                    continue # 跳过这个日期区块
                
                # --- 查找该日期下的所有游戏条目 ---
                game_elements = day_block.find_elements(By.CSS_SELECTOR, "div.game-items a.game-item")
                if not game_elements:
                    print(f"  日期 {current_date_str} 未找到游戏条目。")
                    continue
                
                print(f"  找到 {len(game_elements)} 个游戏条目。")
                
                for index, game_element in enumerate(game_elements):
                    processed_count += 1
                    print(f"  -- 检查条目 {index + 1}/{len(game_elements)} --")
                    
                    # --- 定义需要抓取的字段 ---
                    name, status, publisher, category = "未知名称", "未知状态", "未知厂商", "未知类型"
                    platform, description, icon_url, link = "未知平台", "", "", ""
                    # platform 默认为 国内游戏
                    platform = "国内游戏" 
                    
                    scrape_successful = False
                    item_data = {}
                    
                    try:
                        # --- 提取链接 ---
                        href = game_element.get_attribute('href')
                        if href:
                            link = urljoin(BASE_URL, href) # 合成完整 URL
                            print(f"    链接: {link}")
                            # --- 检查链接是否已存在 ---
                            if link in existing_links:
                                print(f"    链接 {link} 已存在于 {output_filename}，跳过。")
                                continue
                        else:
                            print("    警告: 未找到此条目的链接，跳过。")
                            continue
                        
                        # --- 提取图标 URL ---
                        try:
                            icon_element = game_element.find_element(By.CSS_SELECTOR, "div.left-section div.icon-panel")
                            style_attr = icon_element.get_attribute('style')
                            # 使用多种正则表达式匹配可能的URL格式
                            # 1. 尝试标准双引号格式
                            match = re.search(r'url\("(.*?)"\)', style_attr)
                            if not match:
                                # 2. 尝试单引号格式
                                match = re.search(r"url\('(.*?)'\)", style_attr)
                            if not match:
                                # 3. 尝试无引号格式
                                match = re.search(r'url\((.*?)\)', style_attr)
                            
                            if match:
                                icon_url = match.group(1)
                                # 确保URL是绝对URL
                                if icon_url.startswith('//'):
                                    icon_url = 'https:' + icon_url
                                elif not icon_url.startswith(('http://', 'https://')):
                                    icon_url = urljoin(BASE_URL, icon_url)
                                print(f"    图标 URL (来自 style): {icon_url}")
                            else:
                                # 备选方案：尝试从其他属性获取
                                data_src = icon_element.get_attribute('data-src')
                                if data_src:
                                    # 确保URL是绝对URL
                                    if data_src.startswith('//'):
                                        data_src = 'https:' + data_src
                                    elif not data_src.startswith(('http://', 'https://')):
                                        data_src = urljoin(BASE_URL, data_src)
                                    icon_url = data_src
                                    print(f"    图标 URL (来自 data-src): {icon_url}")
                                else:
                                    # 尝试获取background-image
                                    bg_image = icon_element.value_of_css_property('background-image')
                                    if bg_image and bg_image != 'none':
                                        match = re.search(r'url\("?(.*?)"?\)', bg_image)
                                        if match:
                                            bg_url = match.group(1)
                                            # 确保URL是绝对URL
                                            if bg_url.startswith('//'):
                                                bg_url = 'https:' + bg_url
                                            elif not bg_url.startswith(('http://', 'https://')):
                                                bg_url = urljoin(BASE_URL, bg_url)
                                            icon_url = bg_url
                                            print(f"    图标 URL (来自 CSS background-image): {icon_url}")
                                        else:
                                            print(f"    警告: 无法从 background-image 解析URL: {bg_image}")
                                    else:
                                        print("    警告: 未能解析图标 URL。")
                        except NoSuchElementException:
                            print("    警告: 未找到图标元素。")
                        except Exception as e:
                            print(f"    提取图标 URL 时出错: {e}")
                        
                        # --- 提取名称 ---
                        try:
                            name_element = game_element.find_element(By.CSS_SELECTOR, "div.right-section div.game-info-1 span")
                            name = name_element.text.strip()
                            print(f"    名称: {name}")
                        except NoSuchElementException:
                            print("    警告: 未找到名称元素。")
                        except Exception as e:
                            print(f"    提取名称时出错: {e}")
                            
                        # --- 提取发行/厂商 ---
                        try:
                            info2_element = game_element.find_element(By.CSS_SELECTOR, "div.right-section div.game-info-2")
                            info_text = info2_element.text.strip()
                            # 尝试按冒号分割
                            if ":" in info_text:
                                parts = info_text.split(':', 1) # 只分割一次
                                publisher_label = parts[0].strip()
                                publisher_value = parts[1].strip()
                                # 可以根据需要保留 label (发行/厂商)，这里只取值
                                publisher = publisher_value
                                print(f"    厂商/发行: {publisher} (原始文本: {info_text})")
                            else:
                                print(f"    警告: 未能解析厂商/发行信息: {info_text}")
                        except NoSuchElementException:
                            print("    警告: 未找到厂商/发行信息元素。")
                        except Exception as e:
                            print(f"    提取厂商/发行时出错: {e}")
                            
                        # --- 提取状态 ---
                        try:
                            status_element = game_element.find_element(By.CSS_SELECTOR, "div.right-section div.test_type span.test_type_tag")
                            status = status_element.text.strip()
                            print(f"    状态: {status}")
                        except NoSuchElementException:
                            print("    警告: 未找到状态元素。")
                        except Exception as e:
                            print(f"    提取状态时出错: {e}")
                        
                        # 平台和简介信息不在此处获取，保留默认值或空
                        # category 也不在此处获取
                        
                        scrape_successful = True
                        
                    except Exception as main_scrape_e:
                        print(f"    处理条目时发生错误: {main_scrape_e}")
                        scrape_successful = False
                    
                    # --- 写入文件 ---
                    if scrape_successful and link: # 确保链接有效
                        item_data = {
                            "name": name,
                            "platform": platform, # 默认为国内游戏
                            "status": status,
                            "publisher": publisher,
                            "category": category, # 保持未知
                            "description": description, # 保持空
                            "link": link,
                            "icon_url": icon_url,
                            "date": current_date_str, # 使用当前区块的日期
                            "source": "16p" 
                        }
                        try:
                            json.dump(item_data, outfile, ensure_ascii=False)
                            outfile.write('\n')
                            newly_scraped_count += 1
                            existing_links.add(link) 
                            print(f"    -> 成功保存条目 {name} 到 {output_filename}")
                        except Exception as write_e:
                            print(f"    写入条目 {name} 数据到文件时出错: {write_e}")
                    else:
                        print(f"    处理条目未成功或链接无效，未写入文件。")
            # 日期循环结束
            print("\n所有日期区块处理完毕。")

    except Exception as e:
        print(f"抓取过程中发生未预料的错误: {e}")
    finally:
        if driver:
            driver.quit()
            print("浏览器已关闭。")

    print(f"\n16p 页面 {target_url} 抓取完成。")
    print(f"总共处理 {processed_count} 个游戏条目。")
    print(f"本次运行新增 {newly_scraped_count} 条数据到 {output_filename}。")
    
    return newly_scraped_count

# --- 主程序入口 (用于测试) --- #
if __name__ == "__main__":
    test_url = "https://www.16p.com/newgame" # 目标 URL
    
    print(f"\n === 开始测试 16p 国内开测表抓取 ({test_url}) === \n")
    new_items_count = get_16p_data(test_url)
    print(f"\n === 测试完成 ({test_url}) === ")
    print(f"本次运行新增 {new_items_count} 条数据。")
    # 输出文件名在函数内部已打印