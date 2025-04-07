@echo off
echo 正在启动游戏监控系统...

REM 使用不包含复杂命令的简单PowerShell脚本
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_dev_simple.ps1"

REM 如果PowerShell脚本失败，显示错误信息
if %ERRORLEVEL% NEQ 0 (
    echo 启动失败！请检查错误信息。
    pause
    exit /b %ERRORLEVEL%
)

REM 脚本正常结束
echo 启动完成。
pause 