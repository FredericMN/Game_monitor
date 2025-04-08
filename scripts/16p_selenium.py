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
from selenium.webdriver.common.action_chains import ActionChains # 用于滚动

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
    original_links = set()  # 新增：用于存储原始16p链接
    
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        data = json.loads(line.strip())
                        if 'link' in data and data['link']:
                            existing_links.add(data['link'])
                        # 加载原始16p链接（如果存在）
                        if 'original_link' in data and data['original_link']:
                            original_links.add(data['original_link'])
                    except json.JSONDecodeError:
                        print(f"警告: 无法解析行: {line.strip()}")
            print(f"从 {filepath} 加载了 {len(existing_links)} 个已存在的链接和 {len(original_links)} 个原始链接。")
        except Exception as e:
            print(f"读取已存在链接文件时出错 ({filepath}): {e}")
    
    # 返回两个集合
    return existing_links, original_links

def scroll_to_bottom(driver, max_attempts=5, scroll_pause_time=2):
    """
    滚动到页面底部以确保动态内容加载
    """
    print("开始滚动页面以加载所有游戏条目...")
    
    # 获取当前滚动位置
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    attempts = 0
    while attempts < max_attempts:
        # 滚动到底部
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # 等待页面加载
        time.sleep(scroll_pause_time)
        
        # 计算新的滚动高度并与上一个滚动高度进行比较
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            attempts += 1
            print(f"页面高度未变化，尝试 {attempts}/{max_attempts}")
        else:
            # 重置尝试计数器，因为页面仍在加载
            attempts = 0
            print(f"页面继续加载中，当前高度: {new_height}px")
        
        last_height = new_height
    
    print("页面滚动完成，所有内容应已加载。")

def clean_game_name(name):
    """
    清理游戏名称，移除可能的后缀
    例如："游戏名称-xxxx" 将变为 "游戏名称"
    """
    if not name:
        return "未知名称"
    
    # 检查并移除 "-" 后面的内容
    if "-" in name:
        parts = name.split("-", 1)
        return parts[0].strip()
    
    return name.strip()

def format_game_category(category_text):
    """
    格式化游戏类型文本:
    1. 将分隔符统一为"/"
    2. 排除首个游戏类型字段中带有"近期"的情况
    3. 只保留前三个字段
    
    例如:
    "国风,放置,角色扮演" -> "国风/放置/角色扮演"
    "近期热门,动作,冒险,策略" -> "动作/冒险/策略"
    "近期期待,策略" -> "策略"
    """
    if not category_text or category_text == "未知类型":
        return "未知类型"
    
    # 替换常见的分隔符为统一格式，支持中英文逗号、顿号、空格、斜杠等
    normalized = re.sub(r'[,，、 |]+', ',', category_text)
    categories = normalized.split(',')
    
    # 过滤掉空白项
    categories = [cat.strip() for cat in categories if cat.strip()]
    
    # 检查首个类型是否包含"近期"，如果是则排除
    if categories and any(keyword in categories[0] for keyword in ["近期", "热门", "期待"]):
        categories = categories[1:]
    
    # 只保留前三个类型
    categories = categories[:3]
    
    # 使用/连接并返回
    return "/".join(categories) if categories else "未知类型"

def identify_source_from_url(url):
    """
    根据URL识别游戏来源平台
    返回: (source_name, formatted_url)
    """
    if not url:
        return "16p", ""
        
    # 识别主要平台
    if "taptap.cn" in url or "taptap.com" in url or "taptap.io" in url:
        return "TapTap", url
    elif "3839.com" in url:
        return "好游快爆", url
    elif "apple.com" in url or "apps.apple" in url:
        return "AppStore", url
    elif "appchina.com" in url:
        return "应用汇", url
    elif "wandoujia.com" in url:
        return "豌豆荚", url
    elif "huawei" in url or "hicloud" in url:
        return "华为应用市场", url
    elif "xiaomi" in url or "mi.com" in url:
        return "小米应用商店", url
    elif "vivo" in url:
        return "vivo应用商店", url
    elif "oppo" in url or "heytap" in url:
        return "OPPO应用市场", url
    elif "qq.com" in url or "myapp.com" in url:
        return "应用宝", url
    elif "baidu" in url:
        return "百度手机助手", url
    elif "meizu" in url:
        return "魅族应用商店", url
    elif "lenovo" in url:
        return "联想应用商店", url
    elif "anzhi" in url:
        return "安智市场", url
    
    # 默认返回16p作为来源
    return "16p", url

def get_game_details(driver, game_url):
    """
    访问游戏详情页并获取额外信息
    返回: description, category, rating, external_link, source, icon_url
    """
    description = ""
    category = "未知类型"
    rating = "未知评分"
    external_link = ""  # 外部平台链接
    source = "16p"      # 来源平台，默认为16p
    icon_url = ""       # 游戏图标URL
    
    try:
        original_window = driver.current_window_handle
        
        # 打开新标签页
        driver.execute_script("window.open(arguments[0]);", game_url)
        
        # 等待新窗口打开
        WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
        
        # 切换到新窗口
        for window_handle in driver.window_handles:
            if window_handle != original_window:
                driver.switch_to.window(window_handle)
                break
        
        # 等待详情页加载
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[id='gamedescription'], h1.game_detail_name"))
        )
        print(f"  详情页已加载: {driver.current_url}")
        
        # ----- 获取游戏图标 -----
        try:
            # 方法1: 查找符合用户提供的图标元素
            icon_selectors = [
                "div.icon img", 
                "div.gameimg img",
                "div.van-image img",
                "div.icon .van-image__img",
                ".gameimg .van-image__img"
            ]
            
            for selector in icon_selectors:
                try:
                    icon_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if icon_elements:
                        for img in icon_elements:
                            # 首先尝试获取src属性
                            img_url = img.get_attribute('src')
                            if not img_url or img_url == "":
                                # 如果src为空，尝试data-src属性
                                img_url = img.get_attribute('data-src')
                            
                            if img_url and img_url != "":
                                # 确保URL为完整路径
                                if img_url.startswith('//'):
                                    img_url = 'https:' + img_url
                                elif not img_url.startswith(('http://', 'https://')):
                                    img_url = urljoin(BASE_URL, img_url)
                                
                                icon_url = img_url
                                print(f"  获取到游戏图标URL: {icon_url}")
                                break
                        
                        if icon_url:  # 如果找到了图标URL，跳出选择器循环
                            break
                except Exception as se:
                    print(f"  使用选择器 '{selector}' 查找图标时出错: {se}")
            
            # 方法2: 使用更通用的选择器查找可能的游戏图标
            if not icon_url:
                try:
                    # 查找页面上所有图片元素
                    all_images = driver.find_elements(By.TAG_NAME, "img")
                    
                    # 过滤掉小图标和广告图片，保留可能的游戏图标
                    for img in all_images:
                        try:
                            # 检查图片尺寸，忽略太小的图片
                            width = img.get_attribute("width")
                            height = img.get_attribute("height")
                            
                            # 检查图片类名，找出可能的游戏图标
                            class_name = img.get_attribute("class") or ""
                            
                            # 检查图片URL，查找包含特定关键词的URL
                            img_url = img.get_attribute('src') or img.get_attribute('data-src')
                            
                            if img_url and (
                                ("icon" in img_url.lower() or "logo" in img_url.lower() or "game" in img_url.lower()) or
                                ("icon" in class_name.lower() or "logo" in class_name.lower() or "game" in class_name.lower()) or
                                (width and height and int(width) >= 60 and int(height) >= 60)
                            ):
                                # 确保URL为完整路径
                                if img_url.startswith('//'):
                                    img_url = 'https:' + img_url
                                elif not img_url.startswith(('http://', 'https://')):
                                    img_url = urljoin(BASE_URL, img_url)
                                
                                icon_url = img_url
                                print(f"  通过通用方法获取到游戏图标URL: {icon_url}")
                                break
                        except Exception:
                            continue
                except Exception as ge:
                    print(f"  通用方法查找图标时出错: {ge}")
                    
        except Exception as icon_e:
            print(f"  获取游戏图标时出错: {icon_e}")
        
        # ----- 查找外部平台链接 -----
        try:
            # 方法1: 寻找带有外部链接的div元素
            platform_links = []
            
            # 查找包含平台图标和链接的div元素 (基于用户提供的案例)
            link_containers = driver.find_elements(By.CSS_SELECTOR, "div[style*='display: flex; margin: 8px 0px'] a[target='_blank']")
            if link_containers:
                print(f"  找到 {len(link_containers)} 个可能的外部平台链接")
                
                for link_elem in link_containers:
                    try:
                        href = link_elem.get_attribute('href')
                        if href:
                            # 获取链接内部的平台名称文本
                            platform_text = ""
                            try:
                                platform_span = link_elem.find_element(By.CSS_SELECTOR, "span.plat-title")
                                platform_text = platform_span.text.strip()
                            except:
                                pass
                                
                            # 保存链接信息
                            platform_links.append({
                                'url': href,
                                'text': platform_text
                            })
                            print(f"  发现外部平台链接: {platform_text} - {href}")
                    except Exception as le:
                        print(f"  提取链接信息时出错: {le}")
                
                # 确定要使用的平台链接（优先选择TapTap或好游快爆）
                if platform_links:
                    # 首先查找是否有TapTap链接
                    taptap_links = [link for link in platform_links if 'taptap' in link['url'].lower()]
                    if taptap_links:
                        selected_link = taptap_links[0]['url']
                        source, external_link = identify_source_from_url(selected_link)
                        print(f"  选择使用TapTap链接: {external_link}")
                    else:
                        # 其次查找是否有好游快爆链接
                        kybao_links = [link for link in platform_links if '3839.com' in link['url'].lower()]
                        if kybao_links:
                            selected_link = kybao_links[0]['url']
                            source, external_link = identify_source_from_url(selected_link)
                            print(f"  选择使用好游快爆链接: {external_link}")
                        else:
                            # 否则使用第一个有效链接
                            selected_link = platform_links[0]['url']
                            source, external_link = identify_source_from_url(selected_link)
                            print(f"  选择使用其他平台链接: {external_link}")
            
            # 方法2：通用方法查找所有外部链接
            if not external_link:
                # 使用更通用的选择器查找可能的外部链接
                all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='taptap'], a[href*='3839.com'], a[href*='apple.com']")
                platform_links = []
                
                for link in all_links:
                    try:
                        href = link.get_attribute('href')
                        if href and ('taptap' in href or '3839.com' in href or 'apple.com' in href):
                            platform_links.append({
                                'url': href,
                                'text': link.text.strip()
                            })
                    except:
                        continue
                
                if platform_links:
                    # 优先选择TapTap或好游快爆
                    taptap_links = [link for link in platform_links if 'taptap' in link['url'].lower()]
                    if taptap_links:
                        selected_link = taptap_links[0]['url']
                        source, external_link = identify_source_from_url(selected_link)
                        print(f"  通过通用方法找到TapTap链接: {external_link}")
                    else:
                        kybao_links = [link for link in platform_links if '3839.com' in link['url'].lower()]
                        if kybao_links:
                            selected_link = kybao_links[0]['url']
                            source, external_link = identify_source_from_url(selected_link)
                            print(f"  通过通用方法找到好游快爆链接: {external_link}")
                        else:
                            # 使用第一个找到的链接
                            selected_link = platform_links[0]['url']
                            source, external_link = identify_source_from_url(selected_link)
                            print(f"  通过通用方法找到其他平台链接: {external_link}")
                
        except Exception as plink_e:
            print(f"  尝试提取外部平台链接时出错 (非致命): {plink_e}")
        
        # ----- 改进的展开折叠内容方法 -----
        try:
            # 方法1: 尝试直接修改DOM，强制展开所有折叠内容
            expand_script = """
                // 移除高度限制
                var collapsedElements = document.querySelectorAll('.read-more-content, [style*="height"], [style*="overflow: hidden"]');
                for (var i = 0; i < collapsedElements.length; i++) {
                    var elem = collapsedElements[i];
                    if (elem.style.height && elem.style.height !== 'auto') {
                        elem.style.height = 'auto';
                    }
                    if (elem.style.overflow === 'hidden') {
                        elem.style.overflow = 'visible';
                    }
                    // 移除可能的maxHeight限制
                    elem.style.maxHeight = 'none';
                }
                
                // 隐藏所有展开按钮
                var expandButtons = document.querySelectorAll('.readmore-toggle, .read-more, .more-icon, .expand-button');
                for (var j = 0; j < expandButtons.length; j++) {
                    expandButtons[j].style.display = 'none';
                }
                
                // 返回是否有任何修改
                return {
                    modified: collapsedElements.length > 0 || expandButtons.length > 0,
                    collapsedCount: collapsedElements.length,
                    buttonCount: expandButtons.length
                };
            """
            result = driver.execute_script(expand_script)
            if result.get('modified', False):
                print(f"  通过DOM修改展开了内容 (修改了{result.get('collapsedCount', 0)}个元素, 隐藏了{result.get('buttonCount', 0)}个按钮)")
                time.sleep(1) # 给DOM变化一点时间
            
            # 方法2: 尝试查找可点击的展开元素并点击
            # 查找包含特定文本或图标的按钮/元素
            expand_elements = driver.find_elements(By.XPATH, 
                "//*[contains(text(), '展开') or contains(text(), '更多') or contains(@class, 'more')]")
            
            for elem in expand_elements:
                if elem.is_displayed():
                    try:
                        print(f"  尝试点击展开元素: {elem.tag_name}.{elem.get_attribute('class')}")
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                        time.sleep(0.5)
                        
                        # 尝试使用多种方式点击
                        try:
                            # 1. 常规点击
                            elem.click()
                            print("  成功通过常规点击展开内容")
                        except Exception:
                            try:
                                # 2. JavaScript点击
                                driver.execute_script("arguments[0].click();", elem)
                                print("  成功通过JavaScript点击展开内容")
                            except Exception:
                                # 3. 模拟鼠标事件
                                action = ActionChains(driver)
                                action.move_to_element(elem).click().perform()
                                print("  成功通过ActionChains点击展开内容")
                        
                        time.sleep(1) # 等待展开动画完成
                    except Exception as click_e:
                        print(f"  尝试点击展开元素时出错: {click_e}")
            
            # 方法3: 尝试查找SVG图标并点击其可点击的父元素
            # 这个方法专门处理带下拉箭头的元素
            arrow_icons = driver.find_elements(By.CSS_SELECTOR, 
                "svg.fa-angles-down, svg.more-icon, [class*='arrow'], [class*='expand']")
            
            for icon in arrow_icons:
                if icon.is_displayed():
                    try:
                        # 查找可点击的父元素 (向上找5层)
                        script = """
                            function findClickableParent(element, maxDepth = 5) {
                                let current = element;
                                let depth = 0;
                                
                                while (current && depth < maxDepth) {
                                    // 检查元素是否可点击
                                    if (current.tagName === 'A' || 
                                        current.tagName === 'BUTTON' || 
                                        current.onclick != null ||
                                        current.getAttribute('role') === 'button' ||
                                        window.getComputedStyle(current).cursor === 'pointer') {
                                        return current;
                                    }
                                    
                                    current = current.parentElement;
                                    depth++;
                                }
                                
                                return null; // 没找到可点击的父元素
                            }
                            
                            const clickableParent = findClickableParent(arguments[0]);
                            if (clickableParent) {
                                clickableParent.click();
                                return true;
                            }
                            return false;
                        """
                        clicked = driver.execute_script(script, icon)
                        if clicked:
                            print("  成功找到并点击了下拉箭头的可点击父元素")
                            time.sleep(1)
                    except Exception as icon_e:
                        print(f"  尝试点击下拉箭头时出错: {icon_e}")
            
            # 最后一种方法：强制点击整个readmore-toggle区域
            try:
                toggle_areas = driver.find_elements(By.CSS_SELECTOR, "div.readmore-toggle")
                for area in toggle_areas:
                    if area.is_displayed():
                        print("  尝试点击整个readmore-toggle区域")
                        # 使用JavaScript触发事件
                        driver.execute_script("""
                            var evt = new MouseEvent('click', {
                                bubbles: true,
                                cancelable: true,
                                view: window
                            });
                            arguments[0].dispatchEvent(evt);
                        """, area)
                        time.sleep(1)
            except Exception as area_e:
                print(f"  尝试点击readmore-toggle区域时出错: {area_e}")
                
        except Exception as expand_e:
            print(f"  尝试展开隐藏内容时出错 (非致命): {expand_e}")
            
        # --- 在获取信息前确保页面完全加载 ---
        # 短暂等待，确保任何异步内容已加载
        time.sleep(2)
        
        # 获取游戏简介
        try:
            description_element = driver.find_element(By.CSS_SELECTOR, "div[id='gamedescription'] div.read-more-content")
            description = description_element.text.strip()
            if description:
                print(f"  获取到游戏简介: {description[:50]}..." if len(description) > 50 else f"  获取到游戏简介: {description}")
            else:
                # 尝试其他可能的选择器
                other_desc_elements = driver.find_elements(By.CSS_SELECTOR, "div.read-more-content, div.game-desc-content")
                for elem in other_desc_elements:
                    content = elem.text.strip()
                    if content:
                        description = content
                        print(f"  通过备选方法获取到游戏简介: {description[:50]}..." if len(description) > 50 else f"  通过备选方法获取到游戏简介: {description}")
                        break
        except Exception as e:
            print(f"  获取游戏简介时出错: {e}")
        
        # 获取游戏类型 - 改进的方法
        try:
            # --- 展开页面后，重新尝试获取游戏类型数据 ---
            # 为了调试，先获取表格内容
            table_debug = driver.find_elements(By.TAG_NAME, "table")
            for idx, table in enumerate(table_debug):
                try:
                    print(f"  [调试] 表格 #{idx+1} 包含行数: {len(table.find_elements(By.TAG_NAME, 'tr'))}")
                    # 查找包含游戏类型的行
                    type_rows = table.find_elements(By.XPATH, ".//tr[.//th[contains(text(), '游戏类型')] or .//th[contains(text(), '类别')]]")
                    if type_rows:
                        print(f"  [调试] 表格 #{idx+1} 找到包含游戏类型的行: {len(type_rows)}个")
                except Exception as td:
                    pass
                
            # 重要：需要确保不会将"开发者的话"或"简介"误认为"游戏类型"
            found_category = False
            
            # 方法1: 特别处理 - 找到精确匹配"游戏类型"或"类别"的th元素
            # 这种方法更精确，不会与"开发者的话"混淆
            try:
                # 使用更精确的XPath：确保只匹配th元素且内容完全匹配或以游戏类型开头
                precise_type_cells = driver.find_elements(By.XPATH, 
                    "//th[normalize-space(text())='游戏类型' or normalize-space(text())='类别' or starts-with(normalize-space(text()), '游戏类型')]")
                
                for cell in precise_type_cells:
                    try:
                        # 查找该元素的父行
                        parent_row = cell.find_element(By.XPATH, "./ancestor::tr")
                        # 获取该行的所有单元格
                        row_cells = parent_row.find_elements(By.TAG_NAME, "td")
                        if row_cells:
                            value_cell = row_cells[0]  # 通常游戏类型值在第一个td单元格
                            cell_text = value_cell.text.strip()
                            if cell_text:
                                # 应用格式化函数
                                category = format_game_category(cell_text)
                                print(f"  获取到游戏类型(精确匹配): {category} (原始: {cell_text})")
                                found_category = True
                                break
                    except Exception as ce:
                        print(f"  [调试] 处理精确匹配单元格出错: {ce}")
                        continue
            except Exception as xe:
                print(f"  精确匹配方法出错: {xe}")
            
            # 如果精确匹配未找到，尝试模糊匹配（但需要避免误匹配）
            if not found_category:
                # 方法2: 查找包含"游戏类型"或"类别"的所有表格单元格，但要过滤掉"开发者的话"和"简介"
                type_cells = driver.find_elements(By.XPATH, "//*[contains(text(), '游戏类型') or contains(text(), '类别')]")
                for cell in type_cells:
                    try:
                        cell_tag = cell.tag_name
                        cell_text = cell.text.strip()
                        # 排除"开发者的话"和"简介"
                        if "开发者的话" in cell_text or "简介" in cell_text:
                            print(f"  [调试] 跳过可能误认为游戏类型的单元格: {cell_tag} - '{cell_text}'")
                            continue
                            
                        print(f"  [调试] 找到包含关键词的单元格: {cell_tag} - '{cell_text}'")
                        
                        # 只处理th标签或特定格式的单元格
                        if cell_tag != 'th' and not (cell_text == '游戏类型' or cell_text == '类别'):
                            next_sibling = driver.execute_script("""
                                let elem = arguments[0];
                                // 如果当前元素是label或span，查找下一个兄弟元素
                                return elem.nextElementSibling;
                            """, cell)
                            
                            # 如果有下一个兄弟元素并包含类型值
                            if next_sibling:
                                sibling_text = next_sibling.text.strip()
                                if sibling_text and not ("开发者" in sibling_text or "简介" in sibling_text):
                                    category = format_game_category(sibling_text)
                                    print(f"  获取到游戏类型(兄弟元素): {category} (原始: {sibling_text})")
                                    found_category = True
                                    break
                            continue
                        
                        # 尝试找到父行和值单元格
                        parent_row = cell.find_element(By.XPATH, "./ancestor::tr")
                        row_cells = parent_row.find_elements(By.TAG_NAME, "td")
                        if row_cells:
                            value_cell = row_cells[0]  # 通常游戏类型值在第一个td单元格
                            cell_text = value_cell.text.strip()
                            if cell_text:
                                # 应用格式化函数
                                category = format_game_category(cell_text)
                                print(f"  获取到游戏类型(直接方法): {category} (原始: {cell_text})")
                                found_category = True
                                break
                    except Exception as ce:
                        print(f"  [调试] 处理单元格出错: {ce}")
                        continue
                    
            # 方法3: 使用XPath直接查找游戏类型后面的单元格文本
            if not found_category:
                try:
                    type_values = driver.find_elements(By.XPATH, 
                        "//th[text()='游戏类型' or text()='类别']/following-sibling::td[1]")
                    
                    if type_values:
                        for value in type_values:
                            text = value.text.strip()
                            if text:
                                # 应用格式化函数
                                category = format_game_category(text)
                                print(f"  获取到游戏类型(XPath方法): {category} (原始: {text})")
                                found_category = True
                                break
                except Exception as xe:
                    print(f"  XPath查找出错: {xe}")
            
            # 方法4: 使用JavaScript查找包含游戏类型的表格行并提取数据
            if not found_category:
                js_script = """
                    // 在整个文档中查找包含"游戏类型"或"类别"的文本节点
                    function findTypeValue() {
                        // 查找所有表格行
                        const rows = document.querySelectorAll('tr');
                        for (const row of rows) {
                            const text = row.textContent || '';
                            // 确保不包含"开发者的话"或"简介"
                            if ((text.includes('游戏类型') || text.includes('类别')) && 
                                !text.includes('开发者的话') && !text.includes('简介')) {
                                // 找到游戏类型行，获取td的内容
                                const td = row.querySelector('td');
                                if (td) {
                                    return td.textContent.trim();
                                }
                            }
                        }
                        
                        // 尝试查找其他格式
                        const typeLabels = document.querySelectorAll('div, span, p, label');
                        for (const label of typeLabels) {
                            const text = label.textContent || '';
                            // 确保只匹配精确的"游戏类型"或"类别"文本
                            if ((text === '游戏类型' || text === '类别' || 
                                text === '游戏类型：' || text === '类别：') && 
                                !text.includes('开发者的话') && !text.includes('简介')) {
                                // 获取下一个兄弟元素
                                let nextSibling = label.nextElementSibling;
                                if (nextSibling) {
                                    return nextSibling.textContent.trim();
                                }
                                
                                // 或者查找父元素的下一个子元素
                                const parent = label.parentElement;
                                if (parent) {
                                    const children = Array.from(parent.children);
                                    const index = children.indexOf(label);
                                    if (index >= 0 && index + 1 < children.length) {
                                        return children[index + 1].textContent.trim();
                                    }
                                }
                            }
                        }
                        
                        return null;
                    }
                    
                    return findTypeValue();
                """
                
                js_result = driver.execute_script(js_script)
                if js_result:
                    # 应用格式化函数
                    category = format_game_category(js_result)
                    print(f"  获取到游戏类型(JavaScript方法): {category} (原始: {js_result})")
                    found_category = True
                
            # 如果所有方法都失败，尝试从页面源码中提取
            if not found_category:
                # 获取页面源码
                page_source = driver.page_source
                
                # 使用正则表达式查找游戏类型 - 更精确的模式匹配
                pattern = r'<th[^>]*>\s*游戏类型\s*</th>\s*<td[^>]*>([^<]+)</td>|<th[^>]*>\s*类别\s*</th>\s*<td[^>]*>([^<]+)</td>'
                type_matches = re.findall(pattern, page_source)
                
                if type_matches:
                    for match in type_matches:
                        # 从匹配组中提取非空值
                        match_text = match[0] if match[0] else match[1]
                        if match_text.strip():
                            # 应用格式化函数
                            category = format_game_category(match_text.strip())
                            print(f"  获取到游戏类型(正则表达式方法): {category} (原始: {match_text.strip()})")
                            found_category = True
                            break
            
        except Exception as e:
            print(f"  获取游戏类型时出错: {e}")
        
        # 获取游戏评分
        try:
            rating_element = driver.find_element(By.CSS_SELECTOR, "div.review_num span")
            rating = rating_element.text.strip()
            print(f"  获取到游戏评分: {rating}")
        except NoSuchElementException:
            # 尝试其他可能的评分选择器
            try:
                alternative_rating_elements = driver.find_elements(By.CSS_SELECTOR, "div.score-num, span.score-text, div.game-score")
                for elem in alternative_rating_elements:
                    rating_text = elem.text.strip()
                    if rating_text and re.match(r'\d+(\.\d+)?', rating_text):
                        rating = rating_text
                        print(f"  通过备选方法获取到游戏评分: {rating}")
                        break
            except Exception:
                print("  未找到评分元素")
        except Exception as e:
            print(f"  获取游戏评分时出错: {e}")
        
        # 关闭详情页并切回原始窗口
        driver.close()
        driver.switch_to.window(original_window)
        
    except Exception as e:
        print(f"  访问详情页出错: {e}")
        # 尝试切回原始窗口
        try:
            driver.switch_to.window(original_window)
        except:
            pass
    
    return description, category, rating, external_link, source, icon_url

def get_16p_data(target_url): 
    """
    获取指定 URL (16p 开测表) 的国内游戏信息, 支持增量保存。
    """
    print(f"开始抓取 16p 页面 {target_url} 的国内游戏信息 (增量模式)...")
    
    # 输出文件名格式调整 (基于运行日期)
    output_filename = f'16p_games_{datetime.now().strftime("%Y%m%d")}.jsonl' 
    output_path = os.path.join(DATA_DIR, output_filename)
    
    # 1. 加载已存在的链接 (基于详情页链接)
    existing_links, original_links = load_existing_links(output_path)
    
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
            
        # --- 新增: 滚动到底部以确保所有内容加载 ---
        scroll_to_bottom(driver)

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
                    platform, description, icon_url, link, rating = "未知平台", "", "", "", "未知评分"
                    external_link, source = "", "16p"  # 外部链接和来源平台
                    # platform 默认为 国内游戏
                    platform = "国内游戏" 
                    
                    scrape_successful = False
                    item_data = {}
                    
                    try:
                        # --- 提取链接 ---
                        href = game_element.get_attribute('href')
                        if href:
                            original_16p_link = urljoin(BASE_URL, href) # 合成完整 URL
                            link = original_16p_link  # 初始时，链接为16p链接
                            print(f"    链接: {link}")
                            
                            # --- 检查链接是否已存在 ---
                            # 重要改进：同时检查外部链接集合和原始链接集合
                            if link in existing_links or link in original_links:
                                print(f"    链接 {link} 已存在于 {output_filename}，跳过。")
                                continue
                        else:
                            print("    警告: 未找到此条目的链接，跳过。")
                            continue
                        
                        # --- 从列表页面提取基本信息 ---
                        # 保留获取名称、厂商、状态的代码，但移除获取图标的代码
                        
                        # --- 提取名称 ---
                        try:
                            name_element = game_element.find_element(By.CSS_SELECTOR, "div.right-section div.game-info-1 span")
                            raw_name = name_element.text.strip()
                            # 清理游戏名称
                            name = clean_game_name(raw_name)
                            print(f"    名称: {name}" + (f" (原始: {raw_name})" if name != raw_name else ""))
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
                        
                        # --- 添加: 访问详情页获取更多信息 ---
                        if link:
                            print(f"    访问详情页获取更多信息: {link}")
                            # 备份当前页面句柄以便返回
                            description, category, rating, external_link, source, icon_url = get_game_details(driver, link)
                            random_delay(0.5, 1)  # 在请求之间添加延迟
                        
                        scrape_successful = True
                        
                    except Exception as main_scrape_e:
                        print(f"    处理条目时发生错误: {main_scrape_e}")
                        scrape_successful = False
                    
                    # --- 写入文件 ---
                    if scrape_successful and link: # 确保链接有效
                        # 保存原始16p链接
                        original_16p_link = link
                        
                        # 如果找到了外部平台链接，替换原始链接
                        if external_link:
                            link = external_link
                            print(f"    将原始链接 {original_16p_link} 替换为外部平台链接 {link}")
                        
                        item_data = {
                            "name": name,
                            "platform": platform, # 默认为国内游戏
                            "status": status,
                            "publisher": publisher,
                            "category": category, # 从详情页获取
                            "rating": rating,     # 从详情页获取
                            "description": description, # 从详情页获取
                            "link": link,        # 可能是外部平台链接
                            "original_link": original_16p_link,  # 始终保存原始16p链接
                            "icon_url": icon_url,
                            "date": current_date_str, # 使用当前区块的日期
                            "source": source     # 来源平台，可能已更新
                        }
                        try:
                            json.dump(item_data, outfile, ensure_ascii=False)
                            outfile.write('\n')
                            newly_scraped_count += 1
                            
                            # 同时将两种链接都添加到集合中
                            existing_links.add(link) 
                            original_links.add(original_16p_link)
                            
                            print(f"    -> 成功保存条目 {name} 到 {output_filename} (来源: {source})")
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