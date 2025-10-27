// 只在開發模式下導入 Bootstrap，生產環境由 Flask 模板提供
if (import.meta.env.DEV) {
  await import('bootstrap/dist/css/bootstrap.min.css');
  await import('bootstrap/dist/js/bootstrap.bundle.min.js');
}

import { createApp } from 'vue'
import UserManagement from './UserManagement.vue'

createApp(UserManagement).mount('#app')