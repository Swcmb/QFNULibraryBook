import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import AdminView from '../views/AdminView.vue'
import PlansView from '../views/PlansView.vue'

// 路由表：用户端 / 管理端 / 订阅计划端
const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView
  },
  {
    path: '/admin',
    name: 'admin',
    component: AdminView
  },
  {
    path: '/plans',
    name: 'plans',
    component: PlansView
  }
]

// 使用 history 模式，base 用相对路径
const router = createRouter({
  history: createWebHistory('./'),
  routes
})

export default router
