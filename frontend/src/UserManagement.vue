<template>
  <div>
    <!-- Header Section -->
    <div class="d-flex justify-content-between align-items-center mb-4">
      <h2 class="mb-0 text-primary fw-bold">用戶管理</h2>
      <div class="d-flex gap-2 align-items-center">
        <input type="text" class="form-control" placeholder="依姓名或注音搜尋..." v-model="searchTerm" style="width: 250px;">
        <span class="badge bg-secondary-subtle text-secondary-emphasis fs-6">共 {{ filteredUsers.length }} 位</span>
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
    <div v-else class="table-responsive shadow-sm rounded">
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
                <span @click="startEditing(user, 'name')" class="editable-field">
                  {{ user.name }} <i class="bi bi-pencil-fill text-primary ms-1"></i>
                </span>
              </td>
              <td>{{ user.zhuyin }}</td>
              <td class="text-muted" style="font-size: 0.8rem; max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="user.line_user_id">{{ user.line_user_id }}</td>
              <td>
                <span @click="startEditing(user, 'phone')" class="editable-field">{{ user.phone }} <i class="bi bi-pencil-fill text-primary ms-1"></i></span>
              </td>
              <td>
                <span @click="startEditing(user, 'phone2')" class="editable-field">{{ user.phone2 }} <i class="bi bi-pencil-fill text-primary ms-1"></i></span>
              </td>
              <td class="text-center">
                 <button v-if="user.line_user_id && user.line_user_id.startsWith('U')" @click="refreshUserProfile(user.id)" class="btn btn-sm btn-outline-info py-0 px-1" title="從LINE更新資料">
                      <i class="bi bi-arrow-repeat" style="font-size: 1.1rem;"></i>
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

    <!-- Edit Modal -->
    <div class="modal fade" id="editUserModal" tabindex="-1" aria-labelledby="editUserModalLabel" aria-hidden="true" ref="editModalRef">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title" id="editUserModalLabel">{{ modalTitle }}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <input type="text" class="form-control" v-model="editingValue" @keyup.enter="handleModalSave">
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
            <button type="button" class="btn btn-primary" @click="handleModalSave">儲存變更</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, nextTick } from 'vue';
import axios from 'axios';

const users = ref([]);
const loading = ref(true);
const error = ref(null);
const searchTerm = ref('');

const editingUser = ref(null);
const editingField = ref('');
const editingValue = ref('');

const editModalRef = ref(null);
let editModalInstance = null;
const modalTitle = ref('');

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
    const response = await axios.get('/api/admin/users');
    users.value = response.data.users;
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

const startEditing = async (user, field) => {
  editingUser.value = user.id;
  editingField.value = field;
  editingValue.value = user[field] || '';
  modalTitle.value = `編輯 ${user.name} 的${getFieldName(field)}`;
  if (editModalInstance) {
    editModalInstance.show();
  }
};

const handleModalSave = async () => {
  const user = users.value.find(u => u.id === editingUser.value);
  const field = editingField.value;
  if (!user) return;

  // If value hasn't changed, just close the modal.
  if (user[field] === editingValue.value || (user[field] === null && editingValue.value === '')) {
    if (editModalInstance) editModalInstance.hide();
    cancelEditing();
    return;
  }

  try {
    if (field === 'name') {
      await axios.post('/admin/update_user_name', { user_id: user.id, name: editingValue.value });
      showStatus('用戶名稱已更新', 'success');
    } else {
      await axios.post('/admin/update_user_phone', { user_id: user.id, field: field, phone: editingValue.value });
      showStatus('電話已更新', 'success');
    }
  } catch (err) {
    showStatus('更新失敗', 'error');
  } finally {
    // This block runs after try/catch is complete. Hide the modal and reset state.
    if (editModalInstance) {
      editModalInstance.hide();
    }
    cancelEditing();
  }

  // IMPORTANT: Reload users *after* the modal logic is completely finished.
  await loadUsers();
};

const cancelEditing = () => {
  editingUser.value = null;
  editingField.value = '';
  editingValue.value = '';
};
onMounted(() => {
  loadUsers();
  if (editModalRef.value) {
    editModalInstance = new window.bootstrap.Modal(editModalRef.value);
  }
});

const refreshUserProfile = async (userId) => {
  showStatus('正在從LINE更新資料...', 'info');
  try {
    // Using the old endpoint as it's simpler for this page
    const response = await axios.post(`/admin/refresh_user_profile/${userId}`);
    if (response.data.status === 'success') {
      showStatus('✅ 用戶資料已更新，將重新載入列表。', 'success');
      await loadUsers(); // Reload all users to see the change
    } else {
      throw new Error(response.data.message);
    }
  } catch (error) {
    showStatus(`❌ 更新失敗: ${error.message || '未知錯誤'}`, 'error');
  }
};

const addManualUser = async () => {
  const name = prompt("請輸入臨時用戶的姓名：");
  if (name && name.trim()) {
    showStatus('正在新增臨時用戶...', 'info');
    try {
      const response = await axios.post('/api/admin/users/add_manual', { name: name.trim() });
      if (response.data.status === 'success') {
        users.value.unshift(response.data.user); // Add to the top of the list
        showStatus('✅ 臨時用戶已新增', 'success');
      } else {
        throw new Error(response.data.message);
      }
    } catch (error) {
      showStatus(`❌ 新增失敗: ${error.message || '未知錯誤'}`, 'error');
    }
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