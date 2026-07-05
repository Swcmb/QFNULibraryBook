<script setup>
// 根组件：承载全局 Toast 与路由出口
import Toast from './components/Toast.vue'
</script>

<template>
  <div class="app-root">
    <router-view />
    <!-- 全局 Toast 提示 -->
    <Toast />
  </div>
</template>

<style scoped>
.app-root {
  min-height: 100vh;
}
</style>
