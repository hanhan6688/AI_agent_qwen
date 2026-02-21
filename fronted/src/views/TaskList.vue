<template>
  <div class="task-list-container">
    <div class="task-header">
      <h2>任务列表</h2>
      <button @click="loadTasks" class="refresh-button" :disabled="loading">
        {{ loading ? '加载中...' : '刷新' }}
      </button>
    </div>

    <div class="task-stats">
      <div class="stat-card">
        <span class="stat-label">批量任务</span>
        <span class="stat-value">{{ batchTasks.length }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">处理中</span>
        <span class="stat-value processing">{{ taskStats.processing }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">已完成</span>
        <span class="stat-value completed">{{ taskStats.completed }}</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">失败</span>
        <span class="stat-value failed">{{ taskStats.failed }}</span>
      </div>
    </div>

    <div v-if="loading" class="loading-spinner">
      <div class="spinner"></div>
      <p>加载中...</p>
    </div>

    <div v-else-if="batchTasks.length === 0" class="empty-state">
      <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#999" stroke-width="1">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
      </svg>
      <p>暂无任务</p>
    </div>

    <div v-else class="task-grid">
      <div v-for="batch in batchTasks" :key="batch.taskName" class="task-card">
        <div class="task-header-row">
          <h3 class="task-name">{{ batch.taskName }}</h3>
          <span :class="['task-status', getStatusClass(batch.status)]">{{ getStatusText(batch.status) }}</span>
        </div>

        <div class="task-info">
          <p class="task-file-count">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
            </svg>
            共 {{ batch.totalCount }} 个PDF文件
            <span v-if="batch.completedCount > 0" class="count-badge completed">{{ batch.completedCount }} 完成</span>
            <span v-if="batch.processingCount > 0" class="count-badge processing">{{ batch.processingCount }} 处理中</span>
            <span v-if="batch.failedCount > 0" class="count-badge failed">{{ batch.failedCount }} 失败</span>
          </p>
          <p class="task-time">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            {{ formatTime(batch.createdAt) }}
          </p>
        </div>

        <!-- 进度条 -->
        <div v-if="batch.status === 'PROCESSING'" class="progress-bar">
          <div class="progress-fill" :style="{ width: getProgressPercent(batch) + '%' }"></div>
          <span class="progress-text">{{ getProgressPercent(batch) }}%</span>
        </div>

        <div class="task-actions">
          <button
            @click="showPdfList(batch)"
            class="action-button preview"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
            预览PDF ({{ batch.totalCount }})
          </button>
          <button
            v-if="batch.status === 'COMPLETED'"
            @click="downloadJsonZip(batch)"
            class="action-button download"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            下载JSON
          </button>
          <button
            @click="deleteBatchTask(batch)"
            class="action-button delete"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            删除
          </button>
        </div>
      </div>
    </div>

    <!-- PDF列表弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3>{{ selectedBatch?.taskName }} - PDF文件列表</h3>
          <button class="modal-close" @click="closeModal">&times;</button>
        </div>
        <div class="modal-body">
          <div class="pdf-list">
            <div v-for="file in selectedBatch?.files" :key="file.taskId" class="pdf-item">
              <div class="pdf-icon">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#e53e3e" stroke-width="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
              </div>
              <div class="pdf-info">
                <p class="pdf-name">{{ file.fileName }}</p>
                <div class="pdf-status-row">
                  <span :class="['status-tag', getStatusClass(file.status)]">{{ getStatusText(file.status) }}</span>
                  <span v-if="file.status === 'PROCESSING'" class="progress-tag">{{ file.progress }}%</span>
                </div>
                <p v-if="file.errorMessage" class="pdf-error">{{ file.errorMessage }}</p>
              </div>
              <div class="pdf-actions">
                <button @click="previewPdf(file)" class="pdf-action-btn" title="预览">
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { taskApi, fileApi } from '../api'
import { useRouter } from 'vue-router'

const router = useRouter()
const batchTasks = ref([])
const loading = ref(false)
const showModal = ref(false)
const selectedBatch = ref(null)

let refreshInterval = null

const taskStats = computed(() => {
  let processing = 0, completed = 0, failed = 0
  batchTasks.value.forEach(batch => {
    if (batch.status === 'PROCESSING') processing++
    else if (batch.status === 'COMPLETED') completed++
    else if (batch.status === 'FAILED') failed++
  })
  return { processing, completed, failed }
})

const loadTasks = async () => {
  try {
    loading.value = true
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    const userId = user.userId

    if (!userId) {
      router.push('/login')
      return
    }

    const response = await taskApi.getBatchTasks(userId)
    if (response.code === 200) {
      batchTasks.value = response.data || []
    }
  } catch (err) {
    console.error('加载任务失败:', err)
  } finally {
    loading.value = false
  }
}

const getStatusText = (status) => {
  const statusMap = {
    PENDING: '等待中',
    PROCESSING: '处理中',
    COMPLETED: '已完成',
    FAILED: '失败'
  }
  return statusMap[status] || status
}

const getStatusClass = (status) => {
  const classMap = {
    PENDING: 'pending',
    PROCESSING: 'processing',
    COMPLETED: 'completed',
    FAILED: 'failed'
  }
  return classMap[status] || ''
}

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const getProgressPercent = (batch) => {
  if (batch.totalCount === 0) return 0
  return Math.round((batch.completedCount + batch.failedCount) / batch.totalCount * 100)
}

const showPdfList = (batch) => {
  selectedBatch.value = batch
  showModal.value = true
}

const closeModal = () => {
  showModal.value = false
  selectedBatch.value = null
}

const previewPdf = (file) => {
  if (file.filePath) {
    window.open(fileApi.previewUploadedFile(file.filePath), '_blank')
  }
}

const downloadJsonZip = async (batch) => {
  try {
    // 先调用后端创建zip
    const result = await taskApi.createJsonZip(batch.taskName)
    // result.data 包含 { zipPath, downloadUrl, fileName }
    const fileName = result.data?.fileName || result.fileName
    if (!fileName) {
      alert('获取文件名失败')
      return
    }
    // 然后下载
    const downloadUrl = fileApi.downloadResultFile(batch.taskName, fileName)
    window.open(downloadUrl, '_blank')
  } catch (err) {
    alert('下载失败: ' + (err.response?.data?.message || err.message))
  }
}

const deleteBatchTask = async (batch) => {
  if (!confirm(`确定要删除批量任务"${batch.taskName}"吗？这将删除该任务下的所有 ${batch.totalCount} 个文件。`)) return

  try {
    const user = JSON.parse(localStorage.getItem('user') || '{}')
    await taskApi.deleteBatchTask(user.userId, batch.taskName)
    await loadTasks()
  } catch (err) {
    alert('删除失败: ' + (err.response?.data?.message || err.message))
  }
}

onMounted(() => {
  loadTasks()
  // 每10秒自动刷新
  refreshInterval = setInterval(() => {
    loadTasks()
  }, 10000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
.task-list-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

/* 任务列表头部 */
.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 0.8rem;
  border-bottom: 1px solid #e2e8f0;
}

.task-header h2 {
  margin: 0;
  color: #2d3748;
  font-size: 1.3rem;
  font-weight: 600;
}

.refresh-button {
  padding: 0.5rem 1.2rem;
  background: #4299e1;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s;
  font-size: 0.9rem;
  font-weight: 500;

  &:hover:not(:disabled) {
    background: #3182ce;
    transform: translateY(-1px);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

/* 任务统计 */
.task-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.8rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background: white;
  padding: 1rem;
  border-radius: 6px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  text-align: center;
  border: 1px solid #e2e8f0;

  .stat-label {
    display: block;
    color: #718096;
    font-size: 0.85rem;
    margin-bottom: 0.3rem;
    font-weight: 500;
  }

  .stat-value {
    display: block;
    font-size: 1.5rem;
    font-weight: bold;
    color: #2d3748;

    &.processing {
      color: #ed8936;
    }

    &.completed {
      color: #38a169;
    }

    &.failed {
      color: #e53e3e;
    }
  }
}

/* 加载状态 */
.loading-spinner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  flex: 1;
}

.spinner {
  width: 35px;
  height: 35px;
  border: 3px solid #e2e8f0;
  border-top: 3px solid #4299e1;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: #a0aec0;
  flex: 1;

  p {
    margin-top: 0.8rem;
    font-size: 0.95rem;
  }
}

/* 任务网格 */
.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 1rem;
  flex: 1;
  overflow-y: auto;
  padding-right: 0.5rem;
}

/* 任务卡片 */
.task-card {
  background: white;
  padding: 1.2rem;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.3s;
  border: 1px solid #e2e8f0;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    transform: translateY(-1px);
    border-color: #cbd5e0;
  }
}

.task-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.8rem;
}

.task-name {
  margin: 0;
  font-size: 1rem;
  color: #2d3748;
  font-weight: 600;
  word-break: break-word;
  flex: 1;
  margin-right: 0.5rem;
}

.task-status {
  padding: 0.25rem 0.7rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
  white-space: nowrap;

  &.pending {
    background: #ebf8ff;
    color: #2b6cb0;
  }

  &.processing {
    background: #fffaf0;
    color: #d69e2e;
  }

  &.completed {
    background: #f0fff4;
    color: #2f855a;
  }

  &.failed {
    background: #fff5f5;
    color: #c53030;
  }
}

/* 任务信息 */
.task-info {
  margin-bottom: 1rem;

  p {
    margin: 0.4rem 0;
    color: #718096;
    font-size: 0.85rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;

    svg {
      flex-shrink: 0;
      width: 14px;
      height: 14px;
      color: #a0aec0;
    }
  }
}

.count-badge {
  padding: 0.15rem 0.5rem;
  border-radius: 10px;
  font-size: 0.75rem;
  font-weight: 500;

  &.completed {
    background: #c6f6d5;
    color: #276749;
  }

  &.processing {
    background: #feebc8;
    color: #c05621;
  }

  &.failed {
    background: #fed7d7;
    color: #c53030;
  }
}

/* 进度条 */
.progress-bar {
  height: 20px;
  background: #e2e8f0;
  border-radius: 10px;
  margin-bottom: 1rem;
  position: relative;
  overflow: hidden;

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #4299e1, #3182ce);
    border-radius: 10px;
    transition: width 0.3s ease;
  }

  .progress-text {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 0.7rem;
    color: #2d3748;
    font-weight: 600;
  }
}

/* 任务操作按钮 */
.task-actions {
  display: flex;
  gap: 0.4rem;
}

.action-button {
  flex: 1;
  padding: 0.5rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  transition: all 0.3s;

  &.preview {
    background: #3182ce;
    color: white;

    &:hover {
      background: #2b6cb0;
    }
  }

  &.download {
    background: #38a169;
    color: white;

    &:hover {
      background: #2f855a;
    }
  }

  &.delete {
    background: #e53e3e;
    color: white;

    &:hover {
      background: #c53030;
    }
  }

  svg {
    width: 14px;
    height: 14px;
  }
}

/* 模态框 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #e2e8f0;

  h3 {
    margin: 0;
    font-size: 1.1rem;
    color: #2d3748;
  }

  .modal-close {
    background: none;
    border: none;
    font-size: 1.5rem;
    color: #718096;
    cursor: pointer;
    padding: 0;
    line-height: 1;

    &:hover {
      color: #2d3748;
    }
  }
}

.modal-body {
  padding: 1rem 1.5rem;
  overflow-y: auto;
  flex: 1;
}

.pdf-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.pdf-item {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.8rem;
  background: #f7fafc;
  border-radius: 6px;
  border: 1px solid #e2e8f0;

  &:hover {
    background: #edf2f7;
  }
}

.pdf-icon {
  flex-shrink: 0;
}

.pdf-info {
  flex: 1;
  min-width: 0;

  .pdf-name {
    margin: 0 0 0.3rem 0;
    font-size: 0.9rem;
    color: #2d3748;
    font-weight: 500;
    word-break: break-all;
  }

  .pdf-status-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .status-tag {
    padding: 0.15rem 0.5rem;
    border-radius: 10px;
    font-size: 0.7rem;
    font-weight: 500;

    &.pending {
      background: #ebf8ff;
      color: #2b6cb0;
    }

    &.processing {
      background: #fffaf0;
      color: #d69e2e;
    }

    &.completed {
      background: #f0fff4;
      color: #2f855a;
    }

    &.failed {
      background: #fff5f5;
      color: #c53030;
    }
  }

  .progress-tag {
    font-size: 0.7rem;
    color: #718096;
  }

  .pdf-error {
    margin: 0.3rem 0 0 0;
    font-size: 0.75rem;
    color: #c53030;
  }
}

.pdf-actions {
  flex-shrink: 0;
}

.pdf-action-btn {
  padding: 0.4rem;
  background: #3182ce;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    background: #2b6cb0;
  }

  svg {
    display: block;
  }
}
</style>
