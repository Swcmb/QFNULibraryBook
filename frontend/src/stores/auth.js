// 简单的 reactive store（不使用 Pinia）
// 提供用户端与管理端的登录态管理
import { reactive } from 'vue'
import * as api from '../api/client'

export const authStore = reactive({
  // 用户端
  loggedIn: false,
  username: '',

  // 管理端
  adminAuthed: false,

  // 订阅端登录态
  plansLoggedIn: false,
  plansUsername: ''
})

// 检查用户端登录态
export async function checkStatus() {
  const res = await api.getStatus()
  if (res.ok && res.logged_in) {
    authStore.loggedIn = true
    authStore.username = res.username || ''
  } else {
    authStore.loggedIn = false
    authStore.username = ''
  }
  return authStore.loggedIn
}

// 用户登录
export async function userLogin(username, password) {
  const res = await api.login(username, password)
  if (res.ok && res.success) {
    authStore.loggedIn = true
    authStore.username = res.name || username
  }
  return res
}

// 用户退出
export async function userLogout() {
  const res = await api.logout()
  authStore.loggedIn = false
  authStore.username = ''
  return res
}

// 管理员登录
export async function adminLogin(password) {
  const res = await api.adminAuth(password)
  if (res.ok && res.success) {
    authStore.adminAuthed = true
  }
  return res
}

// 管理员退出
export async function adminLogout() {
  const res = await api.adminLogout()
  authStore.adminAuthed = false
  return res
}

// 同步订阅端登录态（复用用户登录态）
export async function syncPlansStatus() {
  const res = await api.getPlanStatus()
  if (res.ok && res.success) {
    authStore.plansLoggedIn = !!res.subscription
    authStore.plansUsername = res.subscription?.username || authStore.username
  }
  return res
}

export default {
  authStore,
  checkStatus,
  userLogin,
  userLogout,
  adminLogin,
  adminLogout,
  syncPlansStatus
}
