@echo off
REM Windows 批处理脚本，用于启动开发环境

REM 检查虚拟环境目录是否存在
if not exist ".\venv\Scripts\python.exe" (
    echo 错误：找不到虚拟环境 Python 可执行文件: .\venv\Scripts\python.exe
    echo 请确保已在项目根目录创建了名为 'venv' 的虚拟环境 (python -m venv venv) 并安装了依赖。
    pause
    exit /b 1
)

echo 正在启动后端 Flask 服务器 (使用 venv, 将在新窗口中运行)... 
REM 切换到 backend 目录并使用相对路径调用 venv python
start "Backend Server" cmd /k "cd backend && ..\venv\Scripts\python.exe app.py"

echo 正在启动前端 HTTP 服务器 (使用 venv, 端口 8000, 将在新窗口中运行)...
REM 切换到 frontend 目录并使用相对路径调用 venv python
start "Frontend Server" cmd /k "cd frontend && ..\venv\Scripts\python.exe -m http.server 8000"

echo 等待服务器启动...
timeout /t 3 /nobreak > nul

echo 在默认浏览器中打开 http://localhost:8000 ...
start http://localhost:8000

echo.
echo 开发服务器已启动 (在单独的窗口中)。
echo 要停止服务器，请手动关闭标题为 "Backend Server" 和 "Frontend Server" 的命令提示符窗口。
echo.
REM 保持窗口打开，直到用户按键
pause 