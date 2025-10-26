<template>
  <div>
    <!-- Info & Header Section -->
    <div class="p-3 mb-4 rounded" style="background-color: #e9ecef;">
        <p class="mb-1"><strong>💡 提示：</strong></p>
        <ul class="mb-1 ps-4" style="font-size: 0.9rem;">
            <li>用戶加好友或發訊息時會自動加入清單。</li>
            <li>點擊用戶姓名或電話號碼可以手動修改。✏️</li>
        </ul>
    </div>

    <div class="d-flex justify-content-between align-items-center mb-3">
        <h2 class="mb-0 text-primary fw-bold">📋 用戶清單 ({{ filteredUsers.length }})</h2>
        <div class="d-flex gap-2 align-items-center">
            <input 
              type="text" 
              class="form-control"
              placeholder="依姓名或注音搜尋..." 
              :value="searchTerm" @input="searchTerm = $event.target.value" style="width: 250px;">
            <button class="btn btn-primary" @click="addManualUser">＋ 新增臨時用戶</button>
        </div>
    </div>

    <!-- Main Content -->
    <div v-if="loading" class="d-flex justify-content-center align-items-center" style="min-height: 300px;">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">載入中...</span>
      </div>
    </div>
    <div v-else-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-else class="table-responsive shadow-sm rounded border">
        <table class="table table-hover table-striped mb-0 align-middle">
          <thead class="table-light">
            <tr>
              <th scope="col" style="width: 60px;" class="text-center">頭像</th>
              <th scope="col">姓名</th>
              <th scope="col">注音</th>
              <th scope="col">LINE User ID</th>
              <th scope="col">電話 (市)</th>
              <th scope="col">電話 (手)</th>
              <th scope="col" class="text-center">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in filteredUsers" :key="user.id">
              <td class="text-center">
                <img :src="`/user_avatar/${user.id}`" alt="avatar" class="rounded-circle" style="width: 40px; height: 40px; object-fit: cover;">
              </td>
              <td>
                <span @click="editField(user, 'name')" class="editable-field">
                  {{ user.name }} <i class="bi bi-pencil-fill text-primary ms-1"></i>
                </span>
              </td>
              <td>{{ user.zhuyin }}</td>
              <td class="text-muted" style="font-size: 0.8rem; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="user.line_user_id">{{ user.line_user_id }}</td>
              <td>
                <span @click="editField(user, 'phone')" class="editable-field">{{ user.phone || '[點擊新增]' }} <i class="bi bi-pencil-fill text-primary ms-1"></i></span>
              </td>
              <td>
                <span @click="editField(user, 'phone2')" class="editable-field">{{ user.phone2 || '[點擊新增]' }} <i class="bi bi-pencil-fill text-primary ms-1"></i></span>
              </td>
              <td class="text-center d-flex gap-1 justify-content-center">
                 <button v-if="user.line_user_id && user.line_user_id.startsWith('U')" @click="refreshUserProfile(user.id)" class="btn btn-sm btn-outline-info py-0 px-1" title="從LINE更新資料">
                      <i class="bi bi-arrow-repeat" style="font-size: 1.1rem;"></i>
                 </button>
                  <button v-if="user.id.startsWith('manual_')" @click="openMergeModal(user)" class="btn btn-sm btn-outline-success py-0 px-1" title="合併用戶">
                      <i class="bi bi-person-plus-fill" style="font-size: 1.1rem;"></i>
                  </button>
                  <button @click="deleteUser(user.id)" class="btn btn-sm btn-outline-danger py-0 px-1" title="刪除用戶">
                      <i class="bi bi-trash-fill" style="font-size: 1.1rem;"></i>
                  </button>
              </td>
            </tr>
          </tbody>
        </table>
    </div>

    <!-- Status Message -->
    <div v-if="status.show" class="position-fixed top-0 end-0 p-3" style="z-index: 1100">
        <div :class="`toast show align-items-center text-white border-0 ${status.type === 'success' ? 'bg-success' : 'bg-danger'}`" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    {{ status.message }}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" @click="status.show = false" aria-label="Close"></button>
            </div>
        </div>
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue';
import { getUsers, updateUser, addManual, mergeUsers, deleteUserApi, refreshProfile } from './api';

const users = ref([]);
const loading = ref(true);
const error = ref(null);
const searchTerm = ref('');

const sourceUser = ref(null);
const targetUserId = ref(null);
const mergeModalRef = ref(null);
let mergeModalInstance = null;

const status = ref({ show: false, message: '', type: 'info' });

const filteredUsers = computed(() => {
  if (!searchTerm.value) {
    return users.value;
  }
  const term = searchTerm.value.toLowerCase();
  return users.value.filter(user => 
    user.name.toLowerCase().includes(term) || 
    (user.zhuyin && user.zhuyin.toLowerCase().includes(term))
  );
});

const realUsers = computed(() => users.value.filter(u => u.id && !u.id.startsWith('manual_')));

function showStatus(message, type = 'success', duration = 3000) {
  status.value = { show: true, message, type };
  setTimeout(() => {
    status.value.show = false;
  }, duration);
}

const loadUsers = async () => {
  loading.value = true;
  error.value = null;
  try {
    const data = await getUsers();
    users.value = data.users;
  } catch (err) {
    error.value = '無法載入用戶資料，請稍後再試。';
    console.error(err);
  } finally {
    loading.value = false;
  }
};

const getFieldName = (field) => {
  const names = { name: '姓名', phone: '電話(市)', phone2: '電話(手)' };
  return names[field] || '欄位';
};

const editField = async (user, field) => {
  const originalValue = user[field] || '';
  const newValue = prompt(`請輸入 ${user.name} 的新${getFieldName(field)}：`, originalValue);

  if (newValue !== null && newValue.trim() !== originalValue) {
    const valueToSave = newValue.trim();
    try {
      await updateUser(user.id, field, valueToSave);
      showStatus('✅ 更新成功', 'success');
      await loadUsers(); // Reload to reflect changes
    } catch (err) {
      showStatus('❌ 更新失敗', 'error');
    }
  }
};

onMounted(() => {
  loadUsers();
  if (mergeModalRef.value) {
    mergeModalInstance = new window.bootstrap.Modal(mergeModalRef.value);
  }
});

const refreshUserProfile = async (userId) => {
  showStatus('正在從LINE更新資料...', 'info');
  try {
    await refreshProfile(userId);
    showStatus('✅ 用戶資料已更新，將重新載入列表。', 'success');
    await loadUsers();
  } catch (error) {
    showStatus(`❌ 更新失敗: ${error.message || '未知錯誤'}`, 'error');
  }
};

const addManualUser = async () => {
  const name = prompt("請輸入臨時用戶的姓名：\n（建議格式：陳先生-手機末四碼）");
  if (name && name.trim()) {
    showStatus('正在新增臨時用戶...', 'info');
    try {
      const newUser = await addManual(name.trim());
      users.value.unshift(newUser.user); // Add to the top of the list
      showStatus('✅ 臨時用戶已新增', 'success');
    } catch (error) {
      showStatus(`❌ 新增失敗: ${error.message || '未知錯誤'}`, 'error');
    }
  }
};

const openMergeModal = (user) => {
  sourceUser.value = user;
  targetUserId.value = '';
  if (mergeModalInstance) {
    mergeModalInstance.show();
  }
};

const confirmMerge = async () => {
  if (!sourceUser.value || !targetUserId.value) {
    showStatus('❌ 請選擇目標用戶', 'error');
    return;
  }
  if (!confirm(`確定要將 ${sourceUser.value.name} 的所有資料合併到目標用戶嗎？此操作無法復原。`)) {
    return;
  }
  try {
    await mergeUsers(sourceUser.value.id, targetUserId.value);
    showStatus('✅ 合併成功', 'success');
    if (mergeModalInstance) mergeModalInstance.hide();
    await loadUsers();
  } catch (error) {
    showStatus(`❌ 合併失敗: ${error.message || '未知錯誤'}`, 'error');
  }
};

const deleteUser = async (userId) => {
    if (!confirm('確定要刪除此用戶嗎？所有相關的預約紀錄也將被刪除，此操作無法復原。')) return;
    try {
        await deleteUserApi(userId);
        showStatus('✅ 用戶已刪除', 'success');
        await loadUsers();
    } catch (error) {
        showStatus(`❌ 刪除失敗: ${error.message || '未知錯誤'}`, 'error');
    }
};

</script>

<style>
.table-hover tbody tr:hover {
  background-color: rgba(0, 123, 255, 0.05);
}
.form-check-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.editable-field {
    cursor: pointer;
    display: inline-block;
    padding: 4px 8px;
    border-radius: 4px;
}
.editable-field:hover {
    background-color: #e9ecef;
}
.editable-field .bi-pencil-fill {
    opacity: 0;
    transition: opacity 0.2s;
}
.editable-field:hover .bi-pencil-fill {
    opacity: 0.6;
}
</style>