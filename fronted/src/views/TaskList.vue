<template>
  <div class="task-list-container">
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>

    <div class="task-header">
      <div class="header-content">
        <h2>任务列表</h2>
        <p class="header-subtitle">实时查看文档提取任务进度与结果</p>
      </div>
      <button @click="loadTasks" class="refresh-button" :disabled="loading">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ spinning: loading }">
          <polyline points="23 4 23 10 17 10"/>
          <polyline points="1 20 1 14 7 14"/>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
        </svg>
        {{ loading ? '刷新中...' : '刷新' }}
      </button>
    </div>

    <div class="task-stats">
      <div class="stat-card" :class="{ 'glow': taskStats.processing > 0 }">
        <div class="stat-icon processing">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
        </div>
        <div class="stat-info">
          <span class="stat-value processing">{{ taskStats.processing }}</span>
          <span class="stat-label">处理中</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon completed">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
        </div>
        <div class="stat-info">
          <span class="stat-value completed">{{ taskStats.completed }}</span>
          <span class="stat-label">已完成</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon failed">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"/>
            <line x1="15" y1="9" x2="9" y2="15"/>
            <line x1="9" y1="9" x2="15" y2="15"/>
          </svg>
        </div>
        <div class="stat-info">
          <span class="stat-value failed">{{ taskStats.failed }}</span>
          <span class="stat-label">失败</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon total">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </div>
        <div class="stat-info">
          <span class="stat-value total">{{ batchTasks.length }}</span>
          <span class="stat-label">批量任务</span>
        </div>
      </div>
    </div>

    <div v-if="loading" class="loading-spinner">
      <div class="spinner-wrapper">
        <div class="spinner"></div>
        <p>加载任务数据...</p>
      </div>
    </div>

    <div v-else-if="batchTasks.length === 0" class="empty-state">
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="12" y1="18" x2="12" y2="12"/>
          <line x1="9" y1="15" x2="15" y2="15"/>
        </svg>
      </div>
      <p class="empty-title">暂无任务</p>
      <p class="empty-subtitle">上传文档后即可开始提取</p>
    </div>

    <div v-else class="task-grid">
      <div v-for="batch in batchTasks" :key="batch.taskName" class="task-card">
        <div class="card-glow"></div>
        <div class="task-header-row">
          <h3 class="task-name">{{ batch.taskName }}</h3>
          <span :class="['task-status', getStatusClass(batch.status)]">
            <span class="status-dot" v-if="batch.status === 'PROCESSING'"></span>
            {{ getStatusText(batch.status) }}
          </span>
        </div>

        <div class="task-info">
          <p class="task-file-count">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            共 {{ batch.totalCount }} 个PDF文件
          </p>
          <div class="count-badges">
            <span v-if="batch.completedCount > 0" class="count-badge completed">
              {{ batch.completedCount }} 完成
            </span>
            <span v-if="batch.processingCount > 0" class="count-badge processing">
              {{ batch.processingCount }} 处理中
            </span>
            <span v-if="batch.failedCount > 0" class="count-badge failed">
              {{ batch.failedCount }} 失败
            </span>
          </div>
          <p class="task-time">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
            {{ formatTime(batch.createdAt) }}
          </p>
        </div>

        <div v-if="batch.status === 'PROCESSING'" class="progress-bar">
          <div class="progress-fill" :style="{ width: getProgressPercent(batch) + '%' }">
            <span class="progress-shine"></span>
          </div>
          <span class="progress-text">{{ getProgressPercent(batch) }}%</span>
        </div>

        <div class="task-actions">
          <button @click="showPdfList(batch)" class="action-button preview">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
            预览 ({{ batch.totalCount }})
          </button>
          <button
            v-if="batch.status === 'COMPLETED'"
            @click="downloadJsonZip(batch)"
            class="action-button download"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            下载JSON
          </button>
          <button @click="deleteBatchTask(batch)" class="action-button delete">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
      </div>
    </div>

    <transition name="modal-fade">
      <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
        <div class="modal-content">
          <div class="modal-header">
            <h3>{{ selectedBatch?.taskName }}</h3>
            <span class="modal-subtitle">PDF文件列表</span>
            <button class="modal-close" @click="closeModal">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="modal-body">
            <div class="pdf-list">
              <div v-for="file in selectedBatch?.files" :key="file.taskId" class="pdf-item">
                <div class="pdf-icon">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
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
                <button @click="previewPdf(selectedBatch, file)" class="pdf-action-btn" title="预览">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
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

// 智能刷新：有处理中任务时3秒刷新，否则15秒
const effectiveRefreshInterval = computed(() => {
  const hasProcessing = taskStats.value.processing > 0
  return hasProcessing ? 3000 : 15000
})

const loadTasks = async () => {
  if (loading.value) return  // 防重复请求
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

const previewPdf = (batch, file) => {
  if (batch?.taskName && file?.filePath) {
    window.open(fileApi.previewTaskPdfFile(batch.taskName, file.filePath), '_blank')
  }
}

const downloadJsonZip = async (batch) => {
  try {
    const result = await taskApi.createJsonZip(batch.taskName)
    const fileName = result.data?.fileName || result.fileName
    if (!fileName) {
      alert('获取文件名失败')
      return
    }
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
  // 使用智能刷新间隔（有处理中任务时3秒，否则15秒）
  refreshInterval = setInterval(() => {
    if (effectiveRefreshInterval.value > 0) {
      loadTasks()
    }
  }, effectiveRefreshInterval.value)
})

// 监听刷新间隔变化，动态调整定时器
watch(effectiveRefreshInterval, (newInterval) => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
    refreshInterval = setInterval(() => {
      loadTasks()
    }, newInterval)
  }
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

.task-list-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
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
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.12) 0%, transparent 70%);
  top: -100px;
  left: -50px;
  animation-delay: -3s;
}

.orb-2 {
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.1) 0%, transparent 70%);
  bottom: -80px;
  right: -50px;
  animation-delay: -10s;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25% { transform: translate(30px, -30px) scale(1.05); }
  50% { transform: translate(-20px, 20px) scale(0.95); }
  75% { transform: translate(20px, 30px) scale(1.02); }
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.9rem;
  padding-bottom: 0.8rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.header-content h2 {
  margin: 0 0 0.3rem 0;
  color: #f8fafc;
  font-size: 1.25rem;
  font-weight: 700;
}

.header-subtitle {
  margin: 0;
  color: #64748b;
  font-size: 0.8rem;
}

.refresh-button {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.52rem 0.85rem;
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 600;
  transition: all 0.3s ease;
  font-family: inherit;
}

.refresh-button:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.25);
  transform: translateY(-1px);
}

.refresh-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.refresh-button svg.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.task-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.65rem;
  margin-bottom: 0.9rem;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.8rem;
  background: rgba(17, 17, 24, 0.6);
  backdrop-filter: blur(20px);
  border-radius: 13px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  border-color: rgba(255, 255, 255, 0.1);
}

.stat-card.glow {
  border-color: rgba(245, 158, 11, 0.3);
  box-shadow: 0 0 20px rgba(245, 158, 11, 0.1);
}

.stat-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-icon.processing {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.stat-icon.completed {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.stat-icon.failed {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.stat-icon.total {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.35rem;
  font-weight: 700;
  color: #f8fafc;
  line-height: 1;
}

.stat-value.processing { color: #fbbf24; }
.stat-value.completed { color: #34d399; }
.stat-value.failed { color: #f87171; }
.stat-value.total { color: #818cf8; }

.stat-label {
  font-size: 0.72rem;
  color: #64748b;
  margin-top: 0.25rem;
}

.loading-spinner {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
}

.spinner-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(99, 102, 241, 0.2);
  border-top-color: #6366f1;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.spinner-wrapper p {
  color: #64748b;
  font-size: 0.9rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  text-align: center;
}

.empty-icon {
  width: 58px;
  height: 58px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #475569;
  margin-bottom: 0.9rem;
}

.empty-title {
  margin: 0 0 0.5rem 0;
  color: #e2e8f0;
  font-size: 1rem;
  font-weight: 600;
}

.empty-subtitle {
  margin: 0;
  color: #64748b;
  font-size: 0.82rem;
}

.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 0.85rem;
  flex: 1;
  overflow-y: auto;
  position: relative;
  z-index: 1;
}

.task-card {
  position: relative;
  padding: 1rem;
  background: rgba(17, 17, 24, 0.6);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 0.3s ease;
  overflow: hidden;
}

.task-card:hover {
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.3);
  box-shadow: 0 14px 30px rgba(0, 0, 0, 0.24);
}

.card-glow {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 56px;
  background: radial-gradient(ellipse at top, rgba(99, 102, 241, 0.1) 0%, transparent 70%);
  pointer-events: none;
}

.task-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 0.65rem;
  position: relative;
}

.task-name {
  margin: 0;
  font-size: 0.94rem;
  color: #f8fafc;
  font-weight: 700;
  word-break: break-word;
  flex: 1;
  margin-right: 0.5rem;
}

.task-status {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.28rem 0.65rem;
  border-radius: 14px;
  font-size: 0.68rem;
  font-weight: 600;
  white-space: nowrap;
}

.task-status.pending {
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
}

.task-status.processing {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.task-status.completed {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.task-status.failed {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.task-info {
  margin-bottom: 0.7rem;
}

.task-file-count {
  display: flex;
  align-items: center;
  gap: 0.38rem;
  color: #94a3b8;
  font-size: 0.8rem;
  margin: 0 0 0.35rem 0;
}

.task-file-count svg {
  color: #64748b;
  flex-shrink: 0;
}

.count-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  margin-bottom: 0.5rem;
}

.count-badge {
  padding: 0.18rem 0.5rem;
  border-radius: 8px;
  font-size: 0.66rem;
  font-weight: 600;
}

.count-badge.completed {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.count-badge.processing {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.count-badge.failed {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.task-time {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  color: #64748b;
  font-size: 0.74rem;
  margin: 0;
}

.task-time svg {
  flex-shrink: 0;
}

.progress-bar {
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  margin-bottom: 0.7rem;
  position: relative;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%);
  border-radius: 10px;
  transition: width 0.5s ease;
  position: relative;
  overflow: hidden;
}

.progress-shine {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  animation: shine 2s infinite;
}

@keyframes shine {
  0% { left: -100%; }
  100% { left: 100%; }
}

.progress-text {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 0.65rem;
  color: white;
  font-weight: 700;
  font-family: 'JetBrains Mono', monospace;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.task-actions {
  display: flex;
  gap: 0.38rem;
  position: relative;
}

.action-button {
  flex: 1;
  padding: 0.55rem 0.65rem;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.76rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  transition: all 0.3s ease;
  font-family: inherit;
}

.action-button.preview {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.24);
}

.action-button.preview:hover {
  transform: translateY(-1px);
  box-shadow: 0 7px 16px rgba(99, 102, 241, 0.32);
}

.action-button.download {
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
  color: white;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.24);
}

.action-button.download:hover {
  transform: translateY(-1px);
  box-shadow: 0 7px 16px rgba(16, 185, 129, 0.32);
}

.action-button.delete {
  flex: 0 0 auto;
  padding: 0.55rem;
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.15);
}

.action-button.delete:hover {
  background: rgba(239, 68, 68, 0.2);
  transform: translateY(-1px);
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  width: 90%;
  max-width: 560px;
  max-height: 80vh;
  background: rgba(17, 17, 24, 0.95);
  backdrop-filter: blur(20px);
  border-radius: 18px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  flex-direction: column;
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
}

.modal-header {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 1rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.modal-header h3 {
  margin: 0;
  color: #f8fafc;
  font-size: 1rem;
  font-weight: 700;
}

.modal-subtitle {
  color: #64748b;
  font-size: 0.78rem;
  flex: 1;
}

.modal-close {
  background: rgba(255, 255, 255, 0.05);
  border: none;
  width: 30px;
  height: 30px;
  border-radius: 9px;
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.modal-close:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
}

.modal-body {
  padding: 0.85rem 1rem;
  overflow-y: auto;
  flex: 1;
}

.pdf-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.pdf-item {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  padding: 0.7rem;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 0.2s ease;
}

.pdf-item:hover {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(99, 102, 241, 0.2);
}

.pdf-icon {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: rgba(239, 68, 68, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #f87171;
}

.pdf-info {
  flex: 1;
  min-width: 0;
}

.pdf-name {
  margin: 0 0 0.3rem 0;
  color: #e2e8f0;
  font-weight: 600;
  font-size: 0.82rem;
  word-break: break-all;
}

.pdf-status-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.status-tag {
  padding: 0.16rem 0.5rem;
  border-radius: 7px;
  font-size: 0.66rem;
  font-weight: 600;
}

.status-tag.pending {
  background: rgba(56, 189, 248, 0.15);
  color: #38bdf8;
}

.status-tag.processing {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.status-tag.completed {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.status-tag.failed {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.progress-tag {
  font-size: 0.75rem;
  color: #64748b;
}

.pdf-error {
  margin: 0.4rem 0 0 0;
  font-size: 0.75rem;
  color: #f87171;
}

.pdf-action-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
  border: none;
  border-radius: 9px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.pdf-action-btn:hover {
  background: rgba(99, 102, 241, 0.25);
  transform: translateY(-1px);
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: all 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

@media (max-width: 768px) {
  .task-stats {
    grid-template-columns: repeat(2, 1fr);
  }

  .task-grid {
    grid-template-columns: 1fr;
  }
}
</style>
