# 智能文档指标提取系统

基于 Spring Boot + Vue3 + AI 的智能文档指标提取系统，支持 PDF 文档上传、AI 智能提取、异步任务处理和结果导出。

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

## 项目结构

```
AI_agent_qwen/
├── backend/                # Spring Boot 后端
│   ├── src/               # 源代码
│   └── pom.xml            # Maven 配置
├── fronted/               # Vue 3 前端
│   ├── src/               # 源代码
│   └── package.json       # npm 配置
├── python-worker/         # Python AI 处理服务
│   ├── integrated_processor.py    # 集成处理器
│   ├── qwen_process_url_new.py    # Qwen 处理模块
│   └── data_process.py            # 数据处理模块
├── docker-compose.yml     # Docker 编排配置
├── init-db.sql           # 数据库初始化脚本
└── start_all.bat         # Windows 快速启动脚本
```

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
# Windows
copy .env.example .env
copy python-worker\.env.example python-worker\.env
copy fronted\.env.example fronted\.env

# Linux/macOS
cp .env.example .env
cp python-worker/.env.example python-worker/.env
cp fronted/.env.example fronted/.env
```

编辑以下文件，填入 API 密钥：

| 文件 | 说明 |
|------|------|
| `.env` | 填入 `MINERU_API_KEY` 和 `QWEN_API_KEY` |
| `python-worker/.env` | Worker 配置（可选） |
| `fronted/.env` | 前端配置（可选） |


### 启动

**1. 启动 Docker 服务**

```bash
docker-compose up -d
```

**2. 安装 Python 依赖**

```bash
cd python-worker
pip install -r requirements.txt
```

**3. 启动后端服务**

```bash
cd backend
mvn spring-boot:run
```

**4. 启动前端服务**

```bash
cd fronted
npm install
npm run dev
```

## 服务地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| 后端 | http://localhost:8080 |
| PostgreSQL | localhost:5433 |
| Redis | localhost:6380 |

## 默认账户

- 用户名: `admin`
- 密码: `admin123`

## 环境变量说明

### 根目录 `.env`

```env
# MinerU API Key
MINERU_API_KEY=your_mineru_api_key_here

# Qwen API Key
QWEN_API_KEY=your_qwen_api_key_here

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6380
REDIS_PASSWORD=docextract123

# PostgreSQL 配置
DB_HOST=localhost
DB_PORT=5433
DB_NAME=docextract
DB_USER=admin
DB_PASSWORD=password123
```

### Python Worker `.env`

```env
# 通义千问 API
DASHSCOPE_API_KEY=your_dashscope_api_key_here

# OpenAI API（可选）
OPENAI_API_KEY=your_openai_api_key_here

# MinerU API
MINERU_API_KEY=your_mineru_api_key_here
```

## 工作流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  用户上传    │ ──▶ │  后端接收    │ ──▶ │  Redis 队列  │
│   PDF 文档   │     │  存储文件    │     │  异步任务    │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
                                              ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  用户下载    │ ◀── │  后端返回    │ ◀── │ Python AI   │
│  Excel 结果  │     │  提取结果    │     │  智能提取    │
└─────────────┘     └─────────────┘     └─────────────┘
```

## 日志查看

- 后端日志: `backend/logs/`
- Python 日志: 控制台输出

## 常见问题

**Q: Docker 容器启动失败？**

A: 确保端口 5433 和 6380 没有被占用，或修改 `docker-compose.yml` 中的端口映射。

**Q: Python 依赖安装失败？**

A: 建议使用虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

**Q: API 调用失败？**

A: 检查 `.env` 文件中的 API 密钥是否正确配置。

## License

MIT License
