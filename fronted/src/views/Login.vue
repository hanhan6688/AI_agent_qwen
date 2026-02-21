<template>
  <div class="login-container">
    <div class="login-card">
      <h1 class="login-title">文档智能提取系统</h1>
      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            class="form-input"
            placeholder="请输入用户名"
            required
          />
        </div>
        <div class="form-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            class="form-input"
            placeholder="请输入密码"
            required
          />
        </div>
        <button type="submit" class="login-button" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
        <p v-if="error" class="error-message">{{ error }}</p>
        <p class="hint-text">
          默认账号: admin / admin123 | 没有账户？<a @click="showRegister = true" class="link">注册</a>
        </p>
      </form>
    </div>
    <!-- 注册弹窗 -->
    <Register v-if="showRegister" @switch-to-login="showRegister = false" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { authApi } from '../api'
import Register from './Register.vue'

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const showRegister = ref(false)

const handleLogin = async () => {
  try {
    loading.value = true
    error.value = ''

    const response = await authApi.login(username.value, password.value)

    if (response.code === 200) {
      // 保存用户信息到localStorage
      // 后端返回的是 { user: { userId, username, ... } }
      const userData = response.data.user || response.data
      localStorage.setItem('user', JSON.stringify(userData))
      console.log('登录成功，用户信息:', userData)
      // 简单的页面刷新，确保组件正确重新渲染
      window.location.reload()
    } else {
      error.value = response.message || '登录失败'
    }
  } catch (err) {
    error.value = err.response?.data?.message || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  width: 100%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  padding: 1rem;
  box-sizing: border-box;
}

.login-card {
  background: white;
  border-radius: 8px;
  box-shadow: 0 15px 40px rgba(0, 0, 0, 0.3);
  width: 360px; /* 固定宽度 */
  max-width: 360px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  margin: 0 auto; /* 水平居中 */
}

.login-title {
  text-align: center;
  margin: 0;
  padding: 1.2rem;
  background: linear-gradient(90deg, #4a5568 0%, #2d3748 100%);
  color: white;
  font-size: 1.3rem;
  font-weight: 600;
}

.login-form {
  display: flex;
  flex-direction: column;
  padding: 1.5rem;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.form-group label {
  font-size: 0.8rem;
  color: #4a5568;
  font-weight: 500;
  margin-bottom: 0.2rem;
}

.form-input {
  padding: 0.75rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.9rem;
  transition: all 0.3s;
  background: white;

  &:focus {
    outline: none;
    border-color: #4299e1;
    box-shadow: 0 0 0 2px rgba(66, 153, 225, 0.2);
  }
}

.login-button {
  padding: 0.8rem;
  background: linear-gradient(90deg, #3182ce 0%, #2b6cb0 100%);
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  margin-top: 0.5rem;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    background: linear-gradient(90deg, #2b6cb0 0%, #2c5282 100%);
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
}

.error-message {
  color: #e53e3e;
  text-align: center;
  margin: 0;
  font-size: 0.8rem;
  padding: 0.5rem;
  background: #fff5f5;
  border-radius: 4px;
  border-left: 3px solid #e53e3e;
}

.hint-text {
  text-align: center;
  color: #718096;
  font-size: 0.75rem;
  margin: 0;
  padding: 0.8rem 1.5rem;
  background: #f7fafc;
  border-top: 1px solid #e2e8f0;
}

.link {
  color: #4299e1;
  cursor: pointer;
  text-decoration: underline;
}

.link:hover {
  color: #2b6cb0;
}
</style>