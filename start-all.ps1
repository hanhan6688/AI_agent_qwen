# PowerShell 统一启动脚本
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "文档智能提取系统 - 统一启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Docker
try {
    docker version >$null 2>&1
    Write-Host "[OK] Docker 正在运行" -ForegroundColor Green
} catch {
    Write-Host "[错误] Docker 未运行，请先启动 Docker Desktop" -ForegroundColor Red
    exit 1
}

# 启动 Docker 容器
Write-Host "[1/4] 正在启动 PostgreSQL 和 Redis (Docker)..." -ForegroundColor Yellow
docker-compose up -d postgres redis

Write-Host "等待容器就绪..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# 检查容器状态
$postgresCheck = docker ps | Select-String "docextract-postgres"
$redisCheck = docker ps | Select-String "docextract-redis"

if ($null -eq $postgresCheck) {
    Write-Host "[错误] PostgreSQL 容器未正常启动" -ForegroundColor Red
    exit 1
}
if ($null -eq $redisCheck) {
    Write-Host "[错误] Redis 容器未正常启动" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Docker 容器已启动" -ForegroundColor Green
Write-Host ""

# 启动 Spring Boot 后端
Write-Host "[2/4] 正在启动 Spring Boot 后端..." -ForegroundColor Yellow
$backendProcess = Start-Process -FilePath "cmd" -ArgumentList "/k", "cd /d $($PSScriptRoot)\backend && mvn spring-boot:run" -WindowStyle Normal -PassThru
Start-Sleep -Seconds 15
Write-Host "[OK] 后端已启动 (新窗口)" -ForegroundColor Green
Write-Host ""

# 启动 Python Worker
Write-Host "[3/4] 正在启动 Python Worker..." -ForegroundColor Yellow
$env:REDIS_HOST = "localhost"
$env:REDIS_PORT = "6379"
$env:REDIS_PASSWORD = "redis123"
$env:BACKEND_API_URL = "http://localhost:8080"
$workerProcess = Start-Process -FilePath "cmd" -ArgumentList "/k", "cd /d $($PSScriptRoot)\python-worker && python worker.py" -WindowStyle Normal -PassThru
Start-Sleep -Seconds 5
Write-Host "[OK] Worker 已启动 (新窗口)" -ForegroundColor Green
Write-Host ""

# 启动 Vue 前端
Write-Host "[4/4] 正在启动 Vue 前端..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\fronted"
if (-not (Test-Path "node_modules")) {
    Write-Host "[信息] 首次运行，正在安装前端依赖..." -ForegroundColor Yellow
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[错误] 前端依赖安装失败" -ForegroundColor Red
        exit 1
    }
}
$frontendProcess = Start-Process -FilePath "cmd" -ArgumentList "/k", "npm run dev" -WindowStyle Normal -PassThru
Set-Location $PSScriptRoot
Start-Sleep -Seconds 5
Write-Host "[OK] 前端已启动 (新窗口)" -ForegroundColor Green
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "所有服务已启动！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "服务列表:" -ForegroundColor White
Write-Host "  - 前端: http://localhost:5173" -ForegroundColor Cyan
Write-Host "  - 后端: http://localhost:8080" -ForegroundColor Cyan
Write-Host "  - 数据库: localhost:5432 (PostgreSQL)" -ForegroundColor Cyan
Write-Host "  - 缓存: localhost:6379 (Redis)" -ForegroundColor Cyan
Write-Host ""
Write-Host "默认登录:" -ForegroundColor White
Write-Host "  用户名: admin" -ForegroundColor Cyan
Write-Host "  密码: admin123" -ForegroundColor Cyan
Write-Host ""
Write-Host "注意: 已打开 3 个新窗口分别运行后端、Worker 和前端" -ForegroundColor Yellow
Write-Host "      请勿关闭这些窗口" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

Read-Host "按 Enter 键继续"
