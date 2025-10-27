import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './assets/global.css'; // 導入全域樣式
import { createApp } from 'vue'
import UserManagement from './UserManagement.vue'

// 只在開發模式下導入 Bootstrap JS，生產環境由 Flask 模板提供
// CSS 可以在頂層導入，但 JS 最好在 DOM 準備好後再處理
if (import.meta.env.DEV) {
  import('bootstrap/dist/js/bootstrap.bundle.min.js');
}

createApp(UserManagement).mount('#app')