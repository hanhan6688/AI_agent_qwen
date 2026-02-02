# 文档智能提取系统

基于 Spring Boot + Vue3 + AI 的智能文档指标提取系统

## 功能特性

- 用户登录认证
- PDF 文档上传
- AI 智能提取文档指标（基于 MinerU + Qwen3-VL）
- 异步任务处理（Redis 队列）
- Excel 结果导出
- 任务状态实时追踪
- 历史任务管理

## 技术栈

### 后端
- Spring Boot 3.2
- PostgreSQL 15
- Redis 7
- Spring Data JPA
- Apache POI

### 前端
- Vue 3
- Vite
- Vue Router
- Axios

### AI 处理
- MinerU API（PDF 转 Markdown）
- Qwen3-VL（智能提取）

## 快速启动

### 前提条件

确保已安装：
- Docker 和 Docker Compose
- Node.js 18+
- Java 17+
- Python 3.8+

### 配置环境变量

复制环境变量模板：
```bash
cp .env.example .env
cp python-worker/.env.example python-worker/.env 2>nul
cp fronted/.env.example fronted/.env 2>nul
```

编辑以下文件，填入 API 密钥：
- `.env` - 填入 MINERU_API_KEY 和 QWEN_API_KEY
- `python-worker/.env` - Worker 配置（可选）
- `fronted/.env` - 前端配置（可选）

### 启动所有服务

#### 方法一：使用统一启动脚本（推荐）

双击运行 `start-all.bat` 或 `start-all.ps1`，脚本将自动：
1. 启动 PostgreSQL 和 Redis (Docker)
2. 启动 Spring Boot 后端
3. 启动 Python Worker
4. 启动 Vue 前端

#### 方法二：手动启动

1. 启动 Docker 服务：
```bash
docker-compose up -d postgres redis
```

2. 启动后端：
```bash
cd backend
mvn spring-boot:run
```

3. 启动 Worker（新终端）：
```bash
cd python-worker
set REDIS_HOST=localhost
set REDIS_PORT=6379
set REDIS_PASSWORD=redis123
set BACKEND_API_URL=http://localhost:8080
python worker.py
```

4. 启动前端（新终端）：
```bash
cd fronted
npm install
npm run dev
```

### 访问系统

打开浏览器访问：http://localhost:5173

默认登录账号：
- 用户名: `admin`
- 密码: `admin123`

## 项目结构

```
BiShe/
├── backend/              # Spring Boot 后端
├── fronted/              # Vue3 前端
├── python-worker/        # Python Worker
├── data/                # 数据存储目录
│   ├── uploads/         # 上传文件
│   ├── processed/       # 处理后的文件
│   └── excel/           # 生成的 Excel
├── docker-compose.yml   # Docker 编排
├── init-db.sql         # 数据库初始化脚本
├── start-all.bat       # 统一启动脚本（Windows）
├── start-all.ps1       # 统一启动脚本（PowerShell）
└── .env.example        # 环境变量模板
```

## 核心流程

1. 用户登录系统
2. 上传 PDF 文件并配置提取字段
3. 后端创建任务并加入 Redis 队列
4. Python Worker 处理任务：
   - 调用 MinerU API 将 PDF 转为 Markdown
   - 调用 Qwen3-VL 从 Markdown 提取数据
   - 生成 Excel 文件
5. 更新任务状态，用户下载 Excel 结果

## 常见问题

### 1. Docker 容器启动失败
检查端口是否被占用：
- 5432: PostgreSQL
- 6379: Redis

### 2. Python Worker 处理失败
检查：
- MinerU API Key 是否正确配置
- Qwen API Key 是否正确配置
- Redis 连接是否正常

### 3. 前端无法连接后端
检查：
- 后端是否正常启动（http://localhost:8080）
- 前端 `.env` 配置

## 开发调试

### 单独启动服务

后端：
```bash
cd backend && mvn spring-boot:run
```

前端：
```bash
cd fronted && npm run dev
```

Worker：
```bash
cd python-worker && python worker.py
```

Docker 数据库：
```bash
docker-compose up -d postgres redis
```

## 许可证

MIT License
