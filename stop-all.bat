@echo off
echo.
echo ========================================
echo   停止所有服务
echo ========================================
echo.

REM 停止 Docker 容器
echo [1/3] 正在停止 Docker 容器...
docker-compose down
echo [OK] Docker 容器已停止
echo.

REM 提示信息
echo [2/3] 正在关闭后端、Worker 和前端...
echo        请手动关闭打开的命令行窗口
echo.

REM 检查并删除前端 node_modules（可选，用于清理空间）
echo [3/3] 清理临时文件...
if exist "fronted\node_modules" (
    set /p CLEAN_NPM="是否删除前端 node_modules 以释放空间？(y/n): "
    if /i "!CLEAN_NPM!"=="y" (
        echo 正在删除 node_modules...
        rmdir /s /q fronted\node_modules
        echo [OK] 已删除 node_modules
    )
)
echo.

echo ========================================
echo   服务已停止！
echo ========================================
echo.
echo 提示：
echo   - Docker 容器已停止
echo   - 请手动关闭后端、Worker 和前端窗口
echo   - 如需重启，运行 start-all.bat
echo ========================================
echo.
pause
