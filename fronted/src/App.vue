<template>
  <div class="app-container">
    <div class="bg-gradient"></div>
    <div class="bg-noise"></div>

    <!-- 登录界面 -->
    <LoginView v-if="!isAuthenticated" />

    <!-- 主应用界面 -->
    <div v-else class="main-wrapper">
      <!-- 顶部标题栏 -->
      <header class="app-header">
        <div class="header-left">
          <div class="logo-container">
            <div class="logo-icon">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <polyline points="14 2 14 8 20 8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
            <div class="logo-text">
              <span class="logo-title">MetricAgent</span>
              <span class="logo-subtitle">通义千问指标提取智能体</span>
            </div>
          </div>
        </div>

        <div class="header-right">
          <div class="user-info">
            <div class="user-avatar">{{ currentUser.username?.[0]?.toUpperCase() || 'U' }}</div>
            <span class="user-name">{{ currentUser.username }}</span>
          </div>
          <button @click="logout" class="logout-btn">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            退出
          </button>
        </div>
      </header>

      <!-- 主体内容区 -->
      <div class="content-wrapper">
        <!-- 左侧导航栏 -->
        <aside class="sidebar">
          <nav class="sidebar-nav">
            <router-link to="/" class="nav-item" :class="{ active: $route.path === '/' }">
              <div class="nav-icon-wrapper">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
              </div>
              <span class="nav-text">上传文档</span>
              <div class="nav-indicator"></div>
            </router-link>
            <router-link to="/tasks" class="nav-item" :class="{ active: $route.path === '/tasks' }">
              <div class="nav-icon-wrapper">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
                  <rect x="9" y="3" width="6" height="4" rx="1"/>
                  <line x1="9" y1="12" x2="15" y2="12"/>
                  <line x1="9" y1="16" x2="13" y2="16"/>
                </svg>
              </div>
              <span class="nav-text">任务列表</span>
              <div class="nav-indicator"></div>
            </router-link>
            <router-link to="/agent" class="nav-item" :class="{ active: $route.path === '/agent' }">
              <div class="nav-icon-wrapper">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M12 3a7 7 0 0 0-7 7v2a7 7 0 0 0 14 0v-2a7 7 0 0 0-7-7z"/>
                  <path d="M9 10h.01"/>
                  <path d="M15 10h.01"/>
                  <path d="M9 15c1.8 1.2 4.2 1.2 6 0"/>
                  <path d="M4 20c1.8-1.5 4.4-2.2 8-2.2s6.2.7 8 2.2"/>
                </svg>
              </div>
              <span class="nav-text">智能体对话</span>
              <div class="nav-indicator"></div>
            </router-link>
          </nav>

          <div class="sidebar-footer">
            <div class="system-status">
              <div class="status-dot"></div>
              <span>系统运行正常</span>
            </div>
          </div>
        </aside>

        <!-- 主内容区 -->
        <main class="main-content">
          <router-view v-slot="{ Component }">
            <transition name="page-fade" mode="out-in">
              <component :is="Component" />
            </transition>
          </router-view>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import LoginView from './views/Login.vue'

const router = useRouter()
const currentUser = ref({})
const isAuthenticated = ref(false)

const checkAuth = () => {
  const userStr = localStorage.getItem('user')
  if (!userStr) {
    isAuthenticated.value = false
    currentUser.value = {}
    return false
  }
  try {
    const user = JSON.parse(userStr)
    if (user.userId) {
      isAuthenticated.value = true
      currentUser.value = user
      return true
    }
  } catch {
    localStorage.removeItem('user')
  }
  isAuthenticated.value = false
  currentUser.value = {}
  return false
}

const logout = () => {
  localStorage.removeItem('user')
  isAuthenticated.value = false
  currentUser.value = {}
  router.replace('/')
}

onMounted(() => {
  checkAuth()
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

.app-container {
  min-height: 100vh;
  font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
  background: #0a0a0f;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow: hidden;
}

/* 背景效果 */
.bg-gradient {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background:
    radial-gradient(ellipse 80% 50% at 20% -20%, rgba(99, 102, 241, 0.15), transparent),
    radial-gradient(ellipse 60% 40% at 80% 100%, rgba(139, 92, 246, 0.1), transparent),
    linear-gradient(180deg, #0a0a0f 0%, #111118 100%);
  pointer-events: none;
  z-index: 0;
}

.bg-noise {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  opacity: 0.03;
  pointer-events: none;
  z-index: 1;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");
}

.main-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  max-width: 1480px;
  margin: 0 auto;
  width: 100%;
  position: relative;
  z-index: 2;
}

/* 顶部标题栏 */
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 1.25rem;
  height: 58px;
  background: rgba(17, 17, 24, 0.8);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.header-left {
  display: flex;
  align-items: center;
}

.logo-container {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.3);
}

.logo-text {
  display: flex;
  flex-direction: column;
}

.logo-title {
  font-size: 1.08rem;
  font-weight: 700;
  color: #f8fafc;
  letter-spacing: -0.02em;
}

.logo-subtitle {
  font-size: 0.68rem;
  color: #64748b;
  font-weight: 400;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.user-avatar {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 0.875rem;
}

.user-name {
  font-size: 0.875rem;
  color: #e2e8f0;
  font-weight: 500;
}

.logout-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.48rem 0.72rem;
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 500;
  transition: all 0.3s ease;
}

.logout-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.4);
}

/* 主体内容区 */
.content-wrapper {
  display: flex;
  flex: 1;
  min-height: 0;
  padding: 0.85rem 1rem;
  gap: 0.85rem;
}

/* 左侧导航栏 */
.sidebar {
  width: 176px;
  background: rgba(17, 17, 24, 0.6);
  backdrop-filter: blur(20px);
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  padding: 0.65rem;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.62rem 0.68rem;
  border-radius: 10px;
  text-decoration: none;
  color: #94a3b8;
  font-weight: 500;
  font-size: 0.875rem;
  transition: all 0.3s ease;
  position: relative;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #e2e8f0;
}

.nav-item.active {
  background: rgba(99, 102, 241, 0.15);
  color: #818cf8;
}

.nav-item.active .nav-icon-wrapper {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: white;
}

.nav-icon-wrapper {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s ease;
}

.nav-text {
  flex: 1;
}

.nav-indicator {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #6366f1;
  opacity: 0;
  transition: opacity 0.3s ease;
}

.nav-item.active .nav-indicator {
  opacity: 1;
}

.sidebar-footer {
  margin-top: auto;
  padding-top: 0.65rem;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.system-status {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.55rem 0.65rem;
  font-size: 0.75rem;
  color: #64748b;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
}

/* 主内容区 */
.main-content {
  flex: 1;
  min-width: 0;
  background: rgba(17, 17, 24, 0.4);
  backdrop-filter: blur(20px);
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  overflow: hidden;
}

/* 页面过渡动画 */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
