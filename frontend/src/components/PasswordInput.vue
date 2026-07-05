<script setup>
// 密码输入组件：含小眼睛切换显隐
import { ref } from 'vue'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  placeholder: {
    type: String,
    default: '请输入密码'
  },
  id: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue'])

// 是否明文显示
const visible = ref(false)

function toggle() {
  visible.value = !visible.value
}

function onInput(e) {
  emit('update:modelValue', e.target.value)
}
</script>

<template>
  <div class="password-input">
    <input
      :id="id"
      :type="visible ? 'text' : 'password'"
      :value="modelValue"
      :placeholder="placeholder"
      class="password-field"
      autocomplete="off"
      @input="onInput"
    />
    <button type="button" class="toggle-btn" @click="toggle" :title="visible ? '隐藏密码' : '显示密码'">
      <svg v-if="!visible" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
      <svg v-else viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
        <line x1="1" y1="1" x2="23" y2="23" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.password-input {
  position: relative;
  width: 100%;
}

.password-field {
  width: 100%;
  padding: 12px 44px 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 8px;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  outline: none;
  transition: all 0.2s;
  box-sizing: border-box;
}

.password-field::placeholder {
  color: rgba(255, 255, 255, 0.6);
}

.password-field:focus {
  border-color: rgba(255, 255, 255, 0.7);
  background: rgba(255, 255, 255, 0.18);
}

/* 浅色主题下（管理端） */
:global(.light-theme) .password-field {
  border-color: #dcdfe6;
  background: #fff;
  color: #303133;
}

:global(.light-theme) .password-field::placeholder {
  color: #a8abb2;
}

.toggle-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.8);
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
}

.toggle-btn:hover {
  color: #fff;
}

:global(.light-theme) .toggle-btn {
  color: #909399;
}

:global(.light-theme) .toggle-btn:hover {
  color: #303133;
}
</style>
