# 设置UTF-8编码
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 显示标题
Write-Host "`n================================================="
Write-Host "            游戏监控系统启动脚本" -ForegroundColor Cyan
Write-Host "=================================================`n"

# 获取当前目录
$currentDir = (Get-Location).Path
Write-Host "当前工作目录: $currentDir" -ForegroundColor Gray

# 检查必要的目录和文件
if (-not (Test-Path "$currentDir\venv\Scripts\python.exe")) {
    Write-Host "错误: 找不到虚拟环境 'venv'" -ForegroundColor Red
    Write-Host "请运行: python -m venv venv"
    Read-Host "按回车键退出"
    exit 1
}

if (-not (Test-Path "$currentDir\backend")) {
    Write-Host "错误: 找不到后端目录 'backend'" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

if (-not (Test-Path "$currentDir\frontend")) {
    Write-Host "错误: 找不到前端目录 'frontend'" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

Write-Host "所有必要的目录和文件检查完毕" -ForegroundColor Green

# 定义Python解释器路径
$pythonPath = "$currentDir\venv\Scripts\python.exe"

# 启动后端服务
Write-Host "`n正在启动后端服务器..." -ForegroundColor Yellow
$backendWindow = Start-Process -FilePath "cmd.exe" -ArgumentList "/k $pythonPath $currentDir\backend\app.py" -PassThru

if ($null -eq $backendWindow) {
    Write-Host "启动后端服务器失败!" -ForegroundColor Red
    Read-Host "按回车键退出"
    exit 1
}

# 启动前端服务
Write-Host "正在启动前端服务器..." -ForegroundColor Yellow
$frontendWindow = Start-Process -FilePath "cmd.exe" -ArgumentList "/k $pythonPath -m http.server 8000 --directory $currentDir\frontend" -PassThru

if ($null -eq $frontendWindow) {
    Write-Host "启动前端服务器失败!" -ForegroundColor Red
    # 尝试关闭后端窗口
    if ($null -ne $backendWindow) {
        Stop-Process -Id $backendWindow.Id -Force -ErrorAction SilentlyContinue
    }
    Read-Host "按回车键退出"
    exit 1
}

# 等待服务器启动
Write-Host "等待服务器初始化（3秒）..." -ForegroundColor Green
Start-Sleep -Seconds 3

# 打开浏览器
Write-Host "在默认浏览器中打开 http://localhost:8000 ..." -ForegroundColor Green
Start-Process "http://localhost:8000"

Write-Host "`n================================================="
Write-Host "后端和前端服务器已在单独的命令行窗口中运行。" -ForegroundColor Cyan
Write-Host "如需停止服务器，请关闭相应的命令行窗口。"
Write-Host "=================================================`n"

Read-Host "按回车键关闭此窗口" 