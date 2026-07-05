import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite 配置：使用绝对路径 base，确保子路由刷新时资源路径正确
export default defineConfig({
  plugins: [vue()],
  base: '/',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/admin/api': 'http://127.0.0.1:8000',
      '/plans/api': 'http://127.0.0.1:8000'
    }
  }
})
