@echo off
chcp 65001 >nul
echo ========================================
echo 修复Redis连接问题
echo ========================================
echo.

echo 步骤 1: 检查Redis容器状态...
docker ps -f name=docextract-redis

echo.
echo 步骤 2: 如果Redis未运行，启动它...
docker start docextract-redis 2>nul

echo.
echo 步骤 3: 测试Redis连接...
timeout /t 5 /nobreak >nul
docker exec docextract-redis redis-cli ping

echo.
echo 步骤 4: 重启Python Worker...
taskkill /F /FI "WINDOWTITLE eq Python Worker*" >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

timeout /t 3 /nobreak >nul
cd python-worker
start "Python Worker" cmd /k "python worker.py"
cd ..

echo.
echo ========================================
echo Redis连接修复完成！
echo ========================================
echo.
echo 如果仍然有问题，请检查：
echo 1. .env 文件中的 REDIS_PASSWORD 是否为 'redis123'
echo 2. docker-compose.yml 中的 redis 服务密码配置
echo 3. application.yml 中的 spring.redis.password 配置
echo.
pause
