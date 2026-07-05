<script setup>
// 全局 Toast 提示组件
// 通过事件总线调用：toast.show('消息', 'success' | 'error' | 'warning' | 'info')
import { reactive, onMounted, onUnmounted } from 'vue'

// toast 列表
const toasts = reactive([])

let idSeed = 0

// 显示 toast
function show(message, type = 'info', duration = 3000) {
  const id = ++idSeed
  toasts.push({ id, message, type })
  setTimeout(() => {
    remove(id)
  }, duration)
}

// 移除 toast
function remove(id) {
  const idx = toasts.findIndex((t) => t.id === id)
  if (idx > -1) toasts.splice(idx, 1)
}

// 简单事件总线：挂到 window 上，全局可调用
const bus = {
  show,
  success: (msg, d) => show(msg, 'success', d),
  error: (msg, d) => show(msg, 'error', d),
  warning: (msg, d) => show(msg, 'warning', d),
  info: (msg, d) => show(msg, 'info', d)
}

onMounted(() => {
  window.$toast = bus
})

onUnmounted(() => {
  delete window.$toast
})
</script>

<template>
  <div class="toast-container">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="toast-item"
      :class="`toast-${t.type}`"
      @click="remove(t.id)"
    >
      <span class="toast-icon">
        <template v-if="t.type === 'success'">✓</template>
        <template v-else-if="t.type === 'error'">✕</template>
        <template v-else-if="t.type === 'warning'">!</template>
        <template v-else>i</template>
      </span>
      <span class="toast-msg">{{ t.message }}</span>
    </div>
  </div>
</template>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 10px;
  pointer-events: none;
}

.toast-item {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 240px;
  max-width: 360px;
  padding: 12px 16px;
  border-radius: 8px;
  color: #fff;
  font-size: 14px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
  cursor: pointer;
  animation: toast-in 0.25s ease;
}

@keyframes toast-in {
  from {
    opacity: 0;
    transform: translateX(40px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.toast-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.25);
  font-weight: bold;
  font-size: 13px;
  flex-shrink: 0;
}

.toast-success {
  background: #07c160;
}

.toast-error {
  background: #e94d4d;
}

.toast-warning {
  background: #f0a020;
}

.toast-info {
  background: #2b5ca8;
}

.toast-msg {
  flex: 1;
  word-break: break-all;
}
</style>
