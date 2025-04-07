#!/usr/bin/env python3
# update_data.py
# 自动化脚本，用于定时更新游戏数据并与后端同步

import os
import sys
import time
import logging
import argparse
from datetime import datetime
import subprocess
import importlib.util

# 设置日志记录
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                         'data', 'update_log.txt')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('update_data')

# 获取脚本和数据目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(ROOT_DIR, 'data')

def add_to_system_startup(platform='windows'):
    """
    将脚本添加到系统启动项
    
    参数:
        platform (str): 操作系统类型，'windows' 或 'linux'
    """
    script_path = os.path.abspath(__file__)
    
    if platform.lower() == 'windows':
        # Windows: 创建一个 .bat 文件放在启动文件夹
        startup_dir = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
        bat_path = os.path.join(startup_dir, 'game_monitor_update.bat')
        
        with open(bat_path, 'w') as f:
            f.write(f'@echo off\n')
            f.write(f'python "{script_path}" --quiet\n')
        
        logger.info(f"已将更新脚本添加到 Windows 启动项: {bat_path}")
    
    elif platform.lower() == 'linux':
        # Linux: 创建一个 crontab 任务
        from crontab import CronTab
        
        cron = CronTab(user=True)
        job = cron.new(command=f'python3 {script_path} --quiet')
        job.setall('0 8 * * *')  # 每天早上 8 点运行
        cron.write()
        
        logger.info("已将更新脚本添加到 Linux crontab 定时任务")
    
    else:
        logger.error(f"不支持的平台: {platform}")

def run_collect_script():
    """
    运行数据收集脚本
    
    返回:
        bool: 是否成功收集数据
    """
    logger.info("开始运行数据收集脚本...")
    
    try:
        # 方法 1: 导入并调用函数
        sys.path.append(SCRIPT_DIR)
        
        try:
            from collect_games import collect_all_game_data
            # 收集数据
            games = collect_all_game_data()
            
            if games:
                logger.info(f"成功收集 {len(games)} 个游戏信息")
                return True
            else:
                logger.warning("未收集到任何游戏数据")
                return False
                
        except ImportError as e:
            logger.error(f"导入 collect_games 模块出错: {e}")
            
            # 方法 2: 作为子进程运行脚本
            logger.info("尝试作为子进程运行脚本...")
            result = subprocess.run(['python', os.path.join(SCRIPT_DIR, 'collect_games.py')], 
                                   capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("子进程成功运行数据收集脚本")
                return True
            else:
                logger.error(f"子进程运行失败: {result.stderr}")
                return False
    
    except Exception as e:
        logger.error(f"运行数据收集脚本时出错: {e}")
        return False

def restart_backend():
    """
    尝试重启后端服务
    
    返回:
        bool: 是否成功重启
    """
    logger.info("尝试重启后端服务...")
    
    try:
        # 检查后端是否在运行
        # 这里使用简单的方法：尝试发起一个请求到后端
        import requests
        
        try:
            response = requests.get('http://localhost:5000/')
            if response.status_code == 200:
                logger.info("后端服务已在运行")
                return True
        except:
            logger.info("后端服务未运行，尝试启动...")
        
        # 尝试启动后端
        app_path = os.path.join(ROOT_DIR, 'backend', 'app.py')
        
        # 非阻塞方式启动后端
        if os.name == 'nt':  # Windows
            subprocess.Popen(['python', app_path], 
                           creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:  # Linux/Mac
            subprocess.Popen(['python3', app_path], 
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE)
        
        # 给一些时间让后端启动
        time.sleep(5)
        
        # 验证后端是否已启动
        try:
            response = requests.get('http://localhost:5000/')
            if response.status_code == 200:
                logger.info("后端服务已成功启动")
                return True
            else:
                logger.warning(f"后端服务启动，但返回状态码: {response.status_code}")
                return False
        except:
            logger.error("后端服务启动失败")
            return False
            
    except Exception as e:
        logger.error(f"重启后端服务时出错: {e}")
        return False

def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description='游戏监控数据更新工具')
    parser.add_argument('--quiet', action='store_true', help='安静模式，不输出日志到控制台')
    parser.add_argument('--add-to-startup', action='store_true', help='将脚本添加到系统启动项')
    parser.add_argument('--platform', choices=['windows', 'linux'], default='windows', help='操作系统类型')
    
    args = parser.parse_args()
    
    if args.quiet:
        # 移除控制台日志处理器
        for handler in logger.handlers[:]:
            if isinstance(handler, logging.StreamHandler):
                logger.removeHandler(handler)
    
    if args.add_to_startup:
        add_to_system_startup(args.platform)
        return
    
    logger.info("=== 开始数据更新 ===")
    logger.info(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行数据收集脚本
    success = run_collect_script()
    
    if success:
        # 重启后端服务
        restart_success = restart_backend()
        if restart_success:
            logger.info("数据更新和后端重启成功完成")
        else:
            logger.warning("数据已更新，但后端重启失败")
    else:
        logger.error("数据更新失败")
    
    logger.info("=== 数据更新结束 ===\n")

if __name__ == "__main__":
    main() 