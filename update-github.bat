@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo  xpbedwars-server-pack GitHub updater
echo ==========================================
echo.

where git >nul 2>nul
if errorlevel 1 (
    echo [ERROR] 没有找到 Git，请先安装 Git for Windows。
    pause
    exit /b 1
)

git status --short
echo.
git add -A

git diff --cached --quiet
if errorlevel 1 (
    set "MSG="
    set /p "MSG=提交说明（直接回车使用自动说明）: "
    if "!MSG!"=="" set "MSG=update: %date% %time%"
    git commit -m "!MSG!"
    if errorlevel 1 (
        echo.
        echo [ERROR] 提交失败。
        pause
        exit /b 1
    )
) else (
    echo 没有需要提交的改动，直接检查远程状态。
)

echo.
echo 正在推送到 origin main ...
git push origin main
if errorlevel 1 (
    echo.
    echo [ERROR] 推送失败，请检查 GitHub 登录或网络。
    pause
    exit /b 1
)

echo.
echo 更新完成：
echo https://github.com/Blacklaegend/xpbedwars-server-pack
echo.
pause
