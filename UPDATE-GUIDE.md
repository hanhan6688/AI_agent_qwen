# 文档提取功能优化更新指南

## 更新内容

### 1. 批量PDF上传支持
- ✅ 前端支持多文件选择和拖拽上传
- ✅ 后端支持批量创建任务
- ✅ 每个文件生成独立的任务
- ✅ 统一使用相同的提取字段配置

### 2. 任务ID优化
- ✅ 使用 `时间戳+UUID` 格式作为任务ID
- ✅ 示例：`20260131224530-a1b2c3d4`
- ✅ 支持批量任务的批次ID追踪

### 3. Redis连接修复
- ✅ 统一使用 `.env` 文件中的密码配置
- ✅ 修复Python Worker的Redis认证问题
- ✅ 提供快速修复脚本 `fix-redis.bat`

### 4. 数据库结构更新
- ✅ tasks表主键从 `id` 改为 `task_id`
- ✅ 新增 `batch_id` 字段用于批量任务追踪
- ✅ 新增 `excel_path` 字段直接存储在tasks表

## 快速开始

### 方式一：完整重启（推荐）

如果你希望应用所有更改并重新初始化数据库：

```bash
double-click restart-all.bat
```

这将：
1. 停止所有服务
2. 重新创建数据库（应用新表结构）
3. 启动PostgreSQL和Redis
4. 启动Spring Boot后端
5. 启动Python Worker
6. 启动Vue前端

### 方式二：仅修复Redis连接

如果Redis连接仍然有问题：

```bash
double-click fix-redis.bat
```

### 方式三：手动更新数据库

如果不想重新初始化数据库，可以手动执行SQL：

```sql
-- 备份原表数据（可选）
CREATE TABLE tasks_backup AS SELECT * FROM tasks;

-- 删除原表
drop table if exists tasks;
drop table if exists extract_results;

-- 重新创建表（使用新的init-db.sql）
-- 请复制init-db.sql中的建表语句执行
```

## 批量上传使用说明

### 前端操作
1. 登录系统（http://localhost:5173）
   - 用户名：`admin`
   - 密码：`admin123`

2. 在Dashboard页面：
   - **点击上传区域**选择多个PDF文件，或
   - **拖拽多个PDF文件**到上传区域

3. 配置提取字段（所有文件使用相同配置）

4. 点击"开始提取"按钮

5. 系统将：
   - 为每个PDF创建独立任务
   - 每个任务有唯一的task_id
   - 所有任务共享相同的batch_id
   - 自动跳转到任务列表查看进度

### 任务管理

在任务列表页面可以：
- 查看每个任务的状态
- 查看批量任务的批次ID
- 下载提取结果Excel
- 删除任务

## 配置检查

### Redis配置一致性检查

确保以下文件中的Redis密码一致：

1. **docker-compose.yml**
   ```yaml
   redis:
     command: redis-server --appendonly yes --requirepass redis123
   ```

2. **.env** (项目根目录)
   ```
   REDIS_PASSWORD=redis123
   ```

3. **python-worker/.env**
   ```
   REDIS_PASSWORD=redis123
   ```

4. **backend/src/main/resources/application.yml**
   ```yaml
   spring:
     redis:
       password: redis123
   ```

### API密钥配置

确保以下文件中有正确的API密钥：

1. **.env** (项目根目录)
   ```
   MINERU_API_KEY=your_mineru_api_key_here
   QWEN_API_KEY=your_qwen_api_key_here
   ```

2. **python-worker/.env**
   ```
   MINERU_API_KEY=your_mineru_api_key_here
   QWEN_API_KEY=your_qwen_api_key_here
   ```

## 故障排除

### Redis连接失败

如果仍然出现Redis连接错误：

1. 运行 `fix-redis.bat`
2. 检查Redis容器是否运行：
   ```bash
   docker ps -f name=docextract-redis
   ```
3. 测试Redis连接：
   ```bash
   docker exec docextract-redis redis-cli ping
   ```
4. 检查密码是否正确

### 任务创建失败

1. 检查后端日志：`backend/logs/app.log`
2. 检查Worker日志：`logs/worker.log`
3. 确保文件大小不超过100MB
4. 确保文件格式为PDF

### 批量上传问题

1. 确保所有文件都是PDF格式
2. 检查浏览器控制台是否有JavaScript错误
3. 检查网络连接是否正常
4. 查看任务列表确认任务是否创建成功

## 日志查看

### 后端日志
```bash
type backend\logs\app.log
```

### Python Worker日志
```bash
type logs\worker.log
```

### Redis日志
```bash
docker logs docextract-redis
```

## 性能优化建议

1. **批量上传文件数量**：建议一次上传10-20个文件
2. **文件大小**：单个文件不超过50MB效果更佳
3. **提取字段**：合理配置提取字段，避免过多字段导致AI处理缓慢
4. **Worker数量**：可以启动多个Worker进程提高并发处理能力

## 版本兼容性

本次更新涉及：
- ✅ 前端：Vue 3组件更新
- ✅ 后端：Spring Boot实体和API更新
- ✅ 数据库：表结构变更
- ✅ Python Worker：适配新的task_id格式

**注意**：如果已有生产数据，请先备份再执行更新！
