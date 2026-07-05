<script setup>
// PlansView：订阅服务页
// 保留原版蓝色渐变背景 + 套餐卡片网格风格
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { authStore, checkStatus } from '../stores/auth'
import * as api from '../api/client'

const router = useRouter()

// 套餐列表
const plans = ref([])
const loading = ref(false)

// 购买模态框
const purchaseVisible = ref(false)
const selectedPlan = ref(null)
const activationCode = ref('')
const activating = ref(false)

// 激活成功
const activateResult = ref(null)

// 当前登录用户
const currentUser = ref('')

// 是否已登录
const isLoggedIn = computed(() => authStore.loggedIn)

// 初始化
onMounted(async () => {
  loading.value = true
  try {
    // 并行加载套餐列表、检查登录态、检查订阅状态
    const [plansRes] = await Promise.all([
      api.getPlans(),
      checkStatus(),
      api.getPlanStatus()
    ])
    if (plansRes.ok && plansRes.success) {
      plans.value = plansRes.plans || []
    } else {
      window.$toast?.error(plansRes.message || '获取套餐失败')
    }
    // 同步当前用户名
    currentUser.value = authStore.username
  } finally {
    loading.value = false
  }
})

// 打开购买模态框
function openPurchase(plan) {
  selectedPlan.value = plan
  activationCode.value = ''
  activateResult.value = null
  purchaseVisible.value = true
}

// 立即激活
async function handleActivate() {
  if (!selectedPlan.value) return
  if (!activationCode.value) {
    window.$toast?.warning('请输入激活码')
    return
  }
  activating.value = true
  try {
    const res = await api.activatePlan(activationCode.value, selectedPlan.value.id)
    if (res.ok && res.success) {
      activateResult.value = {
        message: res.message || '激活成功',
        expires_at: res.expires_at
      }
      window.$toast?.success('激活成功')
    } else {
      window.$toast?.error(res.message || '激活失败')
    }
  } finally {
    activating.value = false
  }
}

// 关闭模态框
function closePurchase() {
  purchaseVisible.value = false
  selectedPlan.value = null
  activationCode.value = ''
  activateResult.value = null
}

// 跳转登录
function goLogin() {
  router.push('/')
}

// 返回首页
function goHome() {
  router.push('/')
}

// 判断是否推荐套餐
function isRecommended(plan) {
  return plan.id === 'combo_monthly'
}

// 格式化价格
function formatPrice(price) {
  if (price === undefined || price === null) return '—'
  return `¥${price}`
}
</script>

<template>
  <div class="plans-page">
    <!-- 顶部标题区 -->
    <div class="header">
      <div class="header-inner">
        <button class="btn btn-default btn-sm back-btn" @click="goHome">← 返回</button>
        <h1 class="page-title">💎 订阅服务</h1>
        <p class="page-subtitle">选择适合您的套餐，享受自动化座位管理服务</p>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-wrap">
      <span class="spinner spinner-dark"></span>
      <span>加载中...</span>
    </div>

    <!-- 套餐网格 -->
    <div v-else-if="plans.length > 0" class="plans-grid">
      <div
        v-for="plan in plans"
        :key="plan.id"
        class="plan-card"
        :class="{ recommended: isRecommended(plan) }"
      >
        <div v-if="isRecommended(plan)" class="recommend-badge">推荐</div>
        <div class="plan-name">{{ plan.name }}</div>
        <div class="plan-desc">{{ plan.description }}</div>
        <div class="plan-price">
          <span class="price-symbol">¥</span>
          <span class="price-num">{{ plan.price }}</span>
        </div>
        <ul class="plan-features">
          <li v-if="plan.default_checkin_time">
            <span class="feat-icon">⏰</span>
            <span>每日签到：{{ plan.default_checkin_time }}</span>
          </li>
          <li v-if="plan.default_signout_time">
            <span class="feat-icon">🏁</span>
            <span>每日签退：{{ plan.default_signout_time }}</span>
          </li>
          <li v-if="plan.duration_days">
            <span class="feat-icon">📅</span>
            <span>有效期限：{{ plan.duration_days }} 天</span>
          </li>
          <li>
            <span class="feat-icon">🔔</span>
            <span>到期提醒</span>
          </li>
        </ul>
        <button class="btn btn-primary btn-block purchase-btn" @click="openPurchase(plan)">
          立即购买
        </button>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <div class="empty-icon">📦</div>
      <p>暂无可用的订阅套餐</p>
      <button class="btn btn-default" @click="goHome">返回首页</button>
    </div>

    <!-- 购买模态框 -->
    <div v-if="purchaseVisible" class="modal-mask" @click.self="closePurchase">
      <div class="modal-dialog">
        <!-- 激活成功界面 -->
        <div v-if="activateResult" class="success-view">
          <div class="success-icon">✓</div>
          <h3 class="success-title">激活成功</h3>
          <p class="success-msg">{{ activateResult.message }}</p>
          <p v-if="activateResult.expires_at" class="success-expire">
            到期时间：{{ activateResult.expires_at }}
          </p>
          <button class="btn btn-primary" @click="goHome">返回首页</button>
        </div>

        <!-- 购买/激活表单 -->
        <template v-else>
          <div class="modal-header">
            <h3>购买套餐</h3>
            <button class="modal-close" @click="closePurchase">×</button>
          </div>
          <div class="modal-body">
            <!-- 选中套餐信息 -->
            <div v-if="selectedPlan" class="selected-plan">
              <div class="sp-name">{{ selectedPlan.name }}</div>
              <div class="sp-price">¥{{ selectedPlan.price }}</div>
            </div>

            <!-- 微信支付提示区 -->
            <div class="wechat-tip">
              <span class="wechat-icon">💳</span>
              <span>微信支付</span>
              <span class="wechat-hint">（请通过微信扫码支付后获取激活码）</span>
            </div>

            <!-- 未登录提示 -->
            <div v-if="!isLoggedIn" class="login-tip">
              <p>⚠️ 请先登录</p>
              <button class="btn btn-primary btn-sm" @click="goLogin">去登录</button>
            </div>

            <!-- 激活表单 -->
            <div v-else class="activate-form">
              <div class="form-row">
                <label class="field-label">学号</label>
                <input
                  :value="currentUser"
                  type="text"
                  class="field-input"
                  readonly
                  placeholder="当前登录用户"
                />
              </div>
              <div class="form-row">
                <label class="field-label">激活码</label>
                <input
                  v-model="activationCode"
                  type="text"
                  class="field-input"
                  placeholder="请输入激活码"
                />
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="btn btn-default" @click="closePurchase">取消</button>
            <button
              v-if="isLoggedIn"
              class="btn btn-primary"
              :disabled="activating"
              @click="handleActivate"
            >
              <span v-if="activating" class="spinner spinner-dark"></span>
              <span>{{ activating ? '激活中...' : '立即激活' }}</span>
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.plans-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #1a3a6b 0%, #2b5ca8 50%, #1a3a6b 100%);
}

/* 顶部标题区 */
.header {
  padding: 40px 20px 30px;
}

.header-inner {
  max-width: 1100px;
  margin: 0 auto;
  text-align: center;
  position: relative;
}

.back-btn {
  position: absolute;
  left: 0;
  top: 0;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.3);
}

.back-btn:hover {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.5);
}

.page-title {
  color: #fff;
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 10px;
}

.page-subtitle {
  color: rgba(255, 255, 255, 0.8);
  font-size: 15px;
}

/* 加载中 */
.loading-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: rgba(255, 255, 255, 0.9);
  padding: 60px 0;
  font-size: 14px;
}

/* 套餐网格 */
.plans-grid {
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 20px 60px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

.plan-card {
  position: relative;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 16px;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  transition: all 0.3s;
}

.plan-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.25);
}

.plan-card.recommended {
  border: 2px solid #9b59ff;
  box-shadow: 0 0 20px rgba(155, 89, 255, 0.3);
}

.recommend-badge {
  position: absolute;
  top: -12px;
  left: 50%;
  transform: translateX(-50%);
  background: linear-gradient(135deg, #9b59ff 0%, #7e3ff2 100%);
  color: #fff;
  padding: 4px 16px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.plan-name {
  color: #fff;
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 8px;
}

.plan-desc {
  color: rgba(255, 255, 255, 0.75);
  font-size: 13px;
  margin-bottom: 16px;
  min-height: 38px;
}

.plan-price {
  display: flex;
  align-items: baseline;
  gap: 2px;
  color: #ffd700;
  margin-bottom: 20px;
}

.price-symbol {
  font-size: 18px;
}

.price-num {
  font-size: 36px;
  font-weight: 700;
}

.plan-features {
  list-style: none;
  margin-bottom: 22px;
  flex: 1;
}

.plan-features li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  color: rgba(255, 255, 255, 0.9);
  font-size: 13px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.feat-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.purchase-btn {
  background: linear-gradient(135deg, #2b5ca8 0%, #1a3a6b 100%);
}

.recommended .purchase-btn {
  background: linear-gradient(135deg, #9b59ff 0%, #7e3ff2 100%);
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: rgba(255, 255, 255, 0.85);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-state p {
  margin-bottom: 20px;
  font-size: 15px;
}

/* 模态框 */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}

.modal-dialog {
  background: #fff;
  border-radius: 16px;
  width: 100%;
  max-width: 460px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid #ebeef5;
}

.modal-header h3 {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.modal-close {
  background: transparent;
  border: none;
  font-size: 26px;
  color: var(--color-text-secondary);
  cursor: pointer;
  line-height: 1;
}

.modal-close:hover {
  color: var(--color-text-primary);
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
}

/* 选中套餐信息 */
.selected-plan {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  background: #f9fafc;
  border-radius: 8px;
  margin-bottom: 16px;
}

.sp-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.sp-price {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-primary);
}

/* 微信支付提示区 */
.wechat-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  background: #e8f8ef;
  border-radius: 8px;
  margin-bottom: 18px;
  color: #07c160;
  font-size: 14px;
  font-weight: 500;
}

.wechat-icon {
  font-size: 18px;
}

.wechat-hint {
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 400;
}

/* 未登录提示 */
.login-tip {
  text-align: center;
  padding: 24px 16px;
}

.login-tip p {
  color: var(--color-warning);
  font-size: 15px;
  margin-bottom: 14px;
}

/* 激活表单 */
.activate-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-row {
  display: flex;
  flex-direction: column;
}

/* 模态框底部 */
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px;
  border-top: 1px solid #ebeef5;
}

/* 激活成功界面 */
.success-view {
  padding: 40px 28px;
  text-align: center;
}

.success-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: linear-gradient(135deg, #07c160 0%, #06a552 100%);
  color: #fff;
  font-size: 36px;
  font-weight: 700;
  margin-bottom: 20px;
  animation: success-pop 0.4s ease;
}

@keyframes success-pop {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  60% {
    transform: scale(1.15);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.success-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 12px;
}

.success-msg {
  color: var(--color-text-regular);
  font-size: 14px;
  margin-bottom: 10px;
}

.success-expire {
  color: var(--color-text-secondary);
  font-size: 13px;
  margin-bottom: 24px;
}

/* 响应式 */
@media (max-width: 900px) {
  .plans-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .plans-grid {
    grid-template-columns: 1fr;
  }
  .page-title {
    font-size: 24px;
  }
  .back-btn {
    position: static;
    margin-bottom: 16px;
  }
  .header-inner {
    text-align: center;
  }
}
</style>
