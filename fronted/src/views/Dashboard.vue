<template>
  <div class="dashboard-container">
    <div class="dashboard-content">
      <div class="welcome-section">
        <h1>🎯 智能文档提取</h1>
        <p>上传PDF文档，AI自动提取您需要的关键指标</p>
      </div>

      <!-- 上传区域 -->
      <div class="upload-section">
        <div
          class="upload-area"
          :class="{ dragover }"
          @dragover.prevent="handleDragOver"
          @dragleave.prevent="handleDragLeave"
          @drop.prevent="handleDrop"
          @click="triggerFileInput"
        >
          <div class="upload-icon">
            <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#667eea" stroke-width="1.5">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
          </div>
          <p class="upload-text">拖拽文件到此处或点击上传</p>
          <p class="upload-hint">支持 PDF、JPG、PNG 格式，最大 100MB，可同时上传多个文件</p>
          <input
            type="file"
            ref="fileInput"
            accept=".pdf,.jpg,.jpeg,.png"
            multiple
            style="display: none"
            @change="handleFileSelect"
          />
        </div>

        <!-- 文件列表 -->
        <div v-if="selectedFiles.length > 0" class="file-list">
          <div v-for="(file, index) in selectedFiles" :key="index" class="file-info">
            <div class="file-icon">{{ getFileIcon(file.name) }}</div>
            <div class="file-details">
              <p class="file-name">{{ file.name }}</p>
              <p class="file-size">{{ formatFileSize(file.size) }}</p>
            </div>
            <button @click="removeFile(index)" class="remove-file">×</button>
          </div>
        </div>
      </div>

      <!-- 任务配置 -->
      <div class="config-section">
        <h3>任务配置</h3>

        <div class="form-group">
          <label for="taskName">任务名称</label>
          <input
            id="taskName"
            v-model="taskName"
            type="text"
            class="form-input"
            placeholder="请输入任务名称"
          />
        </div>

        <!-- 模型模式选择 -->
        <div class="form-group">
          <label>模型模式</label>
          <div class="model-mode-selector">
            <button 
              class="mode-btn" 
              :class="{ active: modelMode === 'normal' }"
              @click="modelMode = 'normal'"
            >
              <span class="mode-icon">⚡</span>
              <span class="mode-text">
                <span class="mode-title">普通版</span>
                <span class="mode-desc">智能路由 (qwen3-vl-plus / qwen-long)</span>
              </span>
            </button>
            <button 
              class="mode-btn pro" 
              :class="{ active: modelMode === 'pro' }"
              @click="modelMode = 'pro'"
            >
              <span class="mode-icon">🚀</span>
              <span class="mode-text">
                <span class="mode-title">专业版</span>
                <span class="mode-desc">更强推理 (qwen3.5-plus, 991K上下文)</span>
              </span>
            </button>
            <button 
              class="mode-btn local" 
              :class="{ active: modelMode === 'local' }"
              @click="modelMode = 'local'"
            >
              <span class="mode-icon">🖥️</span>
              <span class="mode-text">
                <span class="mode-title">本地模型</span>
                <span class="mode-desc">私有部署 (OpenAI 兼容 API)</span>
              </span>
            </button>
          </div>
        </div>

        <div class="form-group">
          <label>提取字段配置</label>
          <div class="extract-fields">
            <div v-for="(field, index) in extractFields" :key="index" class="field-row">
              <input
                v-model="field.name"
                type="text"
                class="field-input"
                placeholder="字段名称（如：熔点、沸点）"
              />
              <input
                v-model="field.description"
                type="text"
                class="field-input"
                placeholder="字段描述（如：物质熔化时的温度）"
              />
              <button
                v-if="extractFields.length > 1"
                @click="removeField(index)"
                class="remove-field-btn"
              >
                ×
              </button>
            </div>
            <button @click="addField" class="add-field-btn">
              + 添加字段
            </button>
          </div>
        </div>

        <div class="form-group">
          <label>推理参数</label>
          <div class="inference-config">
            <div class="config-grid">
              <div class="config-item">
                <label for="temperature">Temperature</label>
                <input
                  id="temperature"
                  v-model.number="inferenceConfig.temperature"
                  type="number"
                  min="0"
                  max="2"
                  step="0.1"
                  class="form-input"
                />
              </div>
              <div class="config-item">
                <label for="topP">Top P</label>
                <input
                  id="topP"
                  v-model.number="inferenceConfig.topP"
                  type="number"
                  min="0"
                  max="1"
                  step="0.05"
                  class="form-input"
                />
              </div>
              <div class="config-item">
                <label for="topK">Top K</label>
                <input
                  id="topK"
                  v-model.number="inferenceConfig.topK"
                  type="number"
                  min="1"
                  step="1"
                  class="form-input"
                />
              </div>
              <div class="config-item">
                <label for="maxTokens">Max Tokens</label>
                <input
                  id="maxTokens"
                  v-model.number="inferenceConfig.maxTokens"
                  type="number"
                  min="128"
                  step="128"
                  class="form-input"
                />
              </div>
            </div>
            <label class="checkbox-row">
              <input
                v-model="inferenceConfig.useImages"
                type="checkbox"
              />
              <span>本地模型允许传入图片</span>
            </label>
            <p class="config-hint">
              普通版和专业版会使用 `temperature / top_p / top_k`；本地模型还会使用 `max_tokens` 和 `use_images`。
            </p>
          </div>
        </div>

        <button
          @click="submitTask"
          class="submit-button"
          :disabled="selectedFiles.length === 0 || !taskName || uploading"
        >
          {{ uploading ? '上传中...' : `开始提取 (${selectedFiles.length} 个文件)` }}
        </button>
      </div>

      <!-- 消息提示 -->
      <div v-if="message" class="message" :class="messageType">
        {{ message }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { taskApi } from '../api'

const router = useRouter()

// 响应式数据
const dragover = ref(false)
const selectedFiles = ref([])
const fileInput = ref(null)
const taskName = ref('')
const modelMode = ref('normal')  // 默认普通版
const uploading = ref(false)
const message = ref('')
const messageType = ref('')

// 提取字段配置
const extractFields = ref([
  { name: '名称', description: '物质或化合物的名称' },
  { name: '熔点', description: '物质熔化时的温度' },
  { name: '沸点', description: '物质沸腾时的温度' }
])
const inferenceConfig = ref({
  temperature: 0,
  topP: 1,
  topK: 20,
  maxTokens: 4096,
  useImages: true
})

// 拖拽事件处理
const handleDragOver = () => {
  dragover.value = true
}

const handleDragLeave = () => {
  dragover.value = false
}

const handleDrop = (event) => {
  dragover.value = false
  const allowedExtensions = ['.pdf', '.jpg', '.jpeg', '.png']
  const files = Array.from(event.dataTransfer.files).filter(f => {
    const ext = f.name.toLowerCase().substring(f.name.lastIndexOf('.'))
    return allowedExtensions.includes(ext)
  })
  if (files.length > 0) {
    addFiles(files)
  }
}

// 文件选择处理
const triggerFileInput = () => {
  fileInput.value.click()
}

const handleFileSelect = (event) => {
  const allowedExtensions = ['.pdf', '.jpg', '.jpeg', '.png']
  const files = Array.from(event.target.files).filter(f => {
    const ext = f.name.toLowerCase().substring(f.name.lastIndexOf('.'))
    return allowedExtensions.includes(ext)
  })
  if (files.length > 0) {
    addFiles(files)
  }
}

// 添加文件
const addFiles = (files) => {
  const validFiles = files.filter(file => {
    if (file.size > 100 * 1024 * 1024) {
      showMessage(`文件 ${file.name} 大小超过 100MB，已跳过`, 'error')
      return false
    }
    return true
  })

  selectedFiles.value.push(...validFiles)

  if (selectedFiles.value.length > 0 && !taskName.value) {
    // 移除文件扩展名作为任务名称
    const firstName = validFiles[0].name
    const lastDotIndex = firstName.lastIndexOf('.')
    taskName.value = lastDotIndex > 0 ? firstName.substring(0, lastDotIndex) : firstName
  }

  showMessage(`已添加 ${validFiles.length} 个文件`, 'success')
}

// 移除文件
const removeFile = (index) => {
  selectedFiles.value.splice(index, 1)
  if (selectedFiles.value.length === 0) {
    fileInput.value.value = ''
  }
}

// 添加字段
const addField = () => {
  extractFields.value.push({ name: '', description: '' })
}

// 移除字段
const removeField = (index) => {
  if (extractFields.value.length > 1) {
    extractFields.value.splice(index, 1)
  } else {
    showMessage('至少需要保留一个提取字段', 'error')
  }
}

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

// 获取文件图标
const getFileIcon = (filename) => {
  const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'))
  if (ext === '.pdf') return '📄'
  if (ext === '.jpg' || ext === '.jpeg') return '🖼️'
  if (ext === '.png') return '🖼️'
  return '📄'
}

// 提交任务
const submitTask = async () => {
  try {
    uploading.value = true
    showMessage('', '')

    // 验证
    if (selectedFiles.value.length === 0) {
      showMessage('请先选择文件', 'error')
      return
    }

    if (!taskName.value.trim()) {
      showMessage('请输入任务名称', 'error')
      return
    }

    // 准备表单数据
    const formData = new FormData()
    formData.append('taskName', taskName.value.trim())

    const user = JSON.parse(localStorage.getItem('user') || '{}')
    if (!user.userId) {
      showMessage('请先登录', 'error')
      setTimeout(() => router.push('/login'), 1500)
      return
    }
    formData.append('userId', user.userId)

    // 将提取字段转换为JSON字符串
    const fieldsJson = extractFields.value.map(f => ({
      name: f.name.trim(),
      description: f.description.trim()
    }))
    formData.append('extractFields', JSON.stringify(fieldsJson))
    
    // 添加模型模式
    formData.append('modelMode', modelMode.value)
    formData.append('inferenceConfig', JSON.stringify({
      temperature: Number(inferenceConfig.value.temperature),
      topP: Number(inferenceConfig.value.topP),
      topK: Number(inferenceConfig.value.topK),
      maxTokens: Number(inferenceConfig.value.maxTokens),
      useImages: Boolean(inferenceConfig.value.useImages)
    }))

    // 添加所有文件
    selectedFiles.value.forEach((file, index) => {
      formData.append('files', file)
    })

    // 发送请求
    const response = await taskApi.createTask(formData)

    if (response.code === 200) {
      showMessage(`批量任务创建成功！共 ${response.data.length} 个任务正在处理...`, 'success')

      // 2秒后跳转到任务列表
      setTimeout(() => {
        router.push('/tasks')
      }, 2000)
    } else {
      showMessage(response.message || '任务创建失败', 'error')
    }
  } catch (err) {
    console.error('创建任务失败:', err)
    showMessage(err.response?.data?.message || '创建任务失败，请稍后重试', 'error')
  } finally {
    uploading.value = false
  }
}

// 显示消息
const showMessage = (text, type = 'success') => {
  message.value = text
  messageType.value = type

  if (text) {
    setTimeout(() => {
      message.value = ''
    }, 5000)
  }
}
</script>

<style scoped>
.dashboard-container {
  width: 100%;
  height: 100%;
}

.dashboard-content {
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 欢迎区域 */
.welcome-section {
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e2e8f0;

  h1 {
    margin: 0 0 0.3rem 0;
    color: #2d3748;
    font-size: 1.5rem;
    font-weight: 700;
  }

  p {
    margin: 0;
    color: #718096;
    font-size: 0.95rem;
  }
}

/* 上传区域 */
.upload-section {
  margin-bottom: 1.5rem;
  flex: 1;
}

.upload-area {
  border: 2px dashed #cbd5e0;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #f7fafc;
  height: 180px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;

  &:hover {
    border-color: #4299e1;
    background: #ebf8ff;
  }

  &.dragover {
    border-color: #4299e1;
    background: #e6fffa;
    transform: scale(1.01);
  }

  .upload-icon {
    margin-bottom: 1rem;
    color: #4299e1;
  }

  .upload-text {
    font-size: 1rem;
    color: #2d3748;
    margin: 0 0 0.3rem 0;
    font-weight: 500;
  }

  .upload-hint {
    font-size: 0.85rem;
    color: #a0aec0;
    margin: 0;
  }
}

/* 文件列表 */
.file-list {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 0.5rem;
  background: white;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.8rem;
  background: #ebf8ff;
  border-radius: 6px;
  border: 1px solid #bee3f8;

  .file-icon {
    font-size: 1.5rem;
  }

  .file-details {
    flex: 1;

    .file-name {
      margin: 0 0 0.2rem 0;
      color: #2d3748;
      font-weight: 500;
      font-size: 0.9rem;
      word-break: break-all;
    }

    .file-size {
      margin: 0;
      color: #718096;
      font-size: 0.8rem;
    }
  }

  .remove-file {
    width: 28px;
    height: 28px;
    border: none;
    background: #fc8181;
    color: white;
    border-radius: 50%;
    font-size: 1rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.3s;

    &:hover {
      background: #f56565;
      transform: scale(1.05);
    }
  }
}

/* 配置区域 */
.config-section {
  flex: 2;
  background: #f7fafc;
  padding: 1.5rem;
  border-radius: 8px;
  border: 1px solid #e2e8f0;

  h3 {
    margin: 0 0 1.2rem 0;
    color: #2d3748;
    font-size: 1.1rem;
    font-weight: 600;
  }
}

/* 表单组 */
.form-group {
  margin-bottom: 1.2rem;

  label {
    display: block;
    margin-bottom: 0.4rem;
    color: #4a5568;
    font-weight: 500;
    font-size: 0.9rem;
  }

  .form-input {
    width: 100%;
    padding: 0.7rem;
    border: 1px solid #cbd5e0;
    border-radius: 4px;
    font-size: 0.95rem;
    transition: all 0.3s;
    background: white;

    &:focus {
      outline: none;
      border-color: #4299e1;
      box-shadow: 0 0 0 2px rgba(66, 153, 225, 0.2);
    }

    &:disabled {
      background: #edf2f7;
      cursor: not-allowed;
      color: #a0aec0;
    }
  }
}

/* 提取字段 */
.extract-fields {
  display: flex;
  flex-direction: column;
  gap: 0.8rem;
  margin-bottom: 1.5rem;
}

.inference-config {
  padding: 1rem;
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.8rem;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;

  label {
    margin: 0;
    font-size: 0.85rem;
    color: #4a5568;
    font-weight: 500;
  }
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.9rem;
  color: #2d3748;
  font-size: 0.9rem;
}

.config-hint {
  margin: 0.7rem 0 0 0;
  font-size: 0.8rem;
  color: #718096;
}

/* 模型模式选择器 */
.model-mode-selector {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
}

.mode-btn {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 1rem;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  background: white;
  cursor: pointer;
  transition: all 0.3s;
  text-align: left;

  &:hover {
    border-color: #cbd5e0;
    background: #f7fafc;
  }

  &.active {
    border-color: #4299e1;
    background: #ebf8ff;
    box-shadow: 0 0 0 3px rgba(66, 153, 225, 0.2);
  }

  &.pro.active {
    border-color: #9f7aea;
    background: #faf5ff;
    box-shadow: 0 0 0 3px rgba(159, 122, 234, 0.2);
  }

  &.local.active {
    border-color: #38a169;
    background: #f0fff4;
    box-shadow: 0 0 0 3px rgba(56, 161, 105, 0.2);
  }
}

.mode-icon {
  font-size: 1.5rem;
}

.mode-text {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.mode-title {
  font-weight: 600;
  font-size: 0.95rem;
  color: #2d3748;
}

.mode-desc {
  font-size: 0.8rem;
  color: #718096;
}

.field-row {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;

  .field-input {
    flex: 1;
    padding: 0.7rem;
    border: 1px solid #cbd5e0;
    border-radius: 4px;
    font-size: 0.9rem;
    transition: all 0.3s;

    &:focus {
      outline: none;
      border-color: #4299e1;
      box-shadow: 0 0 0 2px rgba(66, 153, 225, 0.2);
    }
  }

  .remove-field-btn {
    width: 36px;
    height: 36px;
    border: none;
    background: #fc8181;
    color: white;
    border-radius: 4px;
    font-size: 1.1rem;
    cursor: pointer;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    justify-content: center;

    &:hover {
      background: #f56565;
    }
  }
}

.add-field-btn {
  padding: 0.5rem 1rem;
  background: white;
  border: 1px solid #4299e1;
  color: #4299e1;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 0.9rem;
  font-weight: 500;
  align-self: flex-start;

  &:hover {
    background: #4299e1;
    color: white;
  }
}

/* 提交按钮 */
.submit-button {
  width: 200px;
  padding: 0.8rem;
  background: linear-gradient(90deg, #3182ce 0%, #2b6cb0 100%);
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
    background: linear-gradient(90deg, #2b6cb0 0%, #2c5282 100%);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }
}

/* 消息提示 */
.message {
  padding: 0.8rem;
  border-radius: 4px;
  margin-top: 1rem;
  font-size: 0.9rem;
  font-weight: 500;
  border-left: 3px solid;

  &.success {
    background: #f0fff4;
    color: #22543d;
    border-left-color: #38a169;
  }

  &.error {
    background: #fff5f5;
    color: #742a2a;
    border-left-color: #e53e3e;
  }
}
</style>
