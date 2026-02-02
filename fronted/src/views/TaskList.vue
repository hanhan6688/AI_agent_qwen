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
        <span class="stat-label">总任务</span>
        <span class="stat-value">{{ tasks.length }}</span>
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

    <div v-else-if="tasks.length === 0" class="empty-state">
      <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#999" stroke-width="1">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
      </svg>
      <p>暂无任务</p>
    </div>

    <div v-else class="task-grid">
      <div v-for="task in tasks" :key="task.id" class="task-card">
        <div class="task-header-row">
          <h3 class="task-name">{{ task.taskName }}</h3>
          <span :class="['task-status', task.status.toLowerCase()]">{{ getStatusText(task.status) }}</span>
        </div>

        <div class="task-info">
          <p class="task-file">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
              <polyline points="13 2 13 9 20 9"></polyline>
            </svg>
            {{ task.fileName }}
          </p>
          <p class="task-time">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"></circle>
              <polyline points="12 6 12 12 16 14"></polyline>
            </svg>
            {{ formatTime(task.createdAt) }}
          </p>
        </div>

        <div class="task-actions">
          <button
            @click="previewPDF(task)"
            class="action-button preview"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
            预览PDF
          </button>
          <button
            v-if="task.status === 'COMPLETED'"
            @click="downloadExcel(task)"
            class="action-button download"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            下载Excel
          </button>
          <button
            @click="deleteTask(task.id)"
            class="action-button delete"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            删除
          </button>
        </div>

        <div v-if="task.status === 'FAILED'" class="error-message">
          <p>错误: {{ task.errorMessage }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { taskApi, fileApi } from '../api'
import { useRouter } from 'vue-router'

const router = useRouter()
const tasks = ref([])
const loading = ref(false)

const taskStats = computed(() => {
  return {
    processing: tasks.value.filter(t => t.status === 'PROCESSING').length,
    completed: tasks.value.filter(t => t.status === 'COMPLETED').length,
    failed: tasks.value.filter(t => t.status === 'FAILED').length
  }
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

    const response = await taskApi.getTasks(userId, 0, 100)
    if (response.code === 200) {
      tasks.value = response.data.content
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

const formatTime = (time) => {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

const downloadExcel = (task) => {
  if (task.excelPath) {
    const fileName = task.excelPath.split('/').pop()
    window.open(fileApi.downloadExcel(task.id, fileName), '_blank')
  }
}

const previewPDF = (task) => {
  if (task.fileName) {
    window.open(fileApi.previewUploadedFile(task.fileName), '_blank')
  }
}

const deleteTask = async (taskId) => {
  if (!confirm('确定要删除此任务吗？')) return

  try {
    await taskApi.deleteTask(taskId)
    await loadTasks()
  } catch (err) {
    alert('删除失败: ' + (err.response?.data?.message || err.message))
  }
}

onMounted(() => {
  loadTasks()
  // 每10秒自动刷新
  const interval = setInterval(() => {
    loadTasks()
  }, 10000)

  // 组件卸载时清除定时器
  return () => clearInterval(interval)
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
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
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
}

.task-status {
  padding: 0.25rem 0.7rem;
  border-radius: 12px;
  font-size: 0.75rem;
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

    svg {
      flex-shrink: 0;
      width: 14px;
      height: 14px;
      color: #a0aec0;
    }
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

/* 错误信息 */
.error-message {
  margin-top: 0.8rem;
  padding: 0.6rem;
  background: #fff5f5;
  border-radius: 4px;
  border-left: 3px solid #e53e3e;

  p {
    margin: 0;
    color: #c53030;
    font-size: 0.8rem;
  }
}
</style>