<template>
  <div class="app-container">
    <!-- 登录界面 - 使用v-if确保组件完全销毁和重建 -->
    <LoginView v-if="!isAuthenticated" />
    
    <!-- 主应用界面 -->
    <div v-else class="main-wrapper">
      <!-- 顶部标题栏 -->
      <header class="app-header">
        <div class="header-title">
          <span class="app-logo">📄</span>
          <h1>文档智能提取系统</h1>
        </div>
        <div class="header-user">
          <span class="user-name">{{ currentUser.username }}</span>
          <button @click="logout" class="logout-btn">退出</button>
        </div>
      </header>

      <!-- 主体内容区 -->
      <div class="content-wrapper">
        <!-- 左侧导航栏 -->
        <aside class="sidebar">
          <nav class="sidebar-nav">
            <router-link to="/" class="nav-item">
              <span class="nav-icon">📁</span>
              <span class="nav-text">上传文档</span>
            </router-link>
            <router-link to="/tasks" class="nav-item">
              <span class="nav-icon">📋</span>
              <span class="nav-text">任务列表</span>
            </router-link>
          </nav>
        </aside>

        <!-- 主内容区 -->
        <main class="main-content">
          <div class="app-window">
            <router-view />
          </div>
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import LoginView from './views/Login.vue'

const router = useRouter()
const currentUser = ref({})

const isAuthenticated = computed(() => {
  const user = localStorage.getItem('user')
  return user !== null && user !== 'null'
})

const logout = () => {
  localStorage.removeItem('user')
  currentUser.value = {}
  // 清除路由状态
  router.replace('/')
}

// 监听认证状态变化
watch(() => isAuthenticated.value, (newValue) => {
  if (newValue) {
    const user = localStorage.getItem('user')
    if (user) {
      try {
        currentUser.value = JSON.parse(user)
      } catch (e) {
        console.error('解析用户信息失败:', e)
        // 如果解析失败，强制退出
        logout()
      }
    }
  } else {
    currentUser.value = {}
  }
})

onMounted(() => {
  const user = localStorage.getItem('user')
  if (user) {
    try {
      currentUser.value = JSON.parse(user)
    } catch (e) {
      console.error('解析用户信息失败:', e)
      // 如果解析失败，强制退出
      logout()
    }
  }
})
</script>

<style scoped>
.app-container {
  min-height: 100vh;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  flex-direction: column;
}

/* 登录界面全屏显示 */
.app-container > .login-container {
  flex: 1;
  width: 100%;
}

.main-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  margin: 0 auto;
  max-width: 1400px;
  background: white;
  box-shadow: 0 0 30px rgba(0, 0, 0, 0.2);
  border-radius: 10px;
  margin-top: 1rem;
  margin-bottom: 1rem;
  overflow: hidden;
}

/* 顶部标题栏 */
.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.8rem 1.5rem;
  background: linear-gradient(90deg, #4a5568 0%, #2d3748 100%);
  color: white;
  border-bottom: 1px solid #e2e8f0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.app-logo {
  font-size: 1.5rem;
}

.header-title h1 {
  margin: 0;
  font-size: 1.3rem;
  font-weight: 600;
}

.header-user {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user-name {
  font-weight: 500;
  font-size: 0.95rem;
}

.logout-btn {
  padding: 0.4rem 1rem;
  background: #e74c3c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.3s;

  &:hover {
    background: #c0392b;
    transform: translateY(-1px);
  }
}

/* 主体内容区 */
.content-wrapper {
  display: flex;
  flex: 1;
}

/* 左侧导航栏 */
.sidebar {
  width: 200px;
  background: #f7fafc;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
}

.sidebar-nav {
  padding: 1rem 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 1rem 1.2rem;
  text-decoration: none;
  color: #4a5568;
  font-weight: 500;
  transition: all 0.3s;
  border-left: 3px solid transparent;
  font-size: 0.95rem;

  &:hover {
    background: #edf2f7;
    color: #667eea;
  }

  &.router-link-active {
    background: #e6fffa;
    color: #2b6cb0;
    border-left-color: #2b6cb0;
  }
}

.nav-icon {
  font-size: 1.2rem;
}

/* 主内容区 */
.main-content {
  flex: 1;
  padding: 1.5rem;
  background: #fafcff;
  overflow-y: auto;
}

.app-window {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  padding: 1.5rem;
  height: calc(100vh - 140px);
  overflow-y: auto;
}
</style>