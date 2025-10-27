import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './assets/global.css'; // 導入全域樣式
import { createApp } from 'vue'
import UserManagement from './UserManagement.vue'

// 只在開發模式下導入 Bootstrap JS，生產環境由 Flask 模板提供
async function initializeApp() {
  if (import.meta.env.DEV) {
    // 使用 await 確保 Bootstrap 的 JS 在 Vue 應用啟動前已載入
    const bootstrap = await import('bootstrap/dist/js/bootstrap.bundle.min.js');
    // 手動將導入的模組附加到 window 物件，以供全域使用
    window.bootstrap = bootstrap;
  }
  
  // 此時所有依賴都已載入，可以直接啟動 Vue 應用
  createApp(UserManagement).mount('#app');
}

initializeApp();