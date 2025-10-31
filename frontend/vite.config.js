import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'), // 預約簿
        users: resolve(__dirname, 'users.html'), // 用戶管理
        merge_users: resolve(__dirname, 'merge_users.html'), // 新增合併用戶頁面的進入點
      },
    },
    manifest: true,       // 生成 manifest.json
    outDir: '../static',  // 將打包結果直接輸出到 Flask 的 static 資料夾
    assetsDir: 'assets',
    emptyOutDir: true,
  },
  server: {
    // 設定代理，將 /api 的請求轉發到後端 Flask 伺服器
    proxy: {
      '/api': {
        target: 'http://localhost:5000', // 您的 Flask 後端地址
        changeOrigin: true,
      },
      // 如果您還有其他需要代理的路徑，也可以一併加入
      // 例如，頭像路徑

      '/admin': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
      },
      '/user_avatar': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      }
    }
  }
})
