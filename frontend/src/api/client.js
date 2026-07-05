// 通用请求客户端封装
// - 自动添加 X-Requested-With: XMLHttpRequest 头
// - 自动 JSON 序列化 body
// - 20 秒超时（AbortController）
// - 返回 {ok, status, ...json}
// - 错误处理：超时返回 TIMEOUT 错误码，网络错误返回 NETWORK_ERROR

const DEFAULT_TIMEOUT = 20000

/**
 * 发起请求
 * @param {string} url 请求地址
 * @param {object} options fetch 配置
 * @returns {Promise<object>} 合并了 ok/status 与响应 json 的对象
 */
export async function request(url, options = {}) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), options.timeout || DEFAULT_TIMEOUT)

  // 构造请求头
  const headers = {
    'X-Requested-With': 'XMLHttpRequest',
    ...(options.headers || {})
  }

  // 处理 body：对象自动 JSON 序列化
  let body = options.body
  if (body && typeof body === 'object' && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(body)
  }

  try {
    const res = await fetch(url, {
      ...options,
      headers,
      body,
      signal: controller.signal
    })

    // 尝试解析 JSON，失败则返回文本
    let data = {}
    const text = await res.text()
    if (text) {
      try {
        data = JSON.parse(text)
      } catch {
        data = { message: text }
      }
    }

    return {
      ok: res.ok,
      status: res.status,
      ...data
    }
  } catch (err) {
    // 超时与网络错误统一处理
    if (err.name === 'AbortError') {
      return {
        ok: false,
        status: 0,
        code: 'TIMEOUT',
        message: '请求超时，请稍后重试'
      }
    }
    return {
      ok: false,
      status: 0,
      code: 'NETWORK_ERROR',
      message: '网络错误，请检查连接'
    }
  } finally {
    clearTimeout(timeoutId)
  }
}

// ============== 用户端 API ==============

// 检查登录状态
export const getStatus = () => request('/api/status')

// 用户登录
export const login = (username, password) =>
  request('/api/login', {
    method: 'POST',
    body: { username, password }
  })

// 签到
export const checkin = () => request('/api/checkin', { method: 'POST' })

// 签退
export const signout = () => request('/api/signout', { method: 'POST' })

// 退出登录
export const logout = () => request('/api/logout', { method: 'POST' })

// ============== 管理端 API ==============

// 管理员鉴权
export const adminAuth = (password) =>
  request('/admin/api/auth', { method: 'POST', body: { password } })

// 管理员退出
export const adminLogout = () => request('/admin/api/logout', { method: 'POST' })

// 获取账号列表
export const getAdminUsers = () => request('/admin/api/users')

// 新增账号
export const createAdminUser = (data) =>
  request('/admin/api/users', { method: 'POST', body: data })

// 更新账号
export const updateAdminUser = (username, data) =>
  request(`/admin/api/users/${encodeURIComponent(username)}`, { method: 'PUT', body: data })

// 删除账号
export const deleteAdminUser = (username) =>
  request(`/admin/api/users/${encodeURIComponent(username)}`, { method: 'DELETE' })

// 保存抢座顺序
export const updateGrabOrder = (grab_order) =>
  request('/admin/api/users/order', { method: 'PUT', body: { grab_order } })

// 立即抢座
export const triggerGrab = () => request('/admin/api/grab', { method: 'POST' })

// 抢座状态
export const getGrabStatus = () => request('/admin/api/grab/status')

// 获取日志
export const getAdminLogs = (lines = 100) =>
  request(`/admin/api/logs?lines=${lines}`)

// ============== 订阅码 API ==============

// 生成订阅码
export const generateCodes = (data) =>
  request('/admin/api/subscriptions/codes', { method: 'POST', body: data })

// 查询订阅码列表
export const listCodes = (params = {}) => {
  const query = new URLSearchParams(params).toString()
  return request(`/admin/api/subscriptions/codes?${query}`)
}

// 撤销订阅码
export const revokeCode = (code) =>
  request(`/admin/api/subscriptions/codes/${encodeURIComponent(code)}/revoke`, { method: 'POST' })

// 获取订阅用户列表
export const getSubscriptionUsers = () => request('/admin/api/subscriptions/users')

// 获取订阅统计
export const getSubscriptionStats = () => request('/admin/api/subscriptions/stats')

// 获取套餐列表（管理端）
export const getAdminPlans = () => request('/admin/api/subscriptions/plans')

// ============== 计划端 API ==============

// 获取套餐列表
export const getPlans = () => request('/plans/api/plans')

// 激活订阅
export const activatePlan = (activation_code, plan_id) =>
  request('/plans/api/activate', { method: 'POST', body: { activation_code, plan_id } })

// 订阅状态
export const getPlanStatus = () => request('/plans/api/status')

export default {
  request,
  getStatus,
  login,
  checkin,
  signout,
  logout,
  adminAuth,
  adminLogout,
  getAdminUsers,
  createAdminUser,
  updateAdminUser,
  deleteAdminUser,
  updateGrabOrder,
  triggerGrab,
  getGrabStatus,
  getAdminLogs,
  generateCodes,
  listCodes,
  revokeCode,
  getSubscriptionUsers,
  getSubscriptionStats,
  getAdminPlans,
  getPlans,
  activatePlan,
  getPlanStatus
}
