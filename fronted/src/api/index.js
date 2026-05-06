import axios from 'axios'

// 创建axios实例
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求去重 map
const pendingRequests = new Map()

// 请求拦截器 - 添加token和去重
api.interceptors.request.use(
  config => {
    // 从localStorage获取token（如果有）
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    // 对 GET 请求实现去重（相同 URL + params 只发一次请求）
    if (config.method === 'get') {
      const key = JSON.stringify({ url: config.url, params: config.params })
      if (pendingRequests.has(key)) {
        // 取消当前请求，返回已有请求的 Promise
        config.cancelToken = new axios.CancelToken(cancel => {
          // 等待已有请求完成
          pendingRequests.get(key).then(cached => {
            cancel(cached)
          })
        })
        return config
      }
      // 缓存请求 Promise
      pendingRequests.set(key, new Promise(resolve => {
        // 临时存储 resolve，等请求完成时调用
        config._pendingResolve = resolve
      }))
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器 - 处理去重和返回data
api.interceptors.response.use(
  response => {
    // 调用 pending 请求的 resolve
    if (response.config._pendingResolve) {
      response.config._pendingResolve(response)
      pendingRequests.delete(JSON.stringify({ url: response.config.url, params: response.config.params }))
    }
    return response.data
  },
  error => {
    // 清理 pending 状态
    if (error.config) {
      pendingRequests.delete(JSON.stringify({ url: error.config.url, params: error.config.params }))
    }
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

  // 注册
  register: (username, password, email) => {
    const params = new URLSearchParams()
    params.append('username', username)
    params.append('password', password)
    params.append('email', email)
    return api.post('/api/auth/register', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
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
      timeout: 180000,
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
  },

  // 获取批量任务列表
  getBatchTasks: (userId) => {
    return api.get('/api/tasks/batch', {
      params: { userId }
    })
  },

  // 获取批量任务详情
  getBatchTaskDetails: (userId, taskName) => {
    return api.get(`/api/tasks/batch/${encodeURIComponent(taskName)}`, {
      params: { userId }
    })
  },

  // 删除批量任务
  deleteBatchTask: (userId, taskName) => {
    return api.delete(`/api/tasks/batch/${encodeURIComponent(taskName)}`, {
      params: { userId }
    })
  },

  // 创建JSON zip包
  createJsonZip: (taskName) => {
    return api.post('/api/tasks/create-json-zip', null, {
      params: { taskName }
    })
  }
}

// 文件API
export const fileApi = {
  // 下载上传的文件
  downloadUploadedFile: (fileName) => {
    return `${api.defaults.baseURL}/api/files/download/upload/${encodeURIComponent(fileName)}`
  },

  // 预览上传的文件（PDF）
  previewUploadedFile: (fileName) => {
    return `${api.defaults.baseURL}/api/files/preview/upload/${encodeURIComponent(fileName)}`
  },

  previewTaskPdfFile: (taskName, fileName) => {
    return `${api.defaults.baseURL}/api/files/preview/task/${encodeURIComponent(taskName)}/pdf/${encodeURIComponent(fileName)}`
  },

  // 下载result目录下的ZIP文件
  downloadResultFile: (taskName, fileName) => {
    return `${api.defaults.baseURL}/api/files/download/result/${encodeURIComponent(taskName)}/result/${encodeURIComponent(fileName)}`
  }
}

export const agentApi = {
  profile: () => {
    return api.get('/api/agent/profile')
  },

  chat: (message, history = [], mode = 'normal') => {
    return api.post('/api/agent/chat', { message, history, mode }, {
      timeout: 240000
    })
  },

  streamChat: async ({ message, history = [], mode = 'normal', files = [], onMeta, onDelta, onDone, onError }) => {
    const formData = new FormData()
    const payload = new Blob([JSON.stringify({ message: message || '', mode, history })], {
      type: 'application/json;charset=utf-8'
    })
    formData.append('payload', payload, 'payload.json')
    files.forEach(file => formData.append('files', file))

    const response = await fetch(`${api.defaults.baseURL}/api/agent/chat/stream`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      throw new Error(`流式对话请求失败: HTTP ${response.status}`)
    }
    if (!response.body) {
      throw new Error('当前浏览器不支持流式响应')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    const handleEvent = (rawEvent) => {
      const lines = rawEvent.split(/\r?\n/)
      let event = 'message'
      const dataLines = []

      lines.forEach(line => {
        if (line.startsWith('event:')) {
          event = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trimStart())
        }
      })

      if (dataLines.length === 0) {
        return
      }

      const dataText = dataLines.join('\n')
      let data = dataText
      try {
        data = JSON.parse(dataText)
      } catch {
        // keep raw text
      }

      if (event === 'meta') onMeta?.(data)
      else if (event === 'delta') onDelta?.(data.content || '')
      else if (event === 'done') onDone?.(data)
      else if (event === 'error') onError?.(data.message || '流式对话失败')
    }

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split(/\r?\n\r?\n/)
      buffer = chunks.pop() || ''
      chunks.forEach(handleEvent)
    }

    if (buffer.trim()) {
      handleEvent(buffer)
    }
  }
}

export default api
