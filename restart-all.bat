@echo off
chcp 65001 >nul
echo ========================================
echo 文档智能提取系统 - 重启所有服务
echo ========================================
echo.

echo 步骤 1: 停止所有服务...
call stop-all.bat

echo.
echo 步骤 2: 清理并重新初始化数据库...
echo 正在删除旧的数据库容器...
docker rm -f docextract-postgres 2>nul

echo 等待3秒...
timeout /t 3 /nobreak >nul

echo.
echo 步骤 3: 启动数据库和Redis...
docker-compose up -d postgres redis

echo 等待数据库初始化...
timeout /t 10 /nobreak >nul

echo.
echo 步骤 4: 启动后端服务...
cd backend
start "Backend" cmd /k "mvn spring-boot:run"
cd ..

echo.
echo 步骤 5: 启动Python Worker...
timeout /t 15 /nobreak >nul
cd python-worker
start "Python Worker" cmd /k "python worker.py"
cd ..

echo.
echo 步骤 6: 启动前端服务...
timeout /t 10 /nobreak >nul
cd fronted
start "Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ========================================
echo 所有服务已启动！
echo.
echo 访问地址:
echo - 前端: http://localhost:5173
echo - 后端: http://localhost:8080
echo - Redis: localhost:6379
echo - PostgreSQL: localhost:5432
echo ========================================
echo.
echo 默认账号:
echo - 用户名: admin
echo - 密码: admin123
echo.
echo 按任意键退出此窗口...
pause >nul
