<template>
  <div class="dashboard-container">
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>

    <div class="dashboard-content">
      <section class="hero-section">
        <div class="hero-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
        </div>
        <div class="hero-text">
          <h1>智能指标提取智能体</h1>
          <p>上传 PDF 或图片后，智能体会调用 MinerU 解析文档，再按普通版或专业版链路完成指标抽取，便于演示两种通义千问方案的差异。</p>
        </div>
      </section>

      <section class="panel upload-panel">
        <div
          class="upload-area"
          :class="{ dragover }"
          @dragover.prevent="handleDragOver"
          @dragleave.prevent="handleDragLeave"
          @drop.prevent="handleDrop"
          @click="triggerFileInput"
        >
          <div class="upload-icon">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </div>
          <p class="upload-title">拖拽文件到这里，或者点击上传</p>
          <p class="upload-hint">支持 PDF、JPG、JPEG、PNG，单个文件最大 100MB，可批量上传。</p>
          <input
            ref="fileInput"
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            multiple
            class="hidden-input"
            @change="handleFileSelect"
          />
        </div>

        <div v-if="selectedFiles.length > 0" class="file-list">
          <div v-for="(file, index) in selectedFiles" :key="`${file.name}-${index}`" class="file-card">
            <div class="file-meta">
              <span class="file-badge">{{ getFileIcon(file.name) }}</span>
              <div>
                <p class="file-name">{{ file.name }}</p>
                <p class="file-size">{{ formatFileSize(file.size) }}</p>
              </div>
            </div>
            <button class="ghost-danger-btn" @click.stop="removeFile(index)">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>
      </section>

      <section class="panel config-panel">
        <div class="section-header">
          <h2>任务配置</h2>
          <p>先选择智能体运行链路，再决定是用结构化字段，还是直接用自然语言提示词驱动提取。</p>
        </div>

        <div class="form-group">
          <label for="taskName">任务名称</label>
          <div class="input-wrapper" :class="{ focused: taskNameFocused }">
            <input
              id="taskName"
              v-model="taskName"
              type="text"
              class="form-input"
              placeholder=" "
              @focus="taskNameFocused = true"
              @blur="taskNameFocused = false"
            />
            <label for="taskName" class="input-label">例如：钙钛矿材料论文批量抽取</label>
          </div>
        </div>

        <div class="form-group">
          <label>智能体运行模式</label>
          <div class="mode-grid">
            <button
              class="mode-card"
              :class="{ active: modelMode === 'normal' }"
              @click="modelMode = 'normal'"
            >
              <span class="mode-tag">标准</span>
              <strong>普通版</strong>
              <span>智能路由：无图片输入走 `qwen-long`，有图片输入走 `qwen3.6-plus`，不做前置筛图。</span>
            </button>
            <button
              class="mode-card pro"
              :class="{ active: modelMode === 'pro' }"
              @click="modelMode = 'pro'"
            >
              <span class="mode-tag pro">增强</span>
              <strong>专业版</strong>
              <span>先用 `qwen3-vl-plus` 筛图、理解图片和结构化表格，再交给 `qwen3.6-plus` 统一抽取。</span>
            </button>
          </div>
        </div>

        <div class="form-group">
          <label>提取方式</label>
          <div class="mode-grid prompt-grid">
            <button
              class="mode-card prompt"
              :class="{ active: promptMode === 'fields' }"
              @click="promptMode = 'fields'"
            >
              <span class="mode-tag">结构化</span>
              <strong>字段配置</strong>
              <span>按"字段名 + 说明"生成系统内置提示词，适合固定格式指标抽取。</span>
            </button>
            <button
              class="mode-card prompt natural"
              :class="{ active: promptMode === 'natural' }"
              @click="promptMode = 'natural'"
            >
              <span class="mode-tag natural">自由输入</span>
              <strong>自然语言提示词</strong>
              <span>直接使用你输入的 prompt，完全替代当前内置提示词。</span>
            </button>
          </div>
        </div>

        <div v-if="promptMode === 'fields'" class="section-card">
          <div class="card-header">
            <div>
              <h3>字段配置</h3>
              <p>这一模式会把下列字段自动组装成 prompt，适合你已经明确知道要抽哪些指标的场景。</p>
            </div>
            <button class="secondary-btn" @click="addField">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              新增字段
            </button>
          </div>

          <div class="field-table">
            <div class="field-table-head">
              <span>字段名</span>
              <span>字段说明</span>
              <span>操作</span>
            </div>
            <div v-for="(field, index) in extractFields" :key="`field-${index}`" class="field-row">
              <input
                v-model="field.name"
                type="text"
                class="form-input"
                placeholder="例如：annealing_temp"
              />
              <input
                v-model="field.description"
                type="text"
                class="form-input"
                placeholder="例如：退火温度，无则填 NA"
              />
              <button
                class="ghost-danger-btn compact"
                :disabled="extractFields.length === 1"
                @click="removeField(index)"
              >
                删除
              </button>
            </div>
          </div>
        </div>

        <div v-else class="section-card prompt-card">
          <div class="card-header">
            <div>
              <h3>自然语言提示词</h3>
              <p>启用后将直接把你输入的 prompt 发送给模型，当前字段配置不再参与内置提示词生成。</p>
            </div>
            <div class="action-row">
              <button class="secondary-btn" @click="fillSamplePrompt">填入示例</button>
              <button class="ghost-btn" @click="clearCustomPrompt">清空</button>
            </div>
          </div>

          <textarea
            v-model="customPrompt"
            class="prompt-textarea"
            rows="9"
            placeholder="请输入自然语言提示词，例如：请从这篇材料学 PDF 论文中提取关键指标并输出 JSON。"
          />

          <p class="prompt-hint">
            建议把输出格式、字段要求、缺失值处理规则都写清楚，例如"无则填 NA""作者数量输出数字""仅返回 JSON"。
          </p>
        </div>

        <div class="section-card">
          <div class="card-header">
            <div>
              <h3>推理参数</h3>
              <p>普通版和专业版会使用 `temperature / top_p / top_k / max_tokens`，默认 temperature 为 0，便于稳定复现。</p>
            </div>
          </div>

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

        </div>

        <div class="submit-row">
          <button
            class="submit-button"
            :disabled="selectedFiles.length === 0 || !taskName.trim() || uploading"
            @click="submitTask"
          >
            <span class="button-text">{{ uploading ? '提交中...' : `开始提取（${selectedFiles.length} 个文件）` }}</span>
            <span class="button-loader" v-if="uploading"></span>
          </button>
        </div>
      </section>

      <transition name="fade">
        <div v-if="message" class="message" :class="messageType">
          <svg v-if="messageType === 'success'" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {{ message }}
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { taskApi } from '../api'

const router = useRouter()

const DEFAULT_EXTRACT_FIELDS = [
  { name: 'title', description: '文档主标题' },
  { name: 'subtitle', description: '副标题、章节标题或分组标题，没有则填NA' },
  { name: 'mult-data[].content', description: '每组对比数据的核心内容摘要' },
  { name: 'mult-data[].image', description: '对应图片标识、图片名或图片链接，没有则填NA' },
  { name: 'mult-data[].url', description: '对应来源链接，没有则填NA' }
]

const DEFAULT_CUSTOM_PROMPT = `你是一个专业的文档信息提取助手。请从提供的图文信息中根据指标信息提取内容，并严格按 JSON 格式输出。

如果文档只有单组结果，请返回一个 JSON 对象。
如果文档包含多组并列或对比数据，请返回 JSON 数组，并严格使用以下结构：
[
  {
    "title": "标题1",
    "subtitle": "副标题1",
    "mult-data": [
      {
        "content": "内容1",
        "image": "图片1",
        "url": "链接1"
      },
      {
        "content": "内容2",
        "image": "图片2",
        "url": "链接2"
      }
    ]
  }
]

要求：
1. 仅输出合法 JSON，不要输出解释、注释或 Markdown。
2. 缺失信息统一填写 "NA"。
3. "mult-data" 中的 "content" 放核心内容，"image" 放对应图片标识或图片链接，"url" 放来源链接。
4. 尽量保留原文中的单位、符号、英文大小写和编号。
5. 如果来源内容包含表格，请尽量把每一行都展开成一个 "mult-data" 条目，不要只做摘要。
6. 表格行展开时，"content" 尽量保留该行所有列名和值，例如 "样品=A; 温度=300 K; 性能=12.5%"。
7. 如果表格中有单位、脚注、行表头、列分组或测试条件，请合并进对应行的 "content"，保证多组对照关系完整。`

const dragover = ref(false)
const selectedFiles = ref([])
const fileInput = ref(null)
const taskName = ref('')
const taskNameFocused = ref(false)
const modelMode = ref('normal')
const promptMode = ref('fields')
const customPrompt = ref(DEFAULT_CUSTOM_PROMPT)
const uploading = ref(false)
const message = ref('')
const messageType = ref('')

const extractFields = ref(DEFAULT_EXTRACT_FIELDS.map(field => ({ ...field })))
const inferenceConfig = ref({
  temperature: 0,
  topP: 1,
  topK: 1,
  maxTokens: 4096
})

const handleDragOver = () => {
  dragover.value = true
}

const handleDragLeave = () => {
  dragover.value = false
}

const handleDrop = (event) => {
  dragover.value = false
  const files = Array.from(event.dataTransfer.files).filter(isSupportedFile)
  if (files.length > 0) {
    addFiles(files)
  }
}

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleFileSelect = (event) => {
  const files = Array.from(event.target.files || []).filter(isSupportedFile)
  if (files.length > 0) {
    addFiles(files)
  }
}

const isSupportedFile = (file) => {
  const allowedExtensions = ['.pdf', '.jpg', '.jpeg', '.png']
  const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'))
  return allowedExtensions.includes(ext)
}

const addFiles = (files) => {
  const validFiles = files.filter(file => {
    if (file.size > 100 * 1024 * 1024) {
      showMessage(`文件 ${file.name} 超过 100MB，已跳过`, 'error')
      return false
    }
    return true
  })

  selectedFiles.value.push(...validFiles)

  if (validFiles.length > 0 && !taskName.value.trim()) {
    const firstName = validFiles[0].name
    const lastDotIndex = firstName.lastIndexOf('.')
    taskName.value = lastDotIndex > 0 ? firstName.slice(0, lastDotIndex) : firstName
  }

  if (validFiles.length > 0) {
    showMessage(`已添加 ${validFiles.length} 个文件`, 'success')
  }
}

const removeFile = (index) => {
  selectedFiles.value.splice(index, 1)
  if (selectedFiles.value.length === 0 && fileInput.value) {
    fileInput.value.value = ''
  }
}

const addField = () => {
  extractFields.value.push({ name: '', description: '' })
}

const removeField = (index) => {
  if (extractFields.value.length === 1) {
    showMessage('至少保留一行字段配置，或者切换到自然语言提示词模式。', 'error')
    return
  }
  extractFields.value.splice(index, 1)
}

const fillSamplePrompt = () => {
  customPrompt.value = DEFAULT_CUSTOM_PROMPT
}

const clearCustomPrompt = () => {
  customPrompt.value = ''
}

const formatFileSize = (bytes) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

const getFileIcon = (filename) => {
  const ext = filename.toLowerCase().slice(filename.lastIndexOf('.'))
  if (ext === '.pdf') return 'PDF'
  if (ext === '.jpg' || ext === '.jpeg' || ext === '.png') return 'IMG'
  return 'FILE'
}

const buildExtractPayload = () => {
  const fields = extractFields.value
    .map(field => ({
      name: field.name.trim(),
      description: field.description.trim()
    }))
    .filter(field => field.name || field.description)

  return {
    promptMode: promptMode.value,
    fields,
    customPrompt: promptMode.value === 'natural' ? customPrompt.value.trim() : null
  }
}

const validateBeforeSubmit = () => {
  if (selectedFiles.value.length === 0) {
    showMessage('请先选择文件。', 'error')
    return false
  }

  if (!taskName.value.trim()) {
    showMessage('请输入任务名称。', 'error')
    return false
  }

  const payload = buildExtractPayload()
  if (payload.promptMode === 'fields' && payload.fields.length === 0) {
    showMessage('字段模式下至少填写一行有效字段。', 'error')
    return false
  }

  if (payload.promptMode === 'natural' && !payload.customPrompt) {
    showMessage('自然语言提示词模式下请输入 prompt。', 'error')
    return false
  }

  return true
}

const submitTask = async () => {
  if (!validateBeforeSubmit()) {
    return
  }

  try {
    uploading.value = true
    showMessage('', '')

    const user = JSON.parse(localStorage.getItem('user') || '{}')
    if (!user.userId) {
      showMessage('请先登录。', 'error')
      setTimeout(() => router.push('/login'), 1200)
      return
    }

    const formData = new FormData()
    formData.append('taskName', taskName.value.trim())
    formData.append('userId', user.userId)
    formData.append('extractFields', JSON.stringify(buildExtractPayload()))
    formData.append('modelMode', modelMode.value)
    formData.append('inferenceConfig', JSON.stringify({
      temperature: Number(inferenceConfig.value.temperature),
      topP: Number(inferenceConfig.value.topP),
      topK: Number(inferenceConfig.value.topK),
      maxTokens: Number(inferenceConfig.value.maxTokens)
    }))

    selectedFiles.value.forEach(file => {
      formData.append('files', file)
    })

    const response = await taskApi.createTask(formData)
    if (response.code === 200) {
      showMessage(`任务创建成功，共 ${response.data.length} 个文件进入处理队列。`, 'success')
      setTimeout(() => {
        router.push('/tasks')
      }, 1800)
      return
    }

    showMessage(response.message || '任务创建失败。', 'error')
  } catch (error) {
    console.error('创建任务失败:', error)
    showMessage(error.response?.data?.message || '创建任务失败，请稍后重试。', 'error')
  } finally {
    uploading.value = false
  }
}

const showMessage = (text, type = 'success') => {
  message.value = text
  messageType.value = type

  if (text) {
    setTimeout(() => {
      message.value = ''
    }, 5000)
  }
}

onMounted(() => {
  const recommendedMode = sessionStorage.getItem('agentRecommendedMode')
  const routeReason = sessionStorage.getItem('agentRouteReason')

  if (recommendedMode === 'normal' || recommendedMode === 'pro') {
    modelMode.value = recommendedMode
    sessionStorage.removeItem('agentRecommendedMode')
  }

  if (routeReason) {
    sessionStorage.removeItem('agentRouteReason')
    showMessage(`已根据智能体路由切换到${modelMode.value === 'pro' ? '专业版' : '普通版'}：${routeReason}`, 'success')
  }
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

.dashboard-container {
  width: 100%;
  min-height: 100%;
  position: relative;
  overflow: hidden;
}

.bg-orb {
  position: fixed;
  border-radius: 50%;
  filter: blur(100px);
  pointer-events: none;
  animation: float 25s ease-in-out infinite;
}

.orb-1 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.15) 0%, transparent 70%);
  top: -150px;
  right: -100px;
  animation-delay: -5s;
}

.orb-2 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.12) 0%, transparent 70%);
  bottom: -100px;
  left: -100px;
  animation-delay: -12s;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25% { transform: translate(30px, -30px) scale(1.05); }
  50% { transform: translate(-20px, 20px) scale(0.95); }
  75% { transform: translate(20px, 30px) scale(1.02); }
}

.dashboard-content {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  position: relative;
  z-index: 1;
}

.hero-section {
  display: flex;
  align-items: flex-start;
  gap: 0.9rem;
  padding: 1rem 1.15rem;
  border-radius: 16px;
  background: rgba(17, 17, 24, 0.6);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.hero-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
  box-shadow: 0 8px 32px rgba(99, 102, 241, 0.3);
}

.hero-text h1 {
  margin: 0 0 0.3rem 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: #f8fafc;
  letter-spacing: -0.02em;
}

.hero-text p {
  margin: 0;
  color: #94a3b8;
  line-height: 1.45;
  max-width: 760px;
  font-size: 0.86rem;
}

.panel {
  background: rgba(17, 17, 24, 0.6);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  padding: 1rem;
}

.upload-panel {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
}

.upload-area {
  border: 1.5px dashed rgba(99, 102, 241, 0.4);
  border-radius: 14px;
  padding: 1.15rem 1rem;
  text-align: center;
  background: rgba(99, 102, 241, 0.03);
  cursor: pointer;
  transition: all 0.3s ease;
}

.upload-area:hover,
.upload-area.dragover {
  border-color: rgba(99, 102, 241, 0.8);
  background: rgba(99, 102, 241, 0.08);
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(99, 102, 241, 0.15);
}

.upload-icon {
  width: 54px;
  height: 54px;
  margin: 0 auto 0.75rem;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #818cf8;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(139, 92, 246, 0.1) 100%);
  border: 1px solid rgba(99, 102, 241, 0.3);
}

.upload-title {
  margin: 0 0 0.35rem 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: #e2e8f0;
}

.upload-hint {
  margin: 0;
  color: #64748b;
  font-size: 0.82rem;
}

.hidden-input {
  display: none;
}

.file-list {
  display: grid;
  gap: 0.5rem;
  max-height: 190px;
  overflow-y: auto;
  padding-right: 0.5rem;
}

/* 滚动条样式 */
.file-list::-webkit-scrollbar {
  width: 4px;
}

.file-list::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.02);
  border-radius: 2px;
}

.file-list::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.file-list::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.15);
}

.file-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.7rem;
  padding: 0.65rem 0.8rem;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 0.3s ease;
}

.file-card:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(99, 102, 241, 0.3);
}

.file-meta {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  min-width: 0;
}

.file-badge {
  flex-shrink: 0;
  padding: 0.25rem 0.55rem;
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(239, 68, 68, 0.1) 100%);
  color: #f87171;
  font-size: 0.75rem;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
}

.file-name {
  margin: 0 0 0.2rem 0;
  color: #e2e8f0;
  font-weight: 600;
  word-break: break-all;
  font-size: 0.84rem;
}

.file-size {
  margin: 0;
  color: #64748b;
  font-size: 0.74rem;
}

.section-header {
  margin-bottom: 0.9rem;
}

.section-header h2 {
  margin: 0 0 0.4rem 0;
  color: #f8fafc;
  font-size: 1.08rem;
}

.section-header p {
  margin: 0;
  color: #64748b;
  line-height: 1.45;
  font-size: 0.84rem;
}

.form-group {
  margin-bottom: 0.95rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.4rem;
  color: #94a3b8;
  font-weight: 500;
  font-size: 0.84rem;
}

.input-wrapper {
  position: relative;
}

.form-input {
  width: 100%;
  padding: 0.65rem 0.75rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  font-size: 0.86rem;
  color: #f8fafc;
  transition: all 0.3s ease;
  font-family: inherit;
}

.form-input:focus {
  outline: none;
  border-color: rgba(99, 102, 241, 0.5);
  background: rgba(99, 102, 241, 0.05);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.1);
}

.input-label {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: 0.875rem;
  color: #475569;
  pointer-events: none;
  transition: all 0.3s ease;
  background: transparent;
}

.form-input:focus + .input-label,
.form-input:not(:placeholder-shown) + .input-label {
  top: 0;
  transform: translateY(-50%) scale(0.85);
  color: #6366f1;
  background: #0a0a0f;
  padding: 0 0.5rem;
}

.mode-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem;
}

.prompt-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.mode-card {
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.28rem;
  text-align: left;
  cursor: pointer;
  transition: all 0.3s ease;
}

.mode-card:hover {
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.4);
  background: rgba(99, 102, 241, 0.05);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
}

.mode-card.active {
  border-color: #6366f1;
  background: rgba(99, 102, 241, 0.1);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.mode-card.pro.active {
  border-color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
}

.mode-card.prompt.natural.active {
  border-color: #8b5cf6;
  background: rgba(139, 92, 246, 0.1);
  box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.15);
}

.mode-card strong {
  color: #f8fafc;
  font-size: 0.92rem;
}

.mode-card span:last-child {
  color: #64748b;
  line-height: 1.38;
  font-size: 0.78rem;
}

.mode-tag {
  width: fit-content;
  padding: 0.18rem 0.5rem;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  font-size: 0.68rem;
  font-weight: 700;
}

.mode-tag.pro {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.mode-tag.natural {
  background: rgba(139, 92, 246, 0.15);
  color: #a78bfa;
}

.section-card {
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  padding: 0.85rem;
  background: rgba(255, 255, 255, 0.02);
  margin-bottom: 0.85rem;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.7rem;
  margin-bottom: 0.7rem;
}

.card-header h3 {
  margin: 0 0 0.3rem 0;
  color: #e2e8f0;
  font-size: 0.92rem;
  font-weight: 600;
}

.card-header p {
  margin: 0;
  color: #64748b;
  font-size: 0.78rem;
  line-height: 1.38;
}

.field-table {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.field-table-head,
.field-row {
  display: grid;
  grid-template-columns: 1.1fr 1.6fr 80px;
  gap: 0.45rem;
  align-items: center;
}

.field-table-head {
  color: #64748b;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0 0.15rem;
}

.prompt-card {
  background: linear-gradient(135deg, rgba(139, 92, 246, 0.05) 0%, rgba(99, 102, 241, 0.03) 100%);
  border-color: rgba(139, 92, 246, 0.15);
}

.prompt-textarea {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 0.75rem;
  font-size: 0.82rem;
  color: #e2e8f0;
  background: rgba(255, 255, 255, 0.03);
  resize: vertical;
  min-height: 175px;
  font-family: 'JetBrains Mono', monospace;
  line-height: 1.45;
  box-sizing: border-box;
}

.prompt-textarea:focus {
  outline: none;
  border-color: rgba(139, 92, 246, 0.5);
  box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.1);
}

.prompt-hint {
  margin: 0.5rem 0 0 0;
  color: #a78bfa;
  font-size: 0.76rem;
}

.action-row {
  display: flex;
  gap: 0.45rem;
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem;
}

.config-item {
  display: flex;
  flex-direction: column;
}

.config-item label {
  margin-bottom: 0.3rem;
  color: #94a3b8;
  font-size: 0.78rem;
}

.checkbox-row {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 1rem;
  color: #94a3b8;
  font-size: 0.9rem;
  cursor: pointer;
}

.checkbox-row input {
  width: 16px;
  height: 16px;
  accent-color: #6366f1;
}

.submit-row {
  margin-top: 0.5rem;
}

.submit-button,
.secondary-btn,
.ghost-btn,
.ghost-danger-btn {
  border: none;
  border-radius: 10px;
  padding: 0.65rem 0.9rem;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: inherit;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.submit-button {
  position: relative;
  min-width: 190px;
  color: #ffffff;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.3);
  overflow: hidden;
}

.submit-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s ease;
}

.submit-button:hover::before {
  left: 100%;
}

.submit-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 12px 32px rgba(99, 102, 241, 0.4);
}

.submit-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.button-text {
  position: relative;
  z-index: 1;
}

.button-loader {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

.secondary-btn {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  border: 1px solid rgba(99, 102, 241, 0.2);
}

.secondary-btn:hover {
  background: rgba(99, 102, 241, 0.25);
}

.ghost-btn {
  background: rgba(255, 255, 255, 0.05);
  color: #94a3b8;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.ghost-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
}

.ghost-danger-btn {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.15);
  padding: 0.42rem 0.6rem;
}

.ghost-danger-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.2);
}

.ghost-danger-btn.compact {
  padding: 0.55rem 0.65rem;
  font-size: 0.76rem;
}

.ghost-danger-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.message {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.7rem 0.9rem;
  border-radius: 12px;
  font-size: 0.82rem;
  font-weight: 500;
}

.message.success {
  background: rgba(16, 185, 129, 0.1);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.message.error {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.fade-enter-active,
.fade-leave-active {
  transition: all 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

@media (max-width: 1080px) {
  .mode-grid,
  .prompt-grid,
  .config-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .hero-section {
    flex-direction: column;
    padding: 1.25rem;
  }

  .panel {
    padding: 1.25rem;
  }

  .field-table-head {
    display: none;
  }

  .field-row {
    grid-template-columns: 1fr;
  }

  .card-header,
  .file-card {
    flex-direction: column;
    align-items: stretch;
  }

  .submit-button {
    width: 100%;
  }
}
</style>
