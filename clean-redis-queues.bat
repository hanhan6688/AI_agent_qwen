@echo off
chcp 65001 >nul
echo ========================================
echo 清理Redis中未使用的队列
echo ========================================
echo.

echo 将删除以下队列（如果存在）:
echo - task:completed
echo - task:failed
echo.

set /p confirm="确认删除? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo 操作已取消
    pause
    exit /b 0
)

echo.
echo 连接Redis并删除队列...

redis-cli -h localhost -p 6379 -a redis123 DEL task:completed
redis-cli -h localhost -p 6379 -a redis123 DEL task:failed

echo.
echo ========================================
echo 清理完成！
echo ========================================
pause
