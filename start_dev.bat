@echo off
REM Windows 批处理脚本，用于启动开发环境

echo 正在启动后端 Flask 服务器 (将在新窗口中运行)... 
REM 切换到 backend 目录并启动 app.py
start "Backend Server" cmd /c "cd backend && python app.py"

echo 正在启动前端 HTTP 服务器 (端口 8000, 将在新窗口中运行)...
REM 切换到 frontend 目录并启动 http.server
start "Frontend Server" cmd /c "cd frontend && python -m http.server 8000"

echo 等待服务器启动...
timeout /t 3 /nobreak > nul

echo 在默认浏览器中打开 http://localhost:8000 ...
start http://localhost:8000

echo.
echo 开发服务器已启动 (在单独的窗口中)。
echo 要停止服务器，请手动关闭标题为 "Backend Server" 和 "Frontend Server" 的命令提示符窗口。
echo.
pause 