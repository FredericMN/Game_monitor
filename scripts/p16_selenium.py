# scripts/16p_selenium.py
# 用于抓取 16p 网站的开测表信息 (国内游戏) - 优化版

import os
import time
import random
import json
import re
import threading
from datetime import datetime
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains

# --- 常量定义 ---
# 保存结果的文件夹
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# 16p 基础 URL
BASE_URL = "https://www.16p.com"
DEFAULT_TARGET_URL = f"{BASE_URL}/newgame"

# 多线程配置
MAX_WORKERS = 3

# 文件写入锁
file_lock = threading.Lock()

# Base64 占位符图标模式
BASE64_PLACEHOLDER_PATTERN = re.compile(r'^data:image\/gif;base64,')

# --- 辅助函数 ---

def random_delay(min_sec=0.5, max_sec=1.5):
    """避免爬取过快"""
    time.sleep(random.uniform(min_sec, max_sec))

def setup_driver(headless=True):
    """配置并初始化 Edge 浏览器"""
    options = webdriver.EdgeOptions()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # 增加更常见的 User-Agent
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36 Edg/114.0.1823.58")
    # 禁用图片加载（可选，可以提高速度，但可能影响图标获取）
    # options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})

    try:
        # 尝试使用 WebDriver Manager 安装驱动
        service = EdgeService(EdgeChromiumDriverManager().install())
    except ValueError as e:
        print(f"WebDriver Manager 安装失败: {e}")
        # 如果安装失败，尝试使用系统路径下的驱动 (需要用户自行配置)
        # 例如: service = EdgeService(executable_path='path/to/your/msedgedriver.exe')
        # 如果没有备选方案，则退出
        print("请确保 Edge WebDriver 已安装或 WebDriver Manager 可以访问网络。")
        return None
    except Exception as e:
        print(f"WebDriver Manager 初始化时发生未知错误: {e}")
        return None

    try:
        driver = webdriver.Edge(service=service, options=options)
        # 设置隐式等待和页面加载超时
        driver.implicitly_wait(5) # 等待元素出现的最长时间
        driver.set_page_load_timeout(30) # 页面加载超时时间
        print("Edge WebDriver 初始化成功。")
        return driver
    except WebDriverException as e:
        print(f"初始化 Edge WebDriver 时出错: {e}")
        print("请检查 WebDriver 版本是否与 Edge 浏览器版本匹配。")
        return None
    except Exception as e:
        print(f"初始化 Edge WebDriver 时发生未知错误: {e}")
        return None


def load_existing_links(filepath):
    """从 JSONL 文件加载已存在的游戏详情页链接 (原始 16p 链接)"""
    original_links = set()
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        # 始终使用 original_link 进行去重检查
                        if 'original_link' in data and data['original_link']:
                            original_links.add(data['original_link'])
                    except json.JSONDecodeError:
                        print(f"警告: 无法解析行: {line.strip()}")
            print(f"从 {filepath} 加载了 {len(original_links)} 个已存在的原始链接。")
        except Exception as e:
            print(f"读取已存在链接文件时出错 ({filepath}): {e}")
    return original_links

def scroll_to_bottom(driver, max_attempts=5, scroll_pause_time=2):
    """滚动到页面底部以确保动态内容加载"""
    print("开始滚动页面以加载所有游戏条目...")
    last_height = driver.execute_script("return document.body.scrollHeight")
    attempts = 0
    while attempts < max_attempts:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(scroll_pause_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            attempts += 1
        else:
            attempts = 0 # 重置计数器
        last_height = new_height
        if attempts == 0:
            print(f"页面继续加载中，当前高度: {new_height}px")
        else:
             print(f"页面高度未变化，尝试 {attempts}/{max_attempts}")

    print("页面滚动完成。")


def clean_game_name(name):
    """清理游戏名称，移除可能的后缀"""
    if not name: return "未知名称"
    return name.split("-", 1)[0].strip() if "-" in name else name.strip()


def format_game_category(category_text):
    """格式化游戏类型文本"""
    if not category_text or category_text == "未知类型": return "未知类型"
    normalized = re.sub(r'[,，、/|]+', '/', category_text) # 统一分隔符
    categories = [cat.strip() for cat in normalized.split('/') if cat.strip()]
    if categories and any(keyword in categories[0] for keyword in ["近期", "热门", "期待"]):
        categories = categories[1:]
    return "/".join(categories[:3]) if categories else "未知类型"


def identify_source_from_url(url):
    """根据URL识别游戏来源平台"""
    if not url: return "16p", ""
    domain_map = {
        "taptap.cn": "TapTap", "taptap.com": "TapTap", "taptap.io": "TapTap",
        "3839.com": "好游快爆",
        "apple.com": "AppStore", "apps.apple": "AppStore",
        "appchina.com": "应用汇", "wandoujia.com": "豌豆荚",
        "huawei": "华为应用市场", "hicloud": "华为应用市场",
        "xiaomi": "小米应用商店", "mi.com": "小米应用商店",
        "vivo": "vivo应用商店",
        "oppo": "OPPO应用市场", "heytap": "OPPO应用市场",
        "qq.com": "应用宝", "myapp.com": "应用宝",
        "baidu": "百度手机助手", "meizu": "魅族应用商店",
        "lenovo": "联想应用商店", "anzhi": "安智市场"
    }
    for domain_key, source_name in domain_map.items():
        if domain_key in url:
            return source_name, url
    return "16p", url # 默认为 16p

def safe_get_attribute(element, attribute):
    """安全地获取元素属性，处理 StaleElementReferenceException"""
    try:
        return element.get_attribute(attribute)
    except:
        return None

def safe_find_element(driver_or_element, by, value):
    """安全地查找元素，返回 None 如果找不到"""
    try:
        return driver_or_element.find_element(by, value)
    except NoSuchElementException:
        return None

def safe_find_elements(driver_or_element, by, value):
    """安全地查找多个元素，返回空列表如果找不到"""
    try:
        return driver_or_element.find_elements(by, value)
    except NoSuchElementException:
        return []

def extract_url_from_style(style_string):
    """从 style 属性的 background-image 中提取 URL"""
    if not style_string:
        return None
    match = re.search(r'url\("?(.+?)"?\)', style_string)
    return match.group(1) if match else None

def get_icon_from_list_item(game_element):
    """从列表页的游戏条目中尝试提取图标 URL"""
    try:
        # 优先尝试 div.icon-panel 的 data-src
        icon_panel = safe_find_element(game_element, By.CSS_SELECTOR, "div.icon-panel")
        if icon_panel:
            data_src = safe_get_attribute(icon_panel, 'data-src')
            if data_src:
                return urljoin(BASE_URL, data_src)

            # 其次尝试 style 的 background-image
            style = safe_get_attribute(icon_panel, 'style')
            bg_url = extract_url_from_style(style)
            if bg_url:
                return urljoin(BASE_URL, bg_url)

        # 如果 icon-panel 失败，尝试 div.left-section img 的 src
        img_element = safe_find_element(game_element, By.CSS_SELECTOR, "div.left-section img")
        if img_element:
            src = safe_get_attribute(img_element, 'src')
            if src and not BASE64_PLACEHOLDER_PATTERN.match(src): # 排除base64占位符
                 return urljoin(BASE_URL, src)
            data_src = safe_get_attribute(img_element, 'data-src')
            if data_src:
                 return urljoin(BASE_URL, data_src)

    except Exception as e:
        print(f"    提取列表页图标时出错: {e}")
    return None


def click_expand_buttons(driver):
    """尝试点击页面上所有可能的"展开"按钮"""
    clicked_count = 0
    selectors = [
        "//*[contains(text(), '展开') or contains(text(), '更多')]", # 基于文本
        ".readmore-toggle", ".read-more", ".more-icon", ".expand-button", # 基于类名
        "svg.fa-angles-down", "svg.more-icon", "[class*='arrow']", "[class*='expand']" # 基于图标/类名
    ]

    for selector in selectors:
        try:
            elements = safe_find_elements(driver, By.XPATH if selector.startswith("//") else By.CSS_SELECTOR, selector)
            for elem in elements:
                if elem.is_displayed():
                    try:
                        # 滚动到元素中心
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", elem)
                        time.sleep(0.3) # 短暂等待滚动完成

                        # 优先尝试 JS 点击
                        driver.execute_script("arguments[0].click();", elem)
                        print(f"  尝试通过 JS 点击展开元素: {selector}")
                        clicked_count += 1
                        time.sleep(0.8) # 等待动画

                    except Exception as click_e1:
                        try:
                             # 尝试 ActionChains 点击
                             action = ActionChains(driver)
                             action.move_to_element(elem).pause(0.2).click().perform()
                             print(f"  尝试通过 ActionChains 点击展开元素: {selector}")
                             clicked_count += 1
                             time.sleep(0.8)
                        except Exception as click_e2:
                             print(f"    点击展开元素 {selector} 失败: {click_e1} / {click_e2}")
        except Exception as find_e:
             print(f"  查找展开元素 {selector} 时出错: {find_e}")

    if clicked_count > 0:
        print(f"  共尝试点击了 {clicked_count} 个展开元素。")
    else:
        print(f"  未找到或未能点击展开元素。")


def get_game_details(driver, game_url, list_page_icon_url=None):
    """
    访问游戏详情页并获取额外信息 (优化版)
    返回: description, category, rating, external_link, source, icon_url
    """
    description, category, rating = "", "未知类型", "未知评分"
    external_link, source, icon_url = "", "16p", ""
    max_icon_retries = 2
    icon_retry_delay = 1 # 秒

    original_window = driver.current_window_handle
    new_window_handle = None

    try:
        # 打开新标签页
        driver.execute_script("window.open(arguments[0], '_blank');", game_url)
        WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(len(driver.window_handles))) # 等待窗口数量增加

        # 切换到新窗口
        for handle in driver.window_handles:
            if handle != original_window:
                new_window_handle = handle
                driver.switch_to.window(new_window_handle)
                break

        if not new_window_handle:
            print("  错误: 未能打开或切换到新窗口")
            return description, category, rating, external_link, source, list_page_icon_url # 返回列表页获取的图标

        # 等待关键元素加载
        WebDriverWait(driver, 15).until(
             EC.any_of(
                 EC.presence_of_element_located((By.CSS_SELECTOR, "div.icon img, div.gameimg img, .van-image__img")), # 图标区域
                 EC.presence_of_element_located((By.CSS_SELECTOR, "h1.game_detail_name")), # 游戏名称
                 EC.presence_of_element_located((By.CSS_SELECTOR, "div#gamedescription")) # 描述区域
             )
        )
        print(f"  详情页已加载: {driver.current_url}")
        random_delay(0.5, 1) # 加载后稍作等待

        # --- 获取图标 (带重试机制) ---
        for attempt in range(max_icon_retries + 1):
            icon_selectors = [
                "div.icon img", "div.gameimg img",
                "div.icon .van-image__img", ".gameimg .van-image__img",
                 ".game-icon img", ".app-icon img" # 更多可能的选择器
            ]
            for selector in icon_selectors:
                icon_elements = safe_find_elements(driver, By.CSS_SELECTOR, selector)
                if icon_elements:
                    for img in icon_elements:
                        img_url = safe_get_attribute(img, 'src') or safe_get_attribute(img, 'data-src')
                        if img_url and not BASE64_PLACEHOLDER_PATTERN.match(img_url):
                            icon_url = urljoin(BASE_URL, img_url)
                            print(f"  获取到详情页图标URL (尝试 {attempt+1}): {icon_url}")
                            break # 找到有效图标，跳出内层循环
                    if icon_url: break # 找到有效图标，跳出外层循环
            if icon_url: break # 找到有效图标，结束重试

            if attempt < max_icon_retries:
                print(f"  未找到有效图标或为占位符，尝试刷新或等待 ({attempt+1}/{max_icon_retries})")
                # 可以在这里尝试刷新页面，但可能不稳定，先用延时
                time.sleep(icon_retry_delay)
                # driver.refresh() # 刷新页面 (可选，可能导致状态丢失)
                # WebDriverWait(driver, 15).until(...) # 刷新后需要重新等待加载
            else:
                print(f"  尝试 {max_icon_retries+1} 次后仍未获取详情页有效图标。")
                if list_page_icon_url:
                    icon_url = list_page_icon_url
                    print(f"  使用列表页获取的图标: {icon_url}")
                else:
                    print("  列表页也无图标，图标获取失败。")


        # --- 获取外部平台链接 ---
        platform_link_selectors = [
            "div[style*='display: flex; margin: 8px 0px'] a[target='_blank']", # 特定样式
            "a[href*='taptap']", "a[href*='3839.com']", "a[href*='apple.com']", # 按域名
            ".platform-link a", ".download-link a" # 按类名
        ]
        found_links = []
        for selector in platform_link_selectors:
             links = safe_find_elements(driver, By.CSS_SELECTOR, selector)
             for link_elem in links:
                 href = safe_get_attribute(link_elem, 'href')
                 if href:
                      src, url = identify_source_from_url(href)
                      if src != "16p": # 只保留非16p的外部链接
                          found_links.append({'source': src, 'url': url})

        if found_links:
            # 优先选择 TapTap 或 好游快爆
            preferred_link = next((link for link in found_links if link['source'] == 'TapTap'), None)
            if not preferred_link:
                preferred_link = next((link for link in found_links if link['source'] == '好游快爆'), None)
            # 否则选择第一个找到的外部链接
            if not preferred_link:
                preferred_link = found_links[0]

            source = preferred_link['source']
            external_link = preferred_link['url']
            print(f"  获取到外部平台链接: {source} - {external_link}")


        # --- 展开内容 ---
        click_expand_buttons(driver)
        time.sleep(1) # 等待内容展开

        # --- 获取游戏简介 ---
        desc_selectors = [
            "div#gamedescription div.read-more-content",
            "div.game-desc-content",
            "div.description-content"
        ]
        for selector in desc_selectors:
             desc_element = safe_find_element(driver, By.CSS_SELECTOR, selector)
             if desc_element:
                  desc_text = desc_element.text.strip()
                  if desc_text:
                      description = desc_text
                      print(f"  获取到简介 (选择器: {selector}): {description[:50]}...")
                      break
        if not description:
             print("  警告: 未找到游戏简介。")


        # --- 获取游戏类型 ---
        category_found = False
        # 尝试多种方法获取类型
        # 方法1: 精确 XPath
        precise_type_cells = safe_find_elements(driver, By.XPATH, "//th[normalize-space(.)='游戏类型' or normalize-space(.)='类别']/following-sibling::td[1]")
        if precise_type_cells:
            category_text = precise_type_cells[0].text.strip()
            if category_text:
                category = format_game_category(category_text)
                print(f"  获取到类型 (精确XPath): {category} (原始: {category_text})")
                category_found = True

        # 方法2: JS 查找 (如果XPath失败)
        if not category_found:
            js_script = """
                const labels = ['游戏类型', '类别'];
                for (const label of labels) {
                    const th = Array.from(document.querySelectorAll('th')).find(el => el.textContent.trim().includes(label));
                    if (th) {
                        const td = th.nextElementSibling;
                        if (td && td.tagName === 'TD') return td.textContent.trim();
                        // 备用：查找父行中的 td
                         const parentRow = th.closest('tr');
                         if(parentRow) {
                             const dataCell = parentRow.querySelector('td');
                             if(dataCell) return dataCell.textContent.trim();
                         }
                    }
                     // 查找非表格格式
                     const labelElem = Array.from(document.querySelectorAll('div, span, dt')).find(el => el.textContent.trim().startsWith(label));
                     if(labelElem){
                         let valueElem = labelElem.nextElementSibling || (labelElem.parentElement ? labelElem.parentElement.querySelector('dd, .value') : null);
                         if(valueElem) return valueElem.textContent.trim();
                     }
                }
                return null;
            """
            category_text = driver.execute_script(js_script)
            if category_text:
                category = format_game_category(category_text)
                print(f"  获取到类型 (JS): {category} (原始: {category_text})")
                category_found = True

        if not category_found: print("  警告: 未找到游戏类型。")


        # --- 获取游戏评分 ---
        rating_selectors = [
            "div.review_num span", # 原始
            "div.score-num", "span.score-text", "div.game-score", # 备选
            ".rating-value", ".score"
        ]
        rating_found = False
        for selector in rating_selectors:
            rating_elements = safe_find_elements(driver, By.CSS_SELECTOR, selector)
            for elem in rating_elements:
                 rating_text = elem.text.strip()
                 # 验证是否像评分数字
                 if rating_text and re.match(r'^\d+(\.\d+)?$', rating_text):
                     rating = rating_text
                     print(f"  获取到评分 (选择器: {selector}): {rating}")
                     rating_found = True
                     break
            if rating_found: break

        if not rating_found: print("  警告: 未找到游戏评分。")


    except TimeoutException:
         print(f"  访问或等待详情页超时: {game_url}")
         # 超时也尝试使用列表页图标
         if list_page_icon_url: icon_url = list_page_icon_url
    except Exception as e:
        print(f"  访问详情页时发生错误: {e}")
        # 出错时尝试使用列表页图标
        if list_page_icon_url: icon_url = list_page_icon_url
    finally:
        # 关闭新窗口并切回
        if new_window_handle and new_window_handle in driver.window_handles:
            try:
                driver.close()
            except Exception as close_err:
                print(f"  关闭新窗口时出错: {close_err}")
        try:
            driver.switch_to.window(original_window)
        except Exception as switch_err:
             print(f"  切换回原始窗口时出错: {switch_err}")

    return description, category, rating, external_link, source, icon_url


def process_game_item(original_16p_link, basic_info, list_page_icon_url, output_path, existing_original_links):
    """
    单个游戏条目的处理函数（在线程中运行）
    返回: 成功处理的数据字典或 None
    """
    thread_id = threading.get_ident()
    print(f"[线程 {thread_id}] 开始处理: {original_16p_link}")

    driver = None
    item_data = None
    try:
        # 每个线程创建自己的 WebDriver 实例
        driver = setup_driver(headless=True)
        if not driver:
            print(f"[线程 {thread_id}] WebDriver 初始化失败，跳过 {original_16p_link}")
            return None

        # 访问详情页获取详细信息
        description, category, rating, external_link, source, detail_icon_url = get_game_details(driver, original_16p_link, list_page_icon_url)

        # 决定最终链接和来源
        final_link = external_link if external_link else original_16p_link
        final_source = source # get_game_details 会更新来源

        # 决定最终图标 URL
        final_icon_url = detail_icon_url # 优先详情页获取的（已包含列表页的回退逻辑）

        item_data = {
            "name": basic_info.get("name", "未知名称"),
            "platform": basic_info.get("platform", "国内游戏"),
            "status": basic_info.get("status", "未知状态"),
            "publisher": basic_info.get("publisher", "未知厂商"),
            "category": category,
            "rating": rating,
            "description": description,
            "link": final_link,
            "original_link": original_16p_link,
            "icon_url": final_icon_url if final_icon_url else "", # 确保为空字符串而非 None
            "date": basic_info.get("date", "未知日期"),
            "source": final_source
        }

        # 在写入前最后检查一次是否已存在（理论上主线程已过滤，但多一层保险）
        # 注意：这里的 existing_original_links 是主线程传过来的副本，可能不是最新的，
        # 但主线程的过滤已经足够。这里主要是为了逻辑完整。
        if original_16p_link in existing_original_links:
             print(f"[线程 {thread_id}] 链接 {original_16p_link} 在处理过程中发现已存在，取消写入。")
             return None

        # 写入文件（加锁）
        with file_lock:
            try:
                with open(output_path, 'a', encoding='utf-8') as outfile:
                    json.dump(item_data, outfile, ensure_ascii=False)
                    outfile.write('\n')
                print(f"[线程 {thread_id}] -> 成功保存条目 {item_data['name']} 到 {os.path.basename(output_path)} (来源: {final_source})")
                # 返回数据以便主线程更新计数和集合
                return item_data
            except Exception as write_e:
                print(f"[线程 {thread_id}] 写入条目 {item_data['name']} 数据到文件时出错: {write_e}")
                return None # 写入失败

    except Exception as e:
        print(f"[线程 {thread_id}] 处理条目 {original_16p_link} 时发生错误: {e}")
        return None # 处理失败
    finally:
        if driver:
            try:
                driver.quit()
                # print(f"[线程 {thread_id}] WebDriver 已关闭。")
            except Exception as quit_e:
                print(f"[线程 {thread_id}] 关闭 WebDriver 时出错: {quit_e}")


def get_16p_data(target_url=DEFAULT_TARGET_URL):
    """
    获取指定 URL (16p 开测表) 的国内游戏信息 (多线程优化版)。
    """
    print(f"开始抓取 16p 页面 {target_url} 的国内游戏信息 (多线程模式, Max Workers: {MAX_WORKERS})...")
    output_filename = f'p16_games_{datetime.now().strftime("%Y%m%d_%H%M%S")}.jsonl' # Consistent prefix
    output_path = os.path.join(DATA_DIR, output_filename)

    # 1. 加载已存在的原始链接用于去重
    existing_original_links = load_existing_links(output_path)

    main_driver = setup_driver(headless=True)
    if not main_driver:
        print("主 WebDriver 初始化失败，无法继续。")
        return 0

    tasks_submitted = 0
    items_to_process = []

    try:
        main_driver.get(target_url)
        print(f"已访问: {target_url}")

        # 2. 确保选中 "国内游戏"
        try:
            domestic_game_tab_xpath = "//div[contains(@class, 'type-rang-item') and contains(text(), '国内游戏')]"
            domestic_tab = WebDriverWait(main_driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, domestic_game_tab_xpath))
            )
            if "active" not in domestic_tab.get_attribute('class'):
                print("  未选中 '国内游戏', 正在点击...")
                domestic_tab.click()
                random_delay(1.5, 2.5) # 点击后等待加载
                print("  已点击 '国内游戏'.")
            else:
                print("  已选中 '国内游戏'.")
        except Exception as e:
            print(f"选择 '国内游戏' 标签时出错: {e}")
            return 0 # 关键步骤失败，退出

        # 3. 等待并滚动页面
        try:
            WebDriverWait(main_driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.date-item"))
            )
            print("页面主要内容加载完成。")
            scroll_to_bottom(main_driver)
        except Exception as e:
            print(f"等待或滚动页面时出错: {e}")
            # 尝试继续

        # 4. 遍历日期区块，收集待处理任务
        daily_blocks = safe_find_elements(main_driver, By.CSS_SELECTOR, "div.date-item")
        print(f"找到 {len(daily_blocks)} 个日期区块。开始收集任务...")

        if not daily_blocks:
            print("警告：未找到任何日期区块。")
            return 0

        for day_block in daily_blocks:
            current_date_str = "未知日期"
            try:
                date_element = safe_find_element(day_block, By.CSS_SELECTOR, "div.date_panel span:first-child")
                if date_element: current_date_str = date_element.text.strip()
                print(f"\n处理日期: {current_date_str} ---")
            except Exception as e:
                print(f"  提取日期时出错: {e}")

            game_elements = safe_find_elements(day_block, By.CSS_SELECTOR, "div.game-items a.game-item")
            if not game_elements:
                print(f"  日期 {current_date_str} 未找到游戏条目。")
                continue

            print(f"  找到 {len(game_elements)} 个游戏条目。")

            for index, game_element in enumerate(game_elements):
                original_16p_link = None
                basic_info = {"platform": "国内游戏", "date": current_date_str}
                list_page_icon_url = None

                try:
                    # 提取原始链接
                    href = safe_get_attribute(game_element, 'href')
                    if href:
                        original_16p_link = urljoin(BASE_URL, href)
                    else:
                        print(f"    警告: 条目 {index + 1} 未找到链接，跳过。")
                        continue

                    # --- 检查链接是否已存在 ---
                    if original_16p_link in existing_original_links:
                        # print(f"    链接 {original_16p_link} 已存在，跳过。")
                        continue

                    # --- 提取列表页信息 ---
                    # 名称
                    name_element = safe_find_element(game_element, By.CSS_SELECTOR, "div.right-section div.game-info-1 span")
                    if name_element:
                         raw_name = name_element.text.strip()
                         basic_info["name"] = clean_game_name(raw_name)

                    # 厂商/发行
                    info2_element = safe_find_element(game_element, By.CSS_SELECTOR, "div.right-section div.game-info-2")
                    if info2_element:
                        info_text = info2_element.text.strip()
                        if ":" in info_text:
                             basic_info["publisher"] = info_text.split(':', 1)[1].strip()
                        elif "厂商：" in info_text: # 兼容中文冒号
                             basic_info["publisher"] = info_text.split('厂商：', 1)[1].strip()


                    # 状态
                    status_element = safe_find_element(game_element, By.CSS_SELECTOR, "div.right-section div.test_type span.test_type_tag")
                    if status_element:
                        basic_info["status"] = status_element.text.strip()

                    # 尝试提取列表页图标
                    list_page_icon_url = get_icon_from_list_item(game_element)
                    # print(f"    列表页图标: {list_page_icon_url}") # 调试用

                    # 添加到待处理列表
                    items_to_process.append({
                        "link": original_16p_link,
                        "basic_info": basic_info,
                        "icon": list_page_icon_url
                    })
                    tasks_submitted += 1

                except Exception as e:
                    print(f"    提取条目 {index + 1} 基本信息时出错: {e}")

        print(f"\n任务收集完毕，共找到 {tasks_submitted} 个新游戏条目待处理。")

    except Exception as e:
        print(f"主流程发生错误: {e}")
        return 0 # 主流程错误，直接返回
    finally:
        if main_driver:
            main_driver.quit()
            print("主浏览器已关闭。")

    # --- 5. 使用线程池处理任务 ---
    newly_scraped_count = 0
    if not items_to_process:
        print("没有新的游戏条目需要处理。")
        return 0

    # 将最新的已存在链接集合传递给工作线程
    current_existing_links = existing_original_links.copy()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 提交所有任务
        future_to_item = {
            executor.submit(process_game_item, item["link"], item["basic_info"], item["icon"], output_path, current_existing_links): item["link"]
            for item in items_to_process
        }

        processed_count = 0
        total_tasks = len(future_to_item)
        print(f"开始使用 {MAX_WORKERS} 个线程处理 {total_tasks} 个任务...")

        for future in as_completed(future_to_item):
            original_link = future_to_item[future]
            processed_count += 1
            try:
                result_data = future.result() # 获取线程返回的数据
                if result_data:
                    newly_scraped_count += 1
                    # 注意：这里不再需要更新 existing_original_links，因为写入已在线程内完成
                    # 如果需要实时更新主线程的集合，需要更复杂的线程安全机制
                # 打印进度
                if processed_count % 10 == 0 or processed_count == total_tasks:
                     print(f"  处理进度: {processed_count}/{total_tasks} (新增: {newly_scraped_count})")

            except Exception as exc:
                print(f"  处理链接 {original_link} 时线程产生异常: {exc}")

    print(f"\n16p 页面 {target_url} 抓取完成。")
    print(f"总共提交 {tasks_submitted} 个新游戏条目进行处理。")
    print(f"本次运行成功新增 {newly_scraped_count} 条数据到 {output_filename}。")

    return newly_scraped_count


# --- 主程序入口 ---
if __name__ == "__main__":
    start_time = time.time()
    print(f"\n === 开始 16p 国内开测表抓取 ({DEFAULT_TARGET_URL}) === \n")
    new_items_count = get_16p_data(DEFAULT_TARGET_URL)
    end_time = time.time()
    print(f"\n === 抓取完成 ({DEFAULT_TARGET_URL}) === ")
    print(f"本次运行新增 {new_items_count} 条数据。")
    print(f"总耗时: {end_time - start_time:.2f} 秒。")