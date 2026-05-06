# 基于通义千问大模型的智能指标提取智能体

基于 Spring Boot + Vue 3 + 通义千问大模型的智能指标提取智能体，支持 PDF/图片上传、智能路由解析、指标抽取、智能体对话和结果导出。

## 功能特性

- 用户登录认证
- PDF 文档上传 / 批量上传
- AI 智能提取文档指标（基于 MinerU + 通义千问）
- **智能体对话**（同一个 qwen3.6-plus 对话模型，支持普通版/专业版两种策略）
- 普通版 / 专业版两种运行模式，上传提取链路保留用于演示对比
- 异步任务处理（Redis 队列，8 并发）
- JSON / CSV / Excel 结果导出
- 任务状态实时追踪
- 历史任务管理

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Spring Boot 3.2 / PostgreSQL 15 / Redis 7 |
| 前端 | Vue 3 + Vite / Vue Router / Axios |
| AI | MinerU API / qwen3-vl-plus / qwen-long / qwen3.6-plus |

## 项目结构

```
AI_agent_qwen/
├── backend/           # Spring Boot 后端服务 (端口 8080)
├── fronted/           # Vue 3 前端应用 (端口 5173)
├── python-worker/     # Python AI 处理模块
├── docker-compose.yml # Docker 编排 (PostgreSQL + Redis)
├── init-db.sql        # 数据库初始化脚本
└── start_all.bat      # Windows 快速启动脚本
```

## 快速启动

### 1. 配置环境变量

在项目根目录创建 `.env` 文件：

```env
# MinerU API Key
MINERU_API_KEY=your_mineru_api_key_here

# Qwen API Key
QWEN_API_KEY=your_qwen_api_key_here
```

在 `python-worker/` 目录创建 `.env` 文件：

```env
DASHSCOPE_API_KEY=your_dashscope_api_key_here
```

### 2. 启动依赖服务

```bash
docker-compose up -d
```

| 服务 | 地址 |
|------|------|
| PostgreSQL | localhost:5433 |
| Redis | localhost:6380 |

### 3. 启动后端

```bash
cd backend
mvn spring-boot:run
```

后端地址：http://localhost:8080

### 4. 启动前端

```bash
cd fronted
npm install
npm run dev
```

前端地址：http://localhost:5173

### 5. 一键启动（Windows）

```bash
start_all.bat
```

## 默认账户

- 用户名: `admin`
- 密码: `admin123`

## 模型模式

| 模式 | 模型 | 适用场景 |
|------|------|----------|
| 普通版 | qwen3-vl-plus / qwen-long (智能路由) | 常规文档，性价比高 |
| 专业版 | qwen3-vl-plus 筛图 + qwen3.6-plus 提取 | 复杂推理，高精度 |

## 智能体对话模式

| 对话模式 | 对话模型 | 回答策略 |
|----------|----------|----------|
| 普通版对话 | qwen3.6-plus | 围绕智能路由、批量效率、普通版提取字段设计进行回答 |
| 专业版对话 | qwen3.6-plus | 围绕前置筛图、图片理解、表格结构化和多组对照完整展开进行回答 |

## 工作流程

```
用户上传 PDF → 后端存储 → Redis 队列 → Python Worker 处理
                                              ↓
                                     MinerU 解析 → Qwen 提取
                                              ↓
用户查看结果 ← 后端返回 ← JSON 输出 → CSV/Excel 导出
```

## 常见问题

**Q: 端口被占用？**
A: 修改 `docker-compose.yml` 中的端口映射，或停止占用端口的进程。

**Q: Python 依赖安装失败？**
A: 建议使用 conda 虚拟环境：
```bash
conda create -n docextract python=3.10
conda activate docextract
pip install -r python-worker/requirements.txt
```

**Q: API 调用失败？**
A: 检查 `.env` 文件中的 API 密钥是否正确配置，确保网络可以访问阿里云服务。

## License

MIT License
