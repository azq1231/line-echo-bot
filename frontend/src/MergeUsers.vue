<template>
  <div class="container mt-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
      <h1>
        <i class="bi bi-person-plus-fill me-2"></i>用戶合併建議
      </h1>
      <div>
        <a :href="usersPageUrl" class="btn btn-outline-secondary me-2">
          <i class="bi bi-arrow-left"></i> 返回用戶列表
        </a>
        <button class="btn btn-primary" @click="fetchSuggestions" :disabled="isLoading">
          <i class="bi bi-arrow-clockwise me-1"></i>
          {{ isLoading ? '載入中...' : '重新整理' }}
        </button>
      </div>
    </div>

    <div v-if="status.message" class="alert" :class="status.type === 'success' ? 'alert-success' : 'alert-danger'" role="alert">
      {{ status.message }}
    </div>

    <div v-if="isLoading" class="text-center py-5">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">Loading...</span>
      </div>
      <p class="mt-2">正在分析用戶資料...</p>
    </div>

    <div v-else-if="suggestions.length === 0" class="text-center py-5 bg-light rounded">
      <i class="bi bi-check-circle-fill fs-1 text-success"></i>
      <h4 class="mt-3">太棒了！</h4>
      <p class="text-muted">目前沒有找到可合併的用戶建議。</p>
    </div>

    <div v-else class="row row-cols-1 row-cols-lg-2 g-4">
      <div v-for="(suggestion, index) in suggestions" :key="suggestion.source.user_id" class="col">
        <div class="card h-100 shadow-sm">
          <div class="card-header bg-light fw-bold">
            建議 {{ index + 1 }} - <span class="text-primary">{{ suggestion.reason }}</span>
          </div>
          <div class="card-body">
            <div class="row g-3 align-items-center">
              <!-- Source User (Manual) -->
              <div class="col-md-5">
                <div class="border p-3 rounded bg-light h-100 d-flex flex-column">
                  <h6 class="card-subtitle mb-2 text-muted">
                    <i class="bi bi-person-fill-gear me-1"></i>臨時用戶 (來源)
                  </h6>
                  <p class="card-text fw-bold fs-5">{{ suggestion.source.name }}</p>
                  <p class="card-text small text-muted mt-auto">ID: {{ suggestion.source.user_id.substring(0, 12) }}...</p>
                </div>
              </div>

              <!-- Merge Arrow -->
              <div class="col-md-2 text-center">
                <i class="bi bi-arrow-right-circle-fill fs-2 text-success"></i>
              </div>

              <!-- Target User (LINE) -->
              <div class="col-md-5">
                <div class="border p-3 rounded h-100 d-flex flex-column">
                  <h6 class="card-subtitle mb-2 text-muted">
                    <i class="bi bi-person-check-fill me-1"></i>LINE 用戶 (目標)
                  </h6>
                  <p class="card-text fw-bold fs-5">{{ suggestion.target.name }}</p>
                  <p class="card-text small text-muted mt-auto">ID: {{ suggestion.target.user_id.substring(0, 12) }}...</p>
                </div>
              </div>
            </div>
          </div>
          <div class="card-footer text-end">
            <button class="btn btn-success" @click="executeMerge(suggestion.source.user_id, suggestion.target.user_id, index)" :disabled="isMerging[index]">
              <span v-if="isMerging[index]" class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
              <i v-else class="bi bi-person-plus-fill me-1"></i>
              合併
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import axios from 'axios';

const suggestions = ref([]);
const isLoading = ref(true);
const isMerging = ref({});
const status = ref({ message: '', type: 'info' });
const usersPageUrl = ref('#'); // 返回按鈕的 URL

const showStatus = (message, type = 'success', duration = 4000) => {
  status.value = { message, type };
  setTimeout(() => {
    status.value = { message: '', type: 'info' };
  }, duration);
};

const fetchSuggestions = async () => {
  isLoading.value = true;
  try {
    const response = await axios.get('/api/admin/users/merge_suggestions');
    if (response.data.status === 'success') {
      suggestions.value = response.data.suggestions;
    } else {
      throw new Error(response.data.message || '載入建議失敗');
    }
  } catch (error) {
    showStatus(`❌ 載入合併建議時發生錯誤: ${error.message}`, 'danger');
  } finally {
    isLoading.value = false;
  }
};

const executeMerge = async (sourceId, targetId, index) => {
  if (!confirm(`確定要將臨時用戶的資料合併到 LINE 用戶嗎？\n\n來源 (將被刪除): ${suggestions.value[index].source.name}\n目標 (將被保留): ${suggestions.value[index].target.name}\n\n此操作無法復原。`)) {
    return;
  }

  isMerging.value[index] = true;
  try {
    const response = await axios.post('/api/admin/users/merge', {
      source_user_id: sourceId,
      target_user_id: targetId,
    });

    if (response.data.status === 'success') {
      showStatus('✅ 用戶已成功合併！', 'success');
      // 從列表中移除已合併的建議
      suggestions.value.splice(index, 1);
    } else {
      throw new Error(response.data.message || '合併失敗');
    }
  } catch (error) {
    showStatus(`❌ 合併失敗: ${error.message}`, 'danger');
  } finally {
    isMerging.value[index] = false;
  }
};

onMounted(() => {
  // 從全域變數讀取後端傳來的 URL
  if (window.appConfig && window.appConfig.usersPageUrl) {
    usersPageUrl.value = window.appConfig.usersPageUrl;
  }
  fetchSuggestions();
});
</script>

<style scoped>
.card-subtitle i {
  vertical-align: -0.125em;
}
</style>