import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    // 設定代理，將 /api 的請求轉發到後端 Flask 伺服器
    proxy: {
      '/api': {
        target: 'http://localhost:5000', // 您的 Flask 後端地址
        changeOrigin: true,
      },
      // 如果您還有其他需要代理的路徑，也可以一併加入
      // 例如，頭像路徑
      '/user_avatar': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      }
    }
  }
})
