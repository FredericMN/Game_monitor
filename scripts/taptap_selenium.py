# taptap_selenium.py
# 使用 Selenium 抓取 TapTap 网站内容

# 导入必要的库
import os
import time
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# 保存结果的文件夹
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

def setup_driver():
    """
    配置并初始化 Chrome 浏览器
    """
    # 设置 Chrome 浏览器选项
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 无界面模式
    chrome_options.add_argument("--disable-gpu")  # 禁用 GPU 加速
    chrome_options.add_argument("--window-size=1920,1080")  # 设置窗口大小
    chrome_options.add_argument("--no-sandbox")  # 禁用沙盒模式
    chrome_options.add_argument("--disable-dev-shm-usage")  # 禁用 /dev/shm 使用
    chrome_options.add_argument("--disable-web-security")  # 禁用同源策略
    chrome_options.add_argument("--allow-running-insecure-content")  # 允许运行不安全内容
    
    # 添加用户代理，模拟真实浏览器
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36")
    
    # 初始化 Chrome 浏览器
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    return driver

def get_taptap_daily_games(url):
    """
    获取 TapTap 日历页面的游戏信息
    
    参数:
        url (str): TapTap 日历页面的 URL
        
    返回:
        list: 包含游戏信息的字典列表
    """
    print(f"正在访问 TapTap 日历页面: {url}")
    
    # 初始化 Chrome 浏览器
    driver = setup_driver()
    
    try:
        # 访问目标网页
        driver.get(url)
        print("页面加载中...")
        
        # 等待页面加载完成（尝试多种可能的选择器）
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR, 
                    ".app-calendar-container, .game-list, .game-item, .card-wrap"
                ))
            )
            # 成功找到某个元素
            print("页面元素加载成功")
        except Exception as e:
            print(f"等待页面元素超时，将尝试继续解析: {e}")
        
        # 适当等待，确保动态内容加载完成
        time.sleep(5)
        
        # 尝试执行一些滚动，以确保动态内容加载
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3);")
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(2)
        
        # 获取页面源代码
        page_source = driver.page_source
        
        # 将页面源代码保存到文件，方便调试
        with open(os.path.join(DATA_DIR, 'taptap_page.html'), 'w', encoding='utf-8') as f:
            f.write(page_source)
        print(f"页面源代码已保存到 {os.path.join(DATA_DIR, 'taptap_page.html')}")
        
        # 使用 BeautifulSoup 解析页面
        soup = BeautifulSoup(page_source, 'lxml')
        
        # 尝试多种可能的容器选择器
        containers = [
            # 日历页面选择器
            soup.select(".app-calendar-container"),
            # 排行榜页面选择器
            soup.select(".game-list"),
            # 首页选择器
            soup.select(".card-wrap"),
            # 其他可能的容器
            soup.select(".main-container")
        ]
        
        # 找到非空容器
        container = None
        for c in containers:
            if c and len(c) > 0:
                container = c
                break
        
        if not container:
            print("未找到游戏容器，可能页面结构已变化")
            return []
        
        # 从容器中查找游戏项
        game_items = []
        for cont in container:
            # 尝试多种可能的游戏项选择器
            items = (
                cont.select(".app-calendar-item") or
                cont.select(".game-item") or
                cont.select(".card-middle") or
                cont.select(".app-item")
            )
            if items:
                game_items.extend(items)
        
        if not game_items:
            print("未找到游戏项，可能页面结构已变化")
            return []
        
        print(f"找到 {len(game_items)} 个游戏项")
        
        # 解析每个游戏的信息
        games_data = []
        for item in game_items:
            try:
                # 游戏名称
                name_elem = (
                    item.select_one(".app-calendar-item-title") or
                    item.select_one(".title") or
                    item.select_one(".name") or
                    item.select_one("h3, h4")
                )
                name = name_elem.text.strip() if name_elem else "未知名称"
                
                # 游戏链接
                link_elem = item.select_one("a")
                link = link_elem.get("href") if link_elem else ""
                if link and not link.startswith("http"):
                    link = f"https://www.taptap.cn{link}"
                
                # 游戏状态（如测试招募、首发等）
                status_elem = (
                    item.select_one(".app-calendar-item-tag") or
                    item.select_one(".tag") or
                    item.select_one(".status")
                )
                status = status_elem.text.strip() if status_elem else "未知状态"
                
                # 游戏评分
                rating_elem = (
                    item.select_one(".app-calendar-item-rating") or
                    item.select_one(".rating") or
                    item.select_one(".score")
                )
                rating = rating_elem.text.strip() if rating_elem else "暂无评分"
                
                # 游戏分类
                category_elem = (
                    item.select_one(".app-calendar-item-category") or
                    item.select_one(".category") or
                    item.select_one(".info")
                )
                category = category_elem.text.strip() if category_elem else "未知分类"
                
                # 游戏图标
                icon_elem = item.select_one("img")
                icon_url = icon_elem.get("src") if icon_elem else ""
                
                # 组装游戏数据
                game_data = {
                    "name": name,
                    "link": link,
                    "status": status,
                    "rating": rating,
                    "category": category,
                    "icon_url": icon_url,
                    "source": "TapTap",
                    "date": datetime.now().strftime("%Y-%m-%d")
                }
                
                games_data.append(game_data)
                print(f"已提取游戏信息: {name}")
                
            except Exception as e:
                print(f"解析游戏信息时出错: {e}")
                continue
        
        return games_data
        
    except Exception as e:
        print(f"访问页面或提取数据时出错: {e}")
        return []
        
    finally:
        # 关闭浏览器
        driver.quit()
        print("浏览器已关闭")

def save_to_json(data, filename):
    """
    将数据保存为 JSON 文件
    
    参数:
        data: 要保存的数据
        filename (str): 文件名
    """
    file_path = os.path.join(DATA_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"数据已保存到 {file_path}")

if __name__ == "__main__":
    # 尝试多个 TapTap 相关页面
    urls = [
        "https://www.taptap.cn/app-calendar/2025-04-07",
        "https://www.taptap.cn/top/download",  # 热门榜单页面
        "https://www.taptap.cn/mobile"         # 首页
    ]
    
    all_games = []
    
    # 尝试访问多个页面，直到成功获取数据
    for url in urls:
        print(f"\n尝试从 URL {url} 获取数据")
        games = get_taptap_daily_games(url)
        
        if games:
            all_games.extend(games)
            print(f"成功从 {url} 获取 {len(games)} 个游戏的信息")
            break  # 成功获取数据后退出循环
    
    # 检查是否成功获取数据
    if all_games:
        print(f"\n总共获取 {len(all_games)} 个游戏的信息")
        
        # 保存为 JSON 文件
        save_to_json(all_games, "taptap_games.json")
    else:
        print("\n未获取到游戏数据") 