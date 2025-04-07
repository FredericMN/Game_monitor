# haoyou_selenium.py
# 使用 Selenium 抓取好游快爆网站内容

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
    
    # 添加用户代理，模拟真实浏览器
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36")
    
    # 初始化 Chrome 浏览器
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    return driver

def get_haoyou_games(url):
    """
    获取好游快爆网站的游戏信息
    
    参数:
        url (str): 好游快爆网站的 URL
        
    返回:
        list: 包含游戏信息的字典列表
    """
    print(f"正在访问好游快爆网站: {url}")
    
    # 初始化 Chrome 浏览器
    driver = setup_driver()
    
    try:
        # 访问目标网页
        driver.get(url)
        print("页面加载中...")
        
        # 等待页面加载完成
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".page404-game, .sugar-games, .today-games"))
            )
        except Exception as e:
            print(f"等待页面元素出现超时: {e}")
            # 继续执行，即使超时也尝试解析页面
        
        # 适当等待，确保动态内容加载完成
        time.sleep(5)
        
        # 获取页面源代码
        page_source = driver.page_source
        
        # 将页面源代码保存到文件，方便调试
        with open(os.path.join(DATA_DIR, 'haoyou_page.html'), 'w', encoding='utf-8') as f:
            f.write(page_source)
        print(f"页面源代码已保存到 {os.path.join(DATA_DIR, 'haoyou_page.html')}")
        
        # 使用 BeautifulSoup 解析页面
        soup = BeautifulSoup(page_source, 'lxml')
        
        # 尝试多种可能的容器选择器
        game_container = (
            soup.select_one(".page404-game .area-bd") or  # 404 页面中的游戏列表
            soup.select_one(".sugar-games .game-list") or  # 排行榜页面
            soup.select_one(".today-list")  # 新游发布页面
        )
        
        if not game_container:
            print("未找到游戏容器，可能页面结构不同于预期")
            return []
        
        # 根据容器类型选择正确的游戏项选择器
        game_items = []
        if "page404-game" in str(game_container):
            # 404 页面中的游戏列表
            game_items = game_container.select("li")
        elif "sugar-games" in str(game_container):
            # 排行榜页面
            game_items = game_container.select(".game-item")
        else:
            # 可能是其他类型的页面，尝试通用选择器
            game_items = game_container.select("li") or game_container.select(".game-item")
        
        if not game_items:
            print("未找到游戏项，可能页面结构不同于预期")
            return []
        
        print(f"找到 {len(game_items)} 个游戏项")
        
        # 解析每个游戏的信息
        games_data = []
        for item in game_items:
            try:
                # 游戏名称 (尝试多种可能的选择器)
                name_elem = (
                    item.select_one(".g-name") or 
                    item.select_one(".game-name") or 
                    item.select_one(".title") or 
                    item.select_one("h3")
                )
                name = name_elem.text.strip() if name_elem else "未知名称"
                
                # 游戏链接
                link_elem = item.select_one("a")
                link = link_elem.get("href") if link_elem else ""
                if link and not link.startswith("http"):
                    link = f"https://www.3839.com{link}"
                
                # 游戏状态 (从分数或下载量推断)
                status = "已上线"  # 默认状态
                
                # 游戏评分
                rating_elem = (
                    item.select_one(".score") or
                    item.select_one(".gameScore .score")
                )
                rating = rating_elem.text.strip() if rating_elem else "暂无评分"
                
                # 游戏分类/下载量
                category_elem = (
                    item.select_one(".g-info") or
                    item.select_one(".game-type") or
                    item.select_one(".category")
                )
                category = category_elem.text.strip() if category_elem else "未知分类"
                
                # 游戏图标
                icon_elem = item.select_one("img.g-icon") or item.select_one("img")
                icon_url = icon_elem.get("src") or icon_elem.get("data-src") if icon_elem else ""
                
                # 组装游戏数据
                game_data = {
                    "name": name,
                    "link": link,
                    "status": status,
                    "rating": rating,
                    "category": category,
                    "icon_url": icon_url,
                    "source": "好游快爆",
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
    # 好游快爆游戏页面 URL，更新为排行榜页面
    url = "https://www.3839.com/top/hot.html"
    
    # 获取游戏数据
    games = get_haoyou_games(url)
    
    # 检查是否成功获取数据
    if games:
        print(f"成功获取 {len(games)} 个游戏的信息")
        
        # 保存为 JSON 文件
        save_to_json(games, "haoyou_games.json")
    else:
        print("未获取到游戏数据") 