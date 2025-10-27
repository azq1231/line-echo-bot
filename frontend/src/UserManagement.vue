<template>
  <div class="user-management-page container py-3">
    <!-- Info & Header Section -->
    <div class="p-3 mb-4 rounded" style="background-color: #e9ecef;">
        <p class="mb-1"><strong>💡 提示：</strong></p>
        <ul class="mb-1 ps-4" style="font-size: 0.9rem;">
            <li>用戶加好友或發訊息時會自動加入清單。</li>
            <li>點擊用戶姓名或電話號碼可以手動修改。✏️</li>
        </ul>
    </div>

    <div class="d-flex justify-content-end align-items-center mb-3">
        <div class="d-flex gap-2 align-items-center">
            <input 
              type="text" 
              class="form-control"
              placeholder="依姓名或注音搜尋..." 
              :value="searchTerm" @input="searchTerm = $event.target.value" style="width: 200px;">
            <button class="btn btn-primary" @click="openAddManualUserModal">新增臨時用戶</button>
        </div>
    </div>
    <h2 class="mb-3 text-primary fw-bold">📋 用戶清單 ({{ filteredUsers.length }})</h2>

    <!-- Main Content -->
    <div v-if="loading" class="d-flex justify-content-center align-items-center" style="min-height: 300px;">
      <div class="spinner-border text-primary" role="status">
        <span class="visually-hidden">載入中...</span>
      </div>
    </div>
    <div v-else-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-else class="table-responsive">
        <table class="table table-striped table-bordered mb-0 align-middle">
          <thead class="table-light">
            <tr>
              <th scope="col" style="width: 40px;" class="text-center">頭像</th>
              <th scope="col">用戶資訊</th>
              <th scope="col" class="text-center" style="width: 50px;">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in filteredUsers" :key="user.id">
              <td class="text-center">
                <img :src="`/user_avatar/${user.id}`" alt="avatar" class="rounded-circle" style="width: 40px; height: 40px; object-fit: cover;" @error="onAvatarError">
              </td>
              <td class="user-details">
                <div class="d-flex align-items-center">
                  <span @click="editField(user, 'name')" class="editable-field fw-bold fs-6">
                    {{ user.name }} <i class="bi bi-pencil-fill text-primary ms-1"></i>
                  </span>
                  <button @click="toggleZhuyin(user.id)" class="btn btn-sm btn-link py-0 px-1 text-secondary" title="顯示/隱藏注音">[注]</button>
                </div>
                <div v-if="visibleZhuyin.has(user.id)" class="mt-1">
                  <span @click="editField(user, 'zhuyin')" class="editable-field text-secondary" style="font-size: 0.8rem;">{{ user.zhuyin || '[點擊新增]' }}</span>
                </div>
                <div class="d-flex gap-2 align-items-center mt-2">
                  <span @click="editField(user, 'phone')" class="editable-field text-muted small flex-shrink-0">
                    <i class="bi bi-telephone-fill me-1"></i>{{ user.phone || '市話' }}
                  </span>
                  <span @click="editField(user, 'phone2')" class="editable-field text-muted small flex-shrink-0">
                    <i class="bi bi-phone-fill me-1"></i>{{ user.phone2 || '手機' }}
                  </span>
                </div>
              </td>
              <td class="text-center">
                <div class="d-flex flex-column gap-1">
                    <button v-if="user.id.startsWith('manual_')" @click="openMergeModal(user)" class="btn btn-sm btn-outline-success px-2 icon-btn" title="合併用戶">
                        <i class="bi bi-person-plus-fill" style="font-size: 1.1rem;"></i>
                    </button>
                    <button @click="deleteUser(user.id)" class="btn btn-sm btn-outline-danger px-2 icon-btn" title="刪除用戶">
                        <i class="bi bi-trash-fill" style="font-size: 1.1rem;"></i>
                    </button>
                </div>
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

    <!-- Add Manual User Modal -->
    <div class="modal fade" id="addManualUserModal" tabindex="-1" aria-labelledby="addManualUserModalLabel" aria-hidden="true" ref="addManualModalRef">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="addManualUserModalLabel">新增臨時用戶</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <label for="manualUserName" class="form-label">用戶姓名</label>
            <input type="text" class="form-control" id="manualUserName" v-model="newUserName" placeholder="例如：陳先生-手機末四碼" @keyup.enter="confirmAddManualUser">
            <div class="form-text">為無法使用 LINE 登入的用戶（如電話預約客）建立一個臨時帳號。</div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
            <button type="button" class="btn btn-primary" @click="confirmAddManualUser">儲存</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Merge Modal -->
    <div class="modal fade" id="mergeUserModal" tabindex="-1" aria-labelledby="mergeUserModalLabel" aria-hidden="true" ref="mergeModalRef">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="mergeUserModalLabel">合併用戶</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <p>將臨時用戶 <strong>{{ sourceUser?.name }}</strong> 的所有預約紀錄合併至以下真實用戶：</p>
            <select class="form-select" v-model="targetUserId">
              <option disabled value="">請選擇一個目標用戶...</option>
              <option v-for="u in realUsers" :key="u.id" :value="u.id">{{ u.name }} ({{ u.id }})</option>
            </select>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
            <button type="button" class="btn btn-danger" @click="confirmMerge" :disabled="!targetUserId">確認合併</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue';
import { getUsers, updateUser, addManual, mergeUsers, deleteUserApi } from './api';

const users = ref([]);
const loading = ref(true);
const error = ref(null);
const searchTerm = ref('');
const visibleZhuyin = ref(new Set());

const sourceUser = ref(null);
const targetUserId = ref(null);
const mergeModalRef = ref(null);
let mergeModalInstance = null;

const newUserName = ref('');
const addManualModalRef = ref(null);
let addManualModalInstance = null;
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

const onAvatarError = (e) => {
  // This prevents an infinite loop if the default image also fails to load.
  e.target.src = '/static/nohead.png';
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

const toggleZhuyin = (userId) => {
  if (visibleZhuyin.value.has(userId)) {
    visibleZhuyin.value.delete(userId);
  } else {
    visibleZhuyin.value.add(userId);
  }
};

const getFieldName = (field) => {
  const names = { name: '姓名', zhuyin: '注音', phone: '電話(市)', phone2: '電話(手)' };
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

onMounted(async () => {
  await nextTick();
  await loadUsers();

  // 等待 Bootstrap 載入並初始化 Modal
  const initModal = () => {
    if (window.bootstrap) {
      if (mergeModalRef.value) {
        mergeModalInstance = new window.bootstrap.Modal(mergeModalRef.value);
        console.log('✅ Merge Modal 初始化成功');
      }
      if (addManualModalRef.value) {
        addManualModalInstance = new window.bootstrap.Modal(addManualModalRef.value);
        console.log('✅ Add Manual Modal 初始化成功');
      }
    } else {
      console.warn('⏳ 等待 Bootstrap 載入中...');
      setTimeout(initModal, 200);
    }
  };

  initModal();
});

const openMergeModal = (user) => {
  sourceUser.value = user;
  targetUserId.value = '';

  // 確保 modal 有被初始化
  if (!mergeModalInstance && window.bootstrap && mergeModalRef.value) {
    mergeModalInstance = new window.bootstrap.Modal(mergeModalRef.value);
    console.log('⚙️ 即時初始化 Modal');
  }

  if (mergeModalInstance) {
    mergeModalInstance.show();
    console.log('📦 開啟合併用戶視窗');
  } else {
    console.error('❌ 無法開啟 Modal：Bootstrap 未載入或 ref 尚未綁定');
    alert('系統尚未載入完成，請稍後再試一次。');
  }
};

const openAddManualUserModal = () => {
  newUserName.value = '';
  if (addManualModalInstance) {
    addManualModalInstance.show();
  } else {
    console.error('❌ 無法開啟新增用戶 Modal');
    alert('系統尚未載入完成，請稍後再試一次。');
  }
};

const confirmAddManualUser = async () => {
  const name = newUserName.value.trim();
  if (!name) {
    showStatus('❌ 請輸入用戶姓名', 'error');
    return;
  }
  try {
    const newUser = await addManual(name);
    users.value.unshift(newUser.user);
    showStatus('✅ 臨時用戶已新增', 'success');
    if (addManualModalInstance) addManualModalInstance.hide();
  } catch (error) {
    showStatus(`❌ 新增失敗: ${error.message || '未知錯誤'}`, 'error');
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

<style scoped>
/* 使用命名空間來安全地覆寫樣式，並限定其只在此元件生效 */
.user-management-page .table-responsive {
  border: 1px solid #dee2e6; /* Re-add a border to the container */
  border-radius: 0.375rem; /* Re-add rounded corners */
}

.user-management-page .table {
  border-collapse: collapse !important; /* 關鍵：壓平所有間距 */
  margin-bottom: 0 !important; /* 確保表格本身沒有底部外邊距 */
}

.user-management-page .table tbody tr td {
  vertical-align: middle !important; /* 強制所有欄位垂直置中 */
}

</style>