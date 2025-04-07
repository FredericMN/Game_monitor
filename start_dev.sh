#!/bin/bash

# 脚本用于启动开发环境：后端 Flask 服务器和前端 HTTP 服务器

# 定义日志文件路径
BACKEND_LOG="../backend.log"
FRONTEND_LOG="../frontend.log"

# 清理旧日志文件 (可选)
rm -f ../backend.log ../frontend.log

# 设置退出时清理后台进程的函数
cleanup() {
    echo "正在停止服务器..."
    # 检查并杀掉后台进程
    if kill -0 $backend_pid 2>/dev/null; then
        kill $backend_pid
        echo "后端服务器 (PID: $backend_pid) 已停止。"
    fi
    if kill -0 $frontend_pid 2>/dev/null; then
        kill $frontend_pid
        echo "前端服务器 (PID: $frontend_pid) 已停止。"
    fi
    # echo "日志文件保存在 backend.log 和 frontend.log" # 可选提示
    exit 0
}

# 捕获 Ctrl+C (SIGINT) 和终止信号 (SIGTERM) 并调用 cleanup 函数
trap cleanup SIGINT SIGTERM

echo "正在启动后端 Flask 服务器 (日志写入 backend.log)..."
cd backend
# 使用 python3 启动，并在后台运行 (&)
# 将标准输出和错误输出重定向到日志文件
python3 app.py > "$BACKEND_LOG" 2>&1 &
backend_pid=$! # 获取后台进程的 PID
cd ..

echo "正在启动前端 HTTP 服务器 (端口 8000, 日志写入 frontend.log)..."
cd frontend
# 使用 python3 启动，监听 8000 端口，并在后台运行 (&)
# 将标准输出和错误输出重定向到日志文件
python3 -m http.server 8000 > "$FRONTEND_LOG" 2>&1 &
frontend_pid=$! # 获取后台进程的 PID
cd ..

echo "等待服务器启动... (PID 后端: $backend_pid, 前端: $frontend_pid)"
sleep 2 # 等待 2 秒，确保服务器有足够时间启动

echo "在默认浏览器中打开 http://localhost:8000 ..."
open http://localhost:8000

echo "开发服务器正在运行。日志分别记录在 backend.log 和 frontend.log 文件中。"
echo "按 Ctrl+C 停止所有服务器。"

# 等待后台进程结束，这样脚本会保持运行，可以捕获 Ctrl+C
wait $backend_pid
wait $frontend_pid 