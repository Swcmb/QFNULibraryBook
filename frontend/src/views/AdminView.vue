<script setup>
// AdminView：管理面板
// 保留原版浅灰背景 + 卡片样式
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import PasswordInput from '../components/PasswordInput.vue'
import { authStore, adminLogin, adminLogout } from '../stores/auth'
import * as api from '../api/client'

// ============== 登录态 ==============
const loginPassword = ref('')
const loginLoading = ref(false)

async function handleAdminLogin() {
  if (!loginPassword.value) {
    window.$toast?.warning('请输入访问密码')
    return
  }
  loginLoading.value = true
  try {
    const res = await adminLogin(loginPassword.value)
    if (res.ok && res.success) {
      window.$toast?.success('登录成功')
      loginPassword.value = ''
      await loadAll()
    } else {
      window.$toast?.error(res.message || '密码错误')
    }
  } finally {
    loginLoading.value = false
  }
}

async function handleAdminLogout() {
  await adminLogout()
  window.$toast?.success('已退出')
}

// ============== 抢座任务 ==============
const grabStatus = ref({
  running: false,
  started_at: null,
  finished_at: null,
  results: []
})
const grabLoading = ref(false)
let grabTimer = null

// 抢座状态徽章
const grabBadge = computed(() => {
  if (grabStatus.value.running) {
    return { text: '运行中', class: 'badge-running' }
  }
  if (grabStatus.value.results && grabStatus.value.results.length > 0) {
    const hasFail = grabStatus.value.results.some((r) => !r.success)
    if (hasFail) return { text: '部分失败', class: 'badge-warning' }
    return { text: '全部成功', class: 'badge-success' }
  }
  return { text: '空闲', class: 'badge-idle' }
})

async function loadGrabStatus() {
  const res = await api.getGrabStatus()
  if (res.ok && res.success && res.state) {
    grabStatus.value = res.state
    // 如果仍在运行，启动轮询
    if (res.state.running && !grabTimer) {
      startGrabPolling()
    }
  }
}

async function triggerGrab() {
  if (!confirm('确定要立即执行抢座任务吗？')) return
  grabLoading.value = true
  try {
    const res = await api.triggerGrab()
    if (res.ok && res.success) {
      window.$toast?.success('抢座任务已触发')
      await loadGrabStatus()
      startGrabPolling()
    } else {
      window.$toast?.error(res.message || '触发失败')
    }
  } finally {
    grabLoading.value = false
  }
}

// 轮询抢座状态
function startGrabPolling() {
  if (grabTimer) return
  grabTimer = setInterval(async () => {
    await loadGrabStatus()
    if (!grabStatus.value.running) {
      stopGrabPolling()
      window.$toast?.info('抢座任务已结束')
    }
  }, 3000)
}

function stopGrabPolling() {
  if (grabTimer) {
    clearInterval(grabTimer)
    grabTimer = null
  }
}

// ============== 抢座顺序 ==============
const grabOrder = ref([])

function moveUp(idx) {
  if (idx === 0) return
  const arr = grabOrder.value
  ;[arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]]
}

function moveDown(idx) {
  const arr = grabOrder.value
  if (idx === arr.length - 1) return
  ;[arr[idx + 1], arr[idx]] = [arr[idx], arr[idx + 1]]
}

const orderSaving = ref(false)
async function saveOrder() {
  orderSaving.value = true
  try {
    const res = await api.updateGrabOrder(grabOrder.value)
    if (res.ok && res.success) {
      window.$toast?.success('顺序已保存')
    } else {
      window.$toast?.error(res.message || '保存失败')
    }
  } finally {
    orderSaving.value = false
  }
}

// ============== 账号管理 ==============
const users = ref([])
const usersLoading = ref(false)

async function loadUsers() {
  usersLoading.value = true
  try {
    const res = await api.getAdminUsers()
    if (res.ok && res.success) {
      users.value = res.users || []
      // 同步抢座顺序：以现有用户名为准
      syncGrabOrder()
    }
  } finally {
    usersLoading.value = false
  }
}

// 同步抢座顺序列表
function syncGrabOrder() {
  const names = users.value.map((u) => u.username)
  // 保留原有顺序中仍存在的用户
  const existing = grabOrder.value.filter((n) => names.includes(n))
  // 追加新增用户
  names.forEach((n) => {
    if (!existing.includes(n)) existing.push(n)
  })
  grabOrder.value = existing
}

// 模式映射
const modeMap = {
  1: '指定范围内随机',
  2: '靠近插座',
  3: '随机',
  4: '指定座位号优先级'
}

// 通知渠道映射
const pushMethodMap = {
  '': '无',
  DD: '钉钉',
  TG: 'Telegram',
  BARK: 'Bark',
  ANPUSH: 'AnPush'
}

// ============== 账号编辑模态框 ==============
const modalVisible = ref(false)
const modalMode = ref('create') // create | edit
const editingOriginalUsername = ref('')
const form = reactive({
  username: '',
  password: '',
  mode: 1,
  seat_id: [], // 模式1: [{start, end}]; 模式4: [单个座位号]
  classrooms_name: '',
  date: 'today',
  push_method: '',
  dd_bot_token: '',
  dd_bot_secret: ''
})

function openCreateModal() {
  modalMode.value = 'create'
  editingOriginalUsername.value = ''
  Object.assign(form, {
    username: '',
    password: '',
    mode: 1,
    seat_id: [{ start: '', end: '' }],
    classrooms_name: '',
    date: 'today',
    push_method: '',
    dd_bot_token: '',
    dd_bot_secret: ''
  })
  modalVisible.value = true
}

function openEditModal(user) {
  modalMode.value = 'edit'
  editingOriginalUsername.value = user.username
  // 解析座位配置
  let seatId = user.seat_id
  if (typeof seatId === 'string') {
    try {
      seatId = JSON.parse(seatId)
    } catch {
      seatId = []
    }
  }
  // 兼容后端格式：模式1为数组范围对，模式4为单个座位号数组
  let normalizedSeat = []
  if (user.mode === 1) {
    normalizedSeat = Array.isArray(seatId) && seatId.length ? seatId.map((s) => {
      if (typeof s === 'object') return { start: s.start ?? '', end: s.end ?? '' }
      return { start: '', end: '' }
    }) : [{ start: '', end: '' }]
  } else if (user.mode === 4) {
    normalizedSeat = Array.isArray(seatId) ? seatId : []
  }

  Object.assign(form, {
    username: user.username,
    password: user.password || '',
    mode: user.mode || 1,
    seat_id: normalizedSeat,
    classrooms_name: Array.isArray(user.classrooms_name)
      ? user.classrooms_name.join('\n')
      : (user.classrooms_name || ''),
    date: user.date || 'today',
    push_method: user.push_method || '',
    dd_bot_token: user.dd_bot_token || '',
    dd_bot_secret: user.dd_bot_secret || ''
  })
  modalVisible.value = true
}

// 模式切换时重置座位配置
function onModeChange() {
  if (form.mode === 1) {
    form.seat_id = [{ start: '', end: '' }]
  } else if (form.mode === 4) {
    form.seat_id = ['']
  } else {
    form.seat_id = []
  }
}

// 模式1：新增范围行
function addRange() {
  form.seat_id.push({ start: '', end: '' })
}

// 模式1：删除范围行
function removeRange(idx) {
  form.seat_id.splice(idx, 1)
}

// 模式4：新增座位号
function addSeat() {
  form.seat_id.push('')
}

// 模式4：删除座位号
function removeSeat(idx) {
  form.seat_id.splice(idx, 1)
}

const modalSaving = ref(false)

async function saveUser() {
  if (!form.username || !form.password) {
    window.$toast?.warning('请填写学号和密码')
    return
  }

  // 编辑时若改学号需二次确认
  if (
    modalMode.value === 'edit' &&
    form.username !== editingOriginalUsername.value
  ) {
    if (!confirm(`确定要将学号从 "${editingOriginalUsername.value}" 修改为 "${form.username}" 吗？`)) {
      return
    }
  }

  // 组装数据
  const payload = {
    username: form.username,
    password: form.password,
    mode: Number(form.mode),
    seat_id: form.seat_id,
    classrooms_name: form.classrooms_name
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean),
    date: form.date,
    push_method: form.push_method,
    dd_bot_token: form.dd_bot_token,
    dd_bot_secret: form.dd_bot_secret
  }

  modalSaving.value = true
  try {
    let res
    if (modalMode.value === 'create') {
      res = await api.createAdminUser(payload)
    } else {
      res = await api.updateAdminUser(editingOriginalUsername.value, payload)
    }
    if (res.ok && res.success) {
      window.$toast?.success(modalMode.value === 'create' ? '账号已添加' : '账号已更新')
      modalVisible.value = false
      await loadUsers()
    } else {
      window.$toast?.error(res.message || '保存失败')
    }
  } finally {
    modalSaving.value = false
  }
}

async function deleteUser(username) {
  if (!confirm(`确定要删除账号 "${username}" 吗？此操作不可恢复。`)) return
  const res = await api.deleteAdminUser(username)
  if (res.ok && res.success) {
    window.$toast?.success('账号已删除')
    await loadUsers()
  } else {
    window.$toast?.error(res.message || '删除失败')
  }
}

// ============== 操作日志 ==============
const logLines = ref(100)
const logContent = ref('')
const logLoading = ref(false)

async function loadLogs() {
  logLoading.value = true
  try {
    const res = await api.getAdminLogs(Number(logLines.value) || 100)
    if (res.ok && res.success) {
      logContent.value = res.logs || ''
    } else {
      window.$toast?.error(res.message || '获取日志失败')
    }
  } finally {
    logLoading.value = false
  }
}

// ============== 初始化 ==============
async function loadAll() {
  await Promise.all([loadUsers(), loadGrabStatus(), loadLogs()])
}

onMounted(async () => {
  if (authStore.adminAuthed) {
    await loadAll()
  }
})

onUnmounted(() => {
  stopGrabPolling()
})
</script>

<template>
  <div class="admin-page light-theme">
    <!-- 未登录：登录卡片 -->
    <div v-if="!authStore.adminAuthed" class="login-wrap">
      <div class="login-card">
        <div class="login-title">
          <span class="lock-icon">🔒</span>
          <span>管理面板</span>
        </div>
        <p class="login-desc">请输入访问密码</p>
        <div class="login-form">
          <PasswordInput v-model="loginPassword" placeholder="访问密码" />
          <button class="btn btn-primary btn-block" :disabled="loginLoading" @click="handleAdminLogin">
            <span v-if="loginLoading" class="spinner spinner-dark"></span>
            <span>{{ loginLoading ? '验证中...' : '进 入' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- 已登录：主面板 -->
    <div v-else class="container">
      <!-- 顶部欢迎条 -->
      <div class="topbar">
        <div class="topbar-title">
          <span class="icon">⚙️</span>
          <span>管理面板</span>
        </div>
        <button class="btn btn-default btn-sm" @click="handleAdminLogout">退出登录</button>
      </div>

      <!-- 抢座任务卡片 -->
      <section class="card-block">
        <div class="block-header">
          <h2 class="block-title">🚀 抢座任务</h2>
          <span class="badge" :class="grabBadge.class">{{ grabBadge.text }}</span>
        </div>
        <div class="block-actions">
          <button class="btn btn-primary btn-sm" :disabled="grabLoading || grabStatus.running" @click="triggerGrab">
            <span v-if="grabLoading" class="spinner spinner-dark"></span>
            <span>{{ grabLoading ? '触发中...' : '立即抢座' }}</span>
          </button>
          <button class="btn btn-default btn-sm" @click="loadGrabStatus">🔄 刷新</button>
        </div>
        <div v-if="grabStatus.results && grabStatus.results.length" class="grab-results">
          <div class="results-title">执行结果：</div>
          <div
            v-for="(r, i) in grabStatus.results"
            :key="i"
            class="result-row"
            :class="r.success ? 'row-success' : 'row-error'"
          >
            <span class="row-user">{{ r.username }}</span>
            <span class="row-status">{{ r.success ? '成功' : '失败' }}</span>
            <span v-if="r.error" class="row-error-msg">{{ r.error }}</span>
          </div>
        </div>
        <div v-if="grabStatus.started_at" class="grab-meta">
          <span>开始：{{ grabStatus.started_at }}</span>
          <span v-if="grabStatus.finished_at">结束：{{ grabStatus.finished_at }}</span>
        </div>
      </section>

      <!-- 抢座执行顺序卡片 -->
      <section class="card-block">
        <div class="block-header">
          <h2 class="block-title">📋 抢座执行顺序</h2>
        </div>
        <p class="block-hint">使用上下按钮调整执行顺序，保存后生效。</p>
        <div v-if="grabOrder.length === 0" class="empty">暂无账号</div>
        <ul v-else class="order-list">
          <li v-for="(name, idx) in grabOrder" :key="name" class="order-item">
            <span class="order-index">{{ idx + 1 }}</span>
            <span class="order-name">{{ name }}</span>
            <span class="order-ctrl">
              <button class="mini-btn" :disabled="idx === 0" @click="moveUp(idx)">↑</button>
              <button class="mini-btn" :disabled="idx === grabOrder.length - 1" @click="moveDown(idx)">↓</button>
            </span>
          </li>
        </ul>
        <button class="btn btn-success btn-sm" :disabled="orderSaving" @click="saveOrder">💾 保存顺序</button>
      </section>

      <!-- 账号管理卡片 -->
      <section class="card-block">
        <div class="block-header">
          <h2 class="block-title">👥 账号管理</h2>
          <button class="btn btn-primary btn-sm" @click="openCreateModal">＋ 新增账号</button>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>学号</th>
                <th>密码</th>
                <th>模式</th>
                <th>座位</th>
                <th>教室</th>
                <th>日期</th>
                <th>通知</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="usersLoading">
                <td colspan="8" class="empty">加载中...</td>
              </tr>
              <tr v-else-if="users.length === 0">
                <td colspan="8" class="empty">暂无账号</td>
              </tr>
              <tr v-for="u in users" :key="u.username">
                <td>{{ u.username }}</td>
                <td>******</td>
                <td>{{ modeMap[u.mode] || u.mode }}</td>
                <td class="seat-cell">
                  <span v-if="u.mode === 1">
                    <template v-if="Array.isArray(u.seat_id)">
                      {{ u.seat_id.map(s => `${s.start}-${s.end}`).join(', ') }}
                    </template>
                    <template v-else>{{ u.seat_id }}</template>
                  </span>
                  <span v-else-if="u.mode === 4">
                    <template v-if="Array.isArray(u.seat_id)">{{ u.seat_id.join(', ') }}</template>
                    <template v-else>{{ u.seat_id }}</template>
                  </span>
                  <span v-else>—</span>
                </td>
                <td class="classroom-cell">
                  {{ Array.isArray(u.classrooms_name) ? u.classrooms_name.join(', ') : u.classrooms_name }}
                </td>
                <td>{{ u.date === 'today' ? '今天' : (u.date === 'tomorrow' ? '明天' : u.date) }}</td>
                <td>{{ pushMethodMap[u.push_method] || u.push_method || '无' }}</td>
                <td>
                  <div class="row-actions">
                    <button class="btn btn-default btn-sm" @click="openEditModal(u)">编辑</button>
                    <button class="btn btn-danger btn-sm" @click="deleteUser(u.username)">删除</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 操作日志卡片 -->
      <section class="card-block">
        <div class="block-header">
          <h2 class="block-title">📜 操作日志</h2>
          <div class="log-ctrl">
            <input v-model.number="logLines" type="number" min="1" max="1000" class="log-lines-input" />
            <span>行</span>
            <button class="btn btn-default btn-sm" :disabled="logLoading" @click="loadLogs">🔄 刷新</button>
          </div>
        </div>
        <pre class="log-box">{{ logLoading ? '加载中...' : (logContent || '暂无日志') }}</pre>
      </section>
    </div>

    <!-- 账号编辑模态框 -->
    <div v-if="modalVisible" class="modal-mask" @click.self="modalVisible = false">
      <div class="modal-dialog">
        <div class="modal-header">
          <h3>{{ modalMode === 'create' ? '新增账号' : '编辑账号' }}</h3>
          <button class="modal-close" @click="modalVisible = false">×</button>
        </div>
        <div class="modal-body">
          <div class="form-row">
            <div class="form-col">
              <label class="field-label">学号</label>
              <input v-model="form.username" type="text" class="field-input" placeholder="学号" />
            </div>
            <div class="form-col">
              <label class="field-label">密码</label>
              <PasswordInput v-model="form.password" placeholder="密码" />
            </div>
          </div>

          <div class="form-row">
            <div class="form-col">
              <label class="field-label">抢座模式</label>
              <select v-model="form.mode" class="field-select" @change="onModeChange">
                <option :value="1">1 - 指定范围内随机</option>
                <option :value="2">2 - 靠近插座</option>
                <option :value="3">3 - 随机</option>
                <option :value="4">4 - 指定座位号优先级</option>
              </select>
            </div>
            <div class="form-col">
              <label class="field-label">预约日期</label>
              <select v-model="form.date" class="field-select">
                <option value="today">今天</option>
                <option value="tomorrow">明天</option>
              </select>
            </div>
          </div>

          <!-- 模式1：范围行 -->
          <div v-if="form.mode === 1" class="form-row-block">
            <label class="field-label">座位范围（起始号 - 结束号）</label>
            <div v-for="(r, i) in form.seat_id" :key="i" class="range-row">
              <input v-model="r.start" type="text" class="field-input" placeholder="起始号" />
              <span class="range-dash">-</span>
              <input v-model="r.end" type="text" class="field-input" placeholder="结束号" />
              <button class="btn btn-danger btn-sm" @click="removeRange(i)">删</button>
            </div>
            <button class="btn btn-default btn-sm" @click="addRange">＋ 添加范围</button>
          </div>

          <!-- 模式4：单个座位号 -->
          <div v-if="form.mode === 4" class="form-row-block">
            <label class="field-label">座位号列表</label>
            <div v-for="(s, i) in form.seat_id" :key="i" class="seat-row">
              <input v-model="form.seat_id[i]" type="text" class="field-input" placeholder="座位号" />
              <button class="btn btn-danger btn-sm" @click="removeSeat(i)">删</button>
            </div>
            <button class="btn btn-default btn-sm" @click="addSeat">＋ 添加座位号</button>
          </div>

          <div class="form-row-block">
            <label class="field-label">教室名称（每行一个）</label>
            <textarea v-model="form.classrooms_name" class="field-textarea" placeholder="教室1&#10;教室2"></textarea>
          </div>

          <div class="form-row">
            <div class="form-col">
              <label class="field-label">通知渠道</label>
              <select v-model="form.push_method" class="field-select">
                <option value="">无</option>
                <option value="DD">钉钉</option>
                <option value="TG">Telegram</option>
                <option value="BARK">Bark</option>
                <option value="ANPUSH">AnPush</option>
              </select>
            </div>
          </div>

          <div v-if="form.push_method === 'DD'" class="form-row-block">
            <div class="form-row">
              <div class="form-col">
                <label class="field-label">钉钉 Token</label>
                <input v-model="form.dd_bot_token" type="text" class="field-input" placeholder="钉钉机器人 Token" />
              </div>
              <div class="form-col">
                <label class="field-label">钉钉 Secret</label>
                <input v-model="form.dd_bot_secret" type="text" class="field-input" placeholder="加签 Secret" />
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-default" @click="modalVisible = false">取消</button>
          <button class="btn btn-primary" :disabled="modalSaving" @click="saveUser">
            <span v-if="modalSaving" class="spinner spinner-dark"></span>
            <span>{{ modalSaving ? '保存中...' : '保 存' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-page {
  min-height: 100vh;
  background: #f5f7fa;
}

/* ============== 登录卡片 ============== */
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 380px;
  background: #fff;
  border-radius: 16px;
  padding: 36px 28px;
  box-shadow: var(--shadow-md);
  text-align: center;
}

.login-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.lock-icon {
  font-size: 24px;
}

.login-desc {
  color: var(--color-text-secondary);
  font-size: 14px;
  margin-bottom: 20px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* ============== 主面板 ============== */
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 20px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  padding: 16px 24px;
  border-radius: 12px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-sm);
}

.topbar-title {
  font-size: 18px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-block {
  background: #fff;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-sm);
}

.block-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 10px;
}

.block-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.block-hint {
  color: var(--color-text-secondary);
  font-size: 13px;
  margin-bottom: 12px;
}

.block-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

/* 徽章 */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.badge-idle {
  background: #f0f0f0;
  color: #909399;
}

.badge-running {
  background: #e6f4ff;
  color: #2b5ca8;
}

.badge-success {
  background: #e8f8ef;
  color: #07c160;
}

.badge-warning {
  background: #fff5e6;
  color: #f0a020;
}

/* 抢座结果 */
.grab-results {
  margin-top: 12px;
  border-top: 1px solid #ebeef5;
  padding-top: 12px;
}

.results-title {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 8px;
}

.result-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 13px;
}

.row-success {
  background: #f0faf3;
  color: #07c160;
}

.row-error {
  background: #fef0f0;
  color: #e94d4d;
}

.row-user {
  font-weight: 600;
  min-width: 120px;
}

.row-status {
  min-width: 50px;
}

.row-error-msg {
  flex: 1;
  color: var(--color-text-regular);
}

.grab-meta {
  display: flex;
  gap: 20px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* 顺序列表 */
.order-list {
  list-style: none;
  margin-bottom: 14px;
}

.order-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: #f9fafc;
  border-radius: 6px;
  margin-bottom: 6px;
}

.order-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}

.order-name {
  flex: 1;
  font-size: 14px;
}

.order-ctrl {
  display: flex;
  gap: 4px;
}

.mini-btn {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  background: #fff;
  border: 1px solid var(--color-border);
  cursor: pointer;
  font-size: 14px;
  color: var(--color-text-regular);
}

.mini-btn:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.mini-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.empty {
  text-align: center;
  color: var(--color-text-secondary);
  padding: 20px;
  font-size: 14px;
}

/* 表格 */
.table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table th,
.data-table td {
  padding: 12px 10px;
  text-align: left;
  border-bottom: 1px solid #ebeef5;
  white-space: nowrap;
}

.data-table th {
  background: #f9fafc;
  color: var(--color-text-regular);
  font-weight: 600;
}

.data-table tbody tr:hover {
  background: #f9fafc;
}

.seat-cell,
.classroom-cell {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-actions {
  display: flex;
  gap: 6px;
}

/* 日志 */
.log-ctrl {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.log-lines-input {
  width: 70px;
  padding: 6px 8px;
  border: 1px solid var(--color-border);
  border-radius: 4px;
  font-size: 13px;
}

.log-box {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 16px;
  border-radius: 8px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.6;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 模态框 */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-dialog {
  background: #fff;
  border-radius: 12px;
  width: 100%;
  max-width: 640px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #ebeef5;
}

.modal-header h3 {
  font-size: 16px;
  font-weight: 600;
}

.modal-close {
  background: transparent;
  border: none;
  font-size: 24px;
  color: var(--color-text-secondary);
  cursor: pointer;
  line-height: 1;
}

.modal-close:hover {
  color: var(--color-text-primary);
}

.modal-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid #ebeef5;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}

.form-col {
  display: flex;
  flex-direction: column;
}

.form-row-block {
  margin-bottom: 14px;
}

.range-row,
.seat-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.range-row .field-input,
.seat-row .field-input {
  flex: 1;
}

.range-dash {
  color: var(--color-text-secondary);
}

@media (max-width: 768px) {
  .container {
    padding: 12px;
  }
  .card-block {
    padding: 16px;
  }
  .form-row {
    grid-template-columns: 1fr;
  }
  .data-table {
    font-size: 12px;
  }
  .data-table th,
  .data-table td {
    padding: 8px 6px;
  }
}
</style>
