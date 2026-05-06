<template>
  <div class="login-container">
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="bg-orb orb-3"></div>

    <div class="login-card">
      <div class="card-glow"></div>

      <div class="card-header">
        <div class="logo-wrapper">
          <div class="logo-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
        </div>
        <h1 class="login-title">DocExtract</h1>
        <p class="login-subtitle">智能文档指标提取系统</p>
      </div>

      <form @submit.prevent="handleLogin" class="login-form">
        <div class="form-group">
          <div class="input-wrapper" :class="{ focused: usernameFocused }">
            <div class="input-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
            </div>
            <input
              id="username"
              v-model="username"
              type="text"
              class="form-input"
              placeholder=" "
              required
              @focus="usernameFocused = true"
              @blur="usernameFocused = false"
            />
            <label for="username" class="input-label">用户名</label>
          </div>
        </div>

        <div class="form-group">
          <div class="input-wrapper" :class="{ focused: passwordFocused }">
            <div class="input-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </div>
            <input
              id="password"
              v-model="password"
              type="password"
              class="form-input"
              placeholder=" "
              required
              @focus="passwordFocused = true"
              @blur="passwordFocused = false"
            />
            <label for="password" class="input-label">密码</label>
          </div>
        </div>

        <button type="submit" class="login-button" :disabled="loading" :class="{ loading }">
          <span class="button-text">{{ loading ? '登录中...' : '登录' }}</span>
          <span class="button-loader" v-if="loading"></span>
        </button>

        <transition name="fade">
          <p v-if="error" class="error-message">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            {{ error }}
          </p>
        </transition>
      </form>

      <div class="card-footer">
        <div class="default-account">
          <span class="account-label">默认账号</span>
          <div class="account-fields">
            <button type="button" class="account-chip" @click="fillDefault" title="点击填充">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
              <span>admin</span>
            </button>
            <span class="account-sep">/</span>
            <button type="button" class="account-chip password" @click="fillDefault" title="点击填充">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
              <span>admin123</span>
            </button>
          </div>
        </div>
        <button class="register-link" @click="showRegister = true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="8.5" cy="7" r="4"/>
            <line x1="20" y1="8" x2="20" y2="14"/>
            <line x1="23" y1="11" x2="17" y2="11"/>
          </svg>
          注册新账户
        </button>
      </div>
    </div>

    <!-- 注册弹窗 -->
    <transition name="modal-fade">
      <Register v-if="showRegister" @switch-to-login="showRegister = false" />
    </transition>
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
const usernameFocused = ref(false)
const passwordFocused = ref(false)

const handleLogin = async () => {
  try {
    loading.value = true
    error.value = ''

    const response = await authApi.login(username.value, password.value)

    if (response.code === 200) {
      const userData = response.data.user || response.data
      localStorage.setItem('user', JSON.stringify(userData))
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

const fillDefault = () => {
  username.value = 'admin'
  password.value = 'admin123'
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  width: 100%;
  background: #0a0a0f;
  font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
  padding: 2rem;
  box-sizing: border-box;
  position: relative;
  overflow: hidden;
}

/* 背景动态光球 */
.bg-orb {
  position: fixed;
  border-radius: 50%;
  filter: blur(80px);
  pointer-events: none;
  animation: float 20s ease-in-out infinite;
}

.orb-1 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.3) 0%, transparent 70%);
  top: -100px;
  left: -100px;
  animation-delay: 0s;
}

.orb-2 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.25) 0%, transparent 70%);
  bottom: -150px;
  right: -100px;
  animation-delay: -7s;
}

.orb-3 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.2) 0%, transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  animation-delay: -14s;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  25% { transform: translate(30px, -30px) scale(1.05); }
  50% { transform: translate(-20px, 20px) scale(0.95); }
  75% { transform: translate(20px, 30px) scale(1.02); }
}

/* 登录卡片 */
.login-card {
  position: relative;
  width: 420px;
  background: rgba(17, 17, 24, 0.8);
  backdrop-filter: blur(40px);
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 2.5rem;
  box-shadow:
    0 25px 50px -12px rgba(0, 0, 0, 0.5),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
  z-index: 10;
}

.card-glow {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 200px;
  height: 100px;
  background: radial-gradient(ellipse, rgba(99, 102, 241, 0.3) 0%, transparent 70%);
  filter: blur(40px);
  pointer-events: none;
}

/* 卡片头部 */
.card-header {
  text-align: center;
  margin-bottom: 2.5rem;
}

.logo-wrapper {
  display: flex;
  justify-content: center;
  margin-bottom: 1.5rem;
}

.logo-icon {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow:
    0 8px 32px rgba(99, 102, 241, 0.4),
    inset 0 2px 4px rgba(255, 255, 255, 0.2);
  animation: pulse-glow 3s ease-in-out infinite;
}

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 8px 32px rgba(99, 102, 241, 0.4), inset 0 2px 4px rgba(255, 255, 255, 0.2); }
  50% { box-shadow: 0 8px 48px rgba(99, 102, 241, 0.6), inset 0 2px 4px rgba(255, 255, 255, 0.2); }
}

.login-title {
  font-size: 2rem;
  font-weight: 700;
  color: #f8fafc;
  margin: 0 0 0.5rem 0;
  letter-spacing: -0.03em;
}

.login-subtitle {
  font-size: 0.875rem;
  color: #64748b;
  margin: 0;
  font-weight: 400;
}

/* 表单样式 */
.login-form {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.form-group {
  position: relative;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 1rem;
  color: #475569;
  transition: color 0.3s ease;
  z-index: 2;
}

.input-wrapper.focused .input-icon {
  color: #6366f1;
}

.form-input {
  width: 100%;
  padding: 1rem 1rem 1rem 3rem;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  font-size: 0.95rem;
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
  left: 3rem;
  top: 50%;
  transform: translateY(-50%);
  font-size: 0.875rem;
  color: #64748b;
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

/* 登录按钮 */
.login-button {
  position: relative;
  width: 100%;
  padding: 1rem;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
  border: none;
  border-radius: 14px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: inherit;
  overflow: hidden;
}

.login-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s ease;
}

.login-button:hover::before {
  left: 100%;
}

.login-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 40px rgba(99, 102, 241, 0.4);
}

.login-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
  transform: none;
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
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: translate(-50%, -50%) rotate(360deg); }
}

/* 错误消息 */
.error-message {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.875rem 1rem;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 12px;
  color: #f87171;
  font-size: 0.85rem;
  margin: 0;
}

/* 底部提示 */
.card-footer {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.default-account {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
}

.account-label {
  font-size: 0.75rem;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.account-fields {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.account-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.5rem 0.875rem;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 20px;
  color: #a5b4fc;
  font-size: 0.8rem;
  font-family: 'JetBrains Mono', monospace;
  cursor: pointer;
  transition: all 0.25s ease;
}

.account-chip:hover {
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(99, 102, 241, 0.4);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
}

.account-chip svg {
  opacity: 0.7;
}

.account-chip.password {
  background: rgba(139, 92, 246, 0.08);
  border-color: rgba(139, 92, 246, 0.2);
  color: #c4b5fd;
}

.account-chip.password:hover {
  background: rgba(139, 92, 246, 0.2);
  border-color: rgba(139, 92, 246, 0.4);
  box-shadow: 0 4px 12px rgba(139, 92, 246, 0.25);
}

.account-sep {
  color: #475569;
  font-size: 0.9rem;
}

.register-link {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  width: 100%;
  margin-top: 0.75rem;
  padding: 0.7rem;
  background: rgba(255, 255, 255, 0.03);
  color: #94a3b8;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 500;
  transition: all 0.3s ease;
  font-family: inherit;
}

.register-link:hover {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.3);
  color: #818cf8;
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: all 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: all 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>