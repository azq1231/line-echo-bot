import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './assets/global.css';
import { createApp } from 'vue';
import MergeUsers from './MergeUsers.vue';

async function initializeApp() {
  if (import.meta.env.DEV) {
    const bootstrap = await import('bootstrap/dist/js/bootstrap.bundle.min.js');
    window.bootstrap = bootstrap;
  }
  
  createApp(MergeUsers).mount('#app');
}

initializeApp();