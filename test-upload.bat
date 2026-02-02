@echo off
echo ========================================
echo 批量上传功能测试
echo ========================================
echo.

echo 检查Python环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python，请安装Python 3.8+
    pause
    exit /b 1
)

echo 安装/更新所需库...
pip install requests redis >nul 2>&1

echo.
echo 运行批量上传测试...
echo.
python test-batch-upload.py

echo.
echo ========================================
echo 测试完成！
echo ========================================
echo.
pause
