<script setup>
// HomeView：用户登录 + 签到/签退页
// 保留原版蓝色渐变背景 + 玻璃拟态卡片风格
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import PasswordInput from '../components/PasswordInput.vue'
import { authStore, checkStatus, userLogin, userLogout } from '../stores/auth'
import * as api from '../api/client'

const router = useRouter()

// 登录表单
const username = ref('')
const password = ref('')
const loading = ref(false)
const statusLoading = ref(false)

// 操作结果
const result = ref(null) // { type: 'success' | 'error', message: '' }

// 签到/签退 loading
const checkinLoading = ref(false)
const signoutLoading = ref(false)

// 进入页面时检查登录态
onMounted(async () => {
  statusLoading.value = true
  await checkStatus()
  statusLoading.value = false
})

// 触发登录
async function handleLogin() {
  if (!username.value || !password.value) {
    window.$toast?.warning('请输入学号和密码')
    return
  }
  loading.value = true
  result.value = null
  try {
    const res = await userLogin(username.value, password.value)
    if (res.ok && res.success) {
      window.$toast?.success('登录成功')
      await checkStatus()
      username.value = ''
      password.value = ''
    } else {
      result.value = {
        type: 'error',
        message: res.message || '登录失败，请检查学号密码'
      }
      window.$toast?.error(res.message || '登录失败')
    }
  } finally {
    loading.value = false
  }
}

// 签到
async function handleCheckin() {
  checkinLoading.value = true
  result.value = null
  try {
    const res = await api.checkin()
    if (res.ok && res.success) {
      result.value = { type: 'success', message: res.message || '签到成功' }
      window.$toast?.success(res.message || '签到成功')
    } else {
      result.value = { type: 'error', message: res.message || '签到失败' }
      window.$toast?.error(res.message || '签到失败')
    }
  } finally {
    checkinLoading.value = false
  }
}

// 签退
async function handleSignout() {
  signoutLoading.value = true
  result.value = null
  try {
    const res = await api.signout()
    if (res.ok && res.success) {
      result.value = { type: 'success', message: res.message || '签退成功' }
      window.$toast?.success(res.message || '签退成功')
    } else {
      result.value = { type: 'error', message: res.message || '签退失败' }
      window.$toast?.error(res.message || '签退失败')
    }
  } finally {
    signoutLoading.value = false
  }
}

// 退出登录
async function handleLogout() {
  await userLogout()
  result.value = null
  window.$toast?.success('已退出登录')
}

// 跳转订阅页
function goPlans() {
  router.push('/plans')
}

// 回车键触发登录
function onKeydown(e) {
  if (e.key === 'Enter' && !authStore.loggedIn) {
    handleLogin()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="home-page">
    <div class="card">
      <!-- Logo 区 -->
      <div class="logo-area">
        <div class="logo-badge">QFNU</div>
        <h1 class="title">曲阜师范大学图书馆</h1>
        <p class="subtitle">座位管理系统</p>
      </div>

      <!-- 状态加载中 -->
      <div v-if="statusLoading" class="status-loading">
        <span class="spinner spinner-dark"></span>
        <span>正在检查登录状态...</span>
      </div>

      <!-- 未登录：显示登录表单 -->
      <template v-else-if="!authStore.loggedIn">
        <div class="form-area">
          <div class="form-item">
            <label class="field-label" for="username">学号</label>
            <input
              id="username"
              v-model="username"
              type="text"
              class="field-input-dark"
              placeholder="请输入学号"
              autocomplete="off"
            />
          </div>
          <div class="form-item">
            <label class="field-label" for="password">密码</label>
            <PasswordInput id="password" v-model="password" placeholder="请输入密码" />
          </div>
          <button class="btn btn-primary btn-block btn-lg login-btn" :disabled="loading" @click="handleLogin">
            <span v-if="loading" class="spinner"></span>
            <span>{{ loading ? '登录中...' : '登 录' }}</span>
          </button>
          <div class="links">
            <a href="https://ids.qfnu.edu.cn/authserver/login" target="_blank" rel="noopener">账号激活</a>
            <span class="divider">|</span>
            <a href="https://ids.qfnu.edu.cn/authserver/getBackPassword" target="_blank" rel="noopener">忘记密码</a>
          </div>
        </div>
      </template>

      <!-- 已登录：显示控制面板 -->
      <template v-else>
        <div class="panel-area">
          <div class="welcome">
            <span class="welcome-icon">👋</span>
            <span>欢迎，<strong>{{ authStore.username }}</strong></span>
          </div>
          <div class="action-grid">
            <button class="action-btn action-checkin" :disabled="checkinLoading" @click="handleCheckin">
              <span v-if="checkinLoading" class="spinner"></span>
              <span v-else class="action-icon">✓</span>
              <span>{{ checkinLoading ? '签到中...' : '签到' }}</span>
            </button>
            <button class="action-btn action-signout" :disabled="signoutLoading" @click="handleSignout">
              <span v-if="signoutLoading" class="spinner"></span>
              <span v-else class="action-icon">⏏</span>
              <span>{{ signoutLoading ? '签退中...' : '签退' }}</span>
            </button>
          </div>
          <button class="btn btn-default btn-block" @click="goPlans">📅 订阅服务</button>
          <button class="btn btn-default btn-block logout-btn" @click="handleLogout">退出登录</button>
        </div>
      </template>

      <!-- 结果展示区 -->
      <div v-if="result" class="result-box" :class="`result-${result.type}`">
        <span class="result-icon">{{ result.type === 'success' ? '✓' : '✕' }}</span>
        <span>{{ result.message }}</span>
      </div>
    </div>

    <!-- 页脚 -->
    <footer class="footer">曲阜师范大学 All Rights Reserved</footer>
  </div>
</template>

<style scoped>
.home-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #1a3a6b 0%, #2b5ca8 50%, #1a3a6b 100%);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.card {
  width: 100%;
  max-width: 400px;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  padding: 36px 28px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
}

.logo-area {
  text-align: center;
  margin-bottom: 28px;
}

.logo-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  margin-bottom: 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.3);
  color: #fff;
  font-weight: 700;
  font-size: 16px;
  letter-spacing: 1px;
}

.title {
  color: #fff;
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 6px;
}

.subtitle {
  color: rgba(255, 255, 255, 0.7);
  font-size: 13px;
}

.status-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: rgba(255, 255, 255, 0.85);
  padding: 24px 0;
  font-size: 14px;
}

.form-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-item {
  display: flex;
  flex-direction: column;
}

.field-input-dark {
  width: 100%;
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  outline: none;
  transition: all 0.2s;
  box-sizing: border-box;
}

.field-input-dark::placeholder {
  color: rgba(255, 255, 255, 0.6);
}

.field-input-dark:focus {
  border-color: rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.18);
}

.login-btn {
  margin-top: 6px;
}

.links {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin-top: 8px;
  font-size: 13px;
}

.links a {
  color: rgba(255, 255, 255, 0.8);
  transition: color 0.2s;
}

.links a:hover {
  color: #fff;
  text-decoration: underline;
}

.divider {
  color: rgba(255, 255, 255, 0.4);
}

.panel-area {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.welcome {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #fff;
  font-size: 16px;
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  margin-bottom: 4px;
}

.welcome strong {
  color: #ffd700;
}

.action-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 18px 12px;
  border-radius: 12px;
  font-size: 14px;
  font-weight: 500;
  color: #fff;
  transition: all 0.2s;
  border: none;
  cursor: pointer;
  min-height: 90px;
}

.action-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.action-icon {
  font-size: 22px;
}

.action-checkin {
  background: linear-gradient(135deg, #07c160 0%, #06a552 100%);
}

.action-checkin:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(7, 193, 96, 0.4);
}

.action-signout {
  background: linear-gradient(135deg, #f0a020 0%, #d68a12 100%);
}

.action-signout:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(240, 160, 32, 0.4);
}

.logout-btn {
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.2);
}

.logout-btn:hover {
  background: rgba(255, 255, 255, 0.2);
}

.result-box {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  color: #fff;
  animation: result-in 0.25s ease;
}

@keyframes result-in {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.result-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
  font-weight: bold;
  flex-shrink: 0;
}

.result-success {
  background: rgba(7, 193, 96, 0.85);
}

.result-error {
  background: rgba(233, 77, 77, 0.85);
}

.footer {
  margin-top: 24px;
  color: rgba(255, 255, 255, 0.6);
  font-size: 12px;
  text-align: center;
}

@media (max-width: 480px) {
  .card {
    padding: 28px 20px;
  }
  .title {
    font-size: 18px;
  }
}
</style>
