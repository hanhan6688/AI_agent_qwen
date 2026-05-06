<template>
  <div class="register-overlay">
    <div class="register-card">
      <div class="card-glow"></div>
      <button class="close-btn" @click="goToLogin">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>

      <div class="card-header">
        <div class="register-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
            <circle cx="8.5" cy="7" r="4"/>
            <line x1="20" y1="8" x2="20" y2="14"/>
            <line x1="23" y1="11" x2="17" y2="11"/>
          </svg>
        </div>
        <h2>创建新账户</h2>
        <p>加入 DocExtract 开始智能文档提取</p>
      </div>

      <form @submit.prevent="handleRegister" class="register-form">
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
          <div class="input-wrapper" :class="{ focused: emailFocused }">
            <div class="input-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                <polyline points="22,6 12,13 2,6"/>
              </svg>
            </div>
            <input
              id="email"
              v-model="email"
              type="email"
              class="form-input"
              placeholder=" "
              required
              @focus="emailFocused = true"
              @blur="emailFocused = false"
            />
            <label for="email" class="input-label">邮箱</label>
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

        <div class="form-group">
          <div class="input-wrapper" :class="{ focused: confirmFocused }">
            <div class="input-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                <polyline points="9 11 11 13 15 9"/>
              </svg>
            </div>
            <input
              id="confirmPassword"
              v-model="confirmPassword"
              type="password"
              class="form-input"
              placeholder=" "
              required
              @focus="confirmFocused = true"
              @blur="confirmFocused = false"
            />
            <label for="confirmPassword" class="input-label">确认密码</label>
          </div>
        </div>

        <button type="submit" class="register-button" :disabled="loading" :class="{ loading }">
          <span class="button-text">{{ loading ? '创建中...' : '创建账户' }}</span>
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
        <p class="footer-text">
          已有账户？
          <button @click="goToLogin" class="link-btn">返回登录</button>
        </p>
      </div>
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
const usernameFocused = ref(false)
const emailFocused = ref(false)
const passwordFocused = ref(false)
const confirmFocused = ref(false)

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
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

.register-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 1rem;
}

.register-card {
  position: relative;
  width: 100%;
  max-width: 420px;
  background: rgba(17, 17, 24, 0.95);
  backdrop-filter: blur(40px);
  border-radius: 24px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 2.5rem;
  box-shadow:
    0 25px 50px -12px rgba(0, 0, 0, 0.5),
    inset 0 1px 0 rgba(255, 255, 255, 0.05);
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

.close-btn {
  position: absolute;
  top: 1.25rem;
  right: 1.25rem;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.05);
  border: none;
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
}

.card-header {
  text-align: center;
  margin-bottom: 2rem;
}

.register-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 1.25rem;
  border-radius: 20px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a78bfa 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow:
    0 8px 32px rgba(99, 102, 241, 0.4),
    inset 0 2px 4px rgba(255, 255, 255, 0.2);
}

.card-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: #f8fafc;
  letter-spacing: -0.02em;
}

.card-header p {
  margin: 0;
  color: #64748b;
  font-size: 0.9rem;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
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

.register-button {
  position: relative;
  width: 100%;
  padding: 1rem;
  background: linear-gradient(135deg, #10b981 0%, #059669 100%);
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

.register-button::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s ease;
}

.register-button:hover::before {
  left: 100%;
}

.register-button:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 10px 40px rgba(16, 185, 129, 0.4);
}

.register-button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
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

.card-footer {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  text-align: center;
}

.footer-text {
  color: #64748b;
  font-size: 0.875rem;
  margin: 0;
}

.link-btn {
  background: none;
  border: none;
  color: #818cf8;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  padding: 0;
  transition: color 0.2s ease;
}

.link-btn:hover {
  color: #a5b4fc;
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
</style>