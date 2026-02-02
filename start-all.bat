@echo off
REM 统一启动脚本 - 启动所有服务
REM 启动顺序: Docker (PostgreSQL+Redis) -> Spring Boot -> Python Worker -> Vue Frontend

echo.
echo ========================================
echo   文档智能提取系统 - 统一启动脚本
echo ========================================
echo.

REM 检查 Docker
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未运行
    echo        请先启动 Docker Desktop
    pause
    exit /b 1
)
echo [OK] Docker 正在运行
echo.

REM 启动 Docker 容器
echo [1/4] 正在启动 PostgreSQL 和 Redis (Docker)...
docker-compose up -d postgres redis

REM 等待容器启动
echo 等待容器就绪...
timeout /t 10 /nobreak >nul

REM 检查容器状态
docker ps | findstr "docextract-postgres" >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] PostgreSQL 容器未正常启动
    pause
    exit /b 1
)

docker ps | findstr "docextract-redis" >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Redis 容器未正常启动
    pause
    exit /b 1
)
echo [OK] Docker 容器已启动
echo.

REM 启动 Spring Boot 后端
echo [2/4] 正在启动 Spring Boot 后端...
cd backend
start "Spring Boot Backend" cmd /k "mvn spring-boot:run"
cd ..
timeout /t 15 /nobreak >nul
echo [OK] 后端已启动 (新窗口)
echo.

REM 启动 Python Worker
echo [3/4] 正在启动 Python Worker...
cd python-worker
set REDIS_HOST=localhost
set REDIS_PORT=6379
set REDIS_PASSWORD=redis123
set BACKEND_API_URL=http://localhost:8080
start "Python Worker" cmd /k "python worker.py"
cd ..
timeout /t 5 /nobreak >nul
echo [OK] Worker 已启动 (新窗口)
echo.

REM 启动 Vue 前端
echo [4/4] 正在启动 Vue 前端...
cd fronted
REM 检查 node_modules 是否存在
if not exist "node_modules" (
    echo [信息] 首次运行，正在安装前端依赖...
    call npm install
    if %errorlevel% neq 0 (
        echo [错误] 前端依赖安装失败
        pause
        exit /b 1
    )
)
start "Vue Frontend" cmd /k "npm run dev"
cd ..
timeout /t 5 /nobreak >nul
echo [OK] 前端已启动 (新窗口)
echo.

echo ========================================
echo   所有服务已启动！
echo ========================================
echo.
echo 服务列表:
echo   - 前端: http://localhost:5173
echo   - 后端: http://localhost:8080
echo   - 数据库: localhost:5432 (PostgreSQL)
echo   - 缓存: localhost:6379 (Redis)
echo.
echo 默认登录:
echo   用户名: admin
echo   密码: admin123
echo.
echo 注意: 已打开 3 个新窗口分别运行后端、Worker 和前端
echo       请勿关闭这些窗口
echo ========================================
echo.
pause
