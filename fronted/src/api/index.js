import axios from 'axios'

// 创建axios实例
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    // 从localStorage获取token（如果有）
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    console.error('API错误:', error)
    return Promise.reject(error)
  }
)

// 用户认证API
export const authApi = {
  // 登录
  login: (username, password) => {
    return api.post('/api/auth/login', { username, password })
  },

  // 获取当前用户信息
  getCurrentUser: (userId) => {
    return api.get(`/api/auth/user/${userId}`)
  }
}

// 任务API
export const taskApi = {
  // 创建任务
  createTask: (formData) => {
    return api.post('/api/tasks', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  // 获取任务列表
  getTasks: (userId, page = 0, size = 10) => {
    return api.get('/api/tasks', {
      params: { userId, page, size }
    })
  },

  // 获取任务详情
  getTask: (taskId) => {
    return api.get(`/api/tasks/${taskId}`)
  },

  // 获取任务状态
  getTaskStatus: (taskId) => {
    return api.get(`/api/tasks/${taskId}/status`)
  },

  // 删除任务
  deleteTask: (taskId) => {
    return api.delete(`/api/tasks/${taskId}`)
  }
}

// 文件API
export const fileApi = {
  // 下载Excel文件
  downloadExcel: (taskId, fileName) => {
    return `${api.defaults.baseURL}/api/files/download/excel/${taskId}?fileName=${encodeURIComponent(fileName)}`
  },

  // 下载上传的文件
  downloadUploadedFile: (fileName) => {
    return `${api.defaults.baseURL}/api/files/download/upload/${encodeURIComponent(fileName)}`
  },

  // 预览上传的文件（PDF）
  previewUploadedFile: (fileName) => {
    return `${api.defaults.baseURL}/api/files/preview/upload/${encodeURIComponent(fileName)}`
  }
}

export default api
