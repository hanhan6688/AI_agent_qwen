<template>
  <div class="login-container">
    <div class="login-card">
      <h1 class="login-title">注册新账户</h1>
      <form @submit.prevent="handleRegister" class="login-form">
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
          <label for="email">邮箱</label>
          <input
            id="email"
            v-model="email"
            type="email"
            class="form-input"
            placeholder="请输入邮箱"
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
        <div class="form-group">
          <label for="confirmPassword">确认密码</label>
          <input
            id="confirmPassword"
            v-model="confirmPassword"
            type="password"
            class="form-input"
            placeholder="请再次输入密码"
            required
          />
        </div>
        <button type="submit" class="login-button" :disabled="loading">
          {{ loading ? '注册中...' : '注册' }}
        </button>
        <p v-if="error" class="error-message">{{ error }}</p>
        <p class="hint-text">
          已有账户？<a @click="goToLogin" class="link">返回登录</a>
        </p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { authApi } from '../api'

const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')

const emit = defineEmits(['switch-to-login'])

const handleRegister = async () => {
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致'
    return
  }

  if (password.value.length < 6) {
    error.value = '密码长度至少6位'
    return
  }

  try {
    loading.value = true
    error.value = ''

    const response = await authApi.register(username.value, password.value, email.value)

    if (response.code === 200) {
      alert('注册成功！请登录')
      goToLogin()
    } else {
      error.value = response.message || '注册失败'
    }
  } catch (err) {
    error.value = err.response?.data?.message || '注册失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

const goToLogin = () => {
  emit('switch-to-login')
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
  width: 360px;
  max-width: 360px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  margin: 0 auto;
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
}

.form-input:focus {
  outline: none;
  border-color: #4299e1;
  box-shadow: 0 0 0 2px rgba(66, 153, 225, 0.2);
}

.login-button {
  padding: 0.8rem;
  background: linear-gradient(90deg, #48bb78 0%, #38a169 100%);
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  margin-top: 0.5rem;
}

.login-button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  background: linear-gradient(90deg, #38a169 0%, #2f855a 100%);
}

.login-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
