# Python Worker 集成说明

本项目实现了完整的PDF批量上传和AI解析流程，包含以下组件：

## 组件说明

### 1. integrated_processor.py (集成处理器)
**主要入口脚本**，由Java后端调用

**功能：**
- 接收单个PDF文件路径
- 调用MinerU API进行PDF解析（提取文本和图片）
- 下载解析结果（Markdown和图片）
- 调用Qwen3-VL进行信息提取
- 返回结构化JSON数据

**调用方式：**
```bash
python integrated_processor.py <input_json_file> <extract_fields_json>
```

**输入JSON格式：**
```json
{
  "taskId": 123,
  "taskName": "批量处理任务",
  "userId": 1,
  "fileInfo": {
    "fileName": "example.pdf",
    "filePath": "/path/to/uploaded/example.pdf"
  }
}
```

**输出JSON格式：**
```json
{
  "status": "success",
  "message": "处理完成",
  "data": {
    // 提取的字段数据
    "名称": "化合物A",
    "熔点": "85-87°C",
    ...
  },
  "confidence": 0.95,
  "model": "qwen-vl-max-latest",
  "mineru_processed": true
}
```

### 2. data_process.py (MinerU处理器)
**PDF上传和解析模块**

**功能：**
- 批量上传PDF到MinerU平台
- 轮询处理状态
- 下载解析结果（ZIP格式）
- 解压获取Markdown和图片

**主要函数：**
- `upload_batch(file_batch)` - 上传PDF批次
- `wait_until_done(batch_id)` - 等待处理完成
- `fetch_and_download(batch_id, results)` - 下载结果

### 3. qwen_process_url_new.py (Qwen3-VL处理器)
**AI信息提取模块**

**功能：**
- 读取MinerU生成的Markdown文件
- 提取相关图片（Fig/图表）
- 调用Qwen3-VL API进行多模态分析
- 提取结构化数据

**主要函数：**
- `extract_once(md_file)` - 处理单个Markdown文件
- `build_messages(text, img_paths)` - 构建AI请求
- `try_repair_json(json_str)` - 修复JSON格式

## 环境配置

### 1. 环境变量 (.env文件)
```env
# DashScope API Key (用于Qwen3-VL)
DASHSCOPE_API_KEY=your_dashscope_api_key

# MinerU API Key (用于PDF解析)
MINERU_API_KEY=your_mineru_api_key

# OpenAI API Key (备用)
OPENAI_API_KEY=your_openai_api_key
```

### 2. Java后端配置 (application.yml)
```yaml
python:
  worker-dir: ${user.home}/docextract/python-worker  # Python脚本目录
  script-path: integrated_processor.py               # 主处理脚本
  mineru-timeout: 3600                              # MinerU超时时间(秒)
```

## 处理流程

### 完整流程图

```
用户上传PDF
    ↓
Java后端接收文件并创建Task
    ↓
异步调用PythonWorkerService
    ↓
调用 integrated_processor.py
    ↓
├─→ 步骤1: 复制PDF到临时目录
├─→ 步骤2: 调用MinerU API上传PDF
├─→ 步骤3: 轮询等待MinerU处理完成
├─→ 步骤4: 下载解析结果(Markdown+图片)
└─→ 步骤5: 调用Qwen3-VL提取信息
    ↓
返回结构化数据
    ↓
Java后端保存结果并更新Task状态
    ↓
用户查看结果
```

## 使用说明

### 1. 安装依赖

```bash
cd python-worker
pip install -r requirements.txt
```

**requirements.txt:**
```
requests
python-dotenv
dashscope
zipfile
pathlib
typing
```

### 2. 配置API密钥

编辑 `.env` 文件，填入有效的API密钥：
- `MINERU_API_KEY`: 从MinerU官网申请
- `DASHSCOPE_API_KEY`: 从阿里云DashScope申请

### 3. 启动后端服务

```bash
# 确保PostgreSQL和Redis已启动
docker-compose up -d

# 启动Spring Boot后端
./gradlew bootRun
```

### 4. 调用API上传PDF

**API端点:** `POST /api/tasks`

**请求示例:**
```bash
curl -X POST http://localhost:8080/api/tasks \
  -F "userId=1" \
  -F "taskName=批量提取测试" \
  -F "extractFields={\"名称\":\"\",\"熔点\":\"\",\"沸点\":\"\"}" \
  -F "files=@/path/to/document1.pdf" \
  -F "files=@/path/to/document2.pdf"
```

**响应示例:**
```json
{
  "code": 200,
  "message": "任务创建成功",
  "data": [
    {
      "taskId": 1,
      "taskName": "批量提取测试 - document1.pdf",
      "status": "PENDING",
      "statusText": "等待处理"
    }
  ]
}
```

### 5. 查询任务状态

```bash
# 查询单个任务状态
curl http://localhost:8080/api/tasks/1/status

# 查询任务详情
curl http://localhost:8080/api/tasks/1

# 查询用户任务列表
curl "http://localhost:8080/api/tasks?userId=1&page=0&size=10"
```

## 错误处理

### 常见错误及解决方案

#### 1. MinerU API密钥无效
```
错误: RuntimeError: HTTP错误: 401
解决: 检查MINERU_API_KEY是否有效，重新申请API密钥
```

#### 2. DashScope API密钥无效
```
错误: API错误: Invalid API key
解决: 检查DASHSCOPE_API_KEY是否有效，确保账户有足够额度
```

#### 3. 处理超时
```
错误: Python脚本执行超时 (3600秒)
解决: 
- 增加application.yml中的mineru-timeout配置
- 检查PDF文件是否过大
- 检查网络连接
```

#### 4. 图片提取失败
```
警告: 未找到带Fig.描述的图片
说明: PDF中没有包含Fig/图表，或格式不符合预期，将尝试提取所有图片
```

## 性能优化建议

### 1. 批量处理优化
- 修改 `data_process.py` 中的 `BATCH_SIZE` (默认200)
- 根据API限制和网络状况调整

### 2. 并发控制
- 修改 `qwen_process_url_new.py` 中的 `max_workers` (默认3)
- 控制同时处理的线程数，避免API限流

### 3. Token限制
- 修改 `MAX_TPM` (Token per Minute) 配置
- 根据DashScope账户额度调整

### 4. 图片数量限制
- 修改 `MAX_IMAGES` (默认15)
- 控制每篇论文处理的图片数量

## 日志和调试

### 日志位置
- Java后端: `backend/logs/`
- Python脚本: 控制台输出和日志文件

### 调试模式
在 `application.yml` 中设置日志级别:
```yaml
logging:
  level:
    com.docextract: DEBUG
    com.docextract.service.PythonWorkerService: DEBUG
```

### 常见问题排查
1. **任务一直显示"处理中"**
   - 检查Python进程是否在运行
   - 查看日志是否有错误
   - 检查MinerU API状态

2. **提取结果为空**
   - 检查PDF是否为扫描件（需要OCR）
   - 检查图片是否包含Fig/图表
   - 查看Qwen3-VL返回的原始响应

3. **JSON解析失败**
   - 查看原始输出格式
   - 检查 `try_repair_json` 函数的修复逻辑

## 安全注意事项

1. **API密钥保护**
   - 不要将 `.env` 文件提交到Git
   - 使用环境变量或安全配置中心

2. **文件上传安全**
   - 后端已限制文件大小 (100MB)
   - 检查文件类型（只允许PDF）

3. **临时文件清理**
   - integrated_processor.py会自动清理临时文件
   - 确保有足够的磁盘空间

## 扩展功能

### 1. 支持更多文件格式
修改 `FileController.java` 支持更多格式:
```java
// 在upload方法中添加格式检查
String contentType = file.getContentType();
if (!"application/pdf".equals(contentType)) {
    throw new RuntimeException("只支持PDF文件");
}
```

### 2. 自定义提取字段
前端可以动态配置提取字段:
```json
{
  "extractFields": {
    "化合物名称": "",
    "分子式": "",
    "CAS号": "",
    "熔点": "",
    "沸点": "",
    "溶解性": ""
  }
}
```

### 3. 结果导出
添加API导出结果为Excel/CSV格式:
```java
@GetMapping("/{taskId}/export")
public ResponseEntity<byte[]> exportResult(@PathVariable Long taskId) {
    // 实现导出逻辑
}
```

## 版本更新记录

### v1.0.0 (2026-02-12)
- 初始版本
- 集成MinerU和Qwen3-VL
- 支持批量PDF处理
- 异步任务处理
- 完整的API接口
