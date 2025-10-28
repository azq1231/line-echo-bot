<template>
  <div class="tw-max-w-screen-2xl tw-mx-auto tw-font-sans">
    <div class="tw-bg-white tw-p-5 tw-rounded-lg tw-shadow-md tw-mb-5">
      <div class="tw-text-center tw-mb-4">
        <h2 class="tw-text-xl tw-font-bold tw-text-indigo-600">{{ weekTitle }}</h2>
      </div>
      <div class="tw-flex tw-flex-wrap tw-gap-2 tw-justify-center">
        <button class="tw-px-4 tw-py-2 tw-rounded-md tw-text-sm tw-font-medium tw-transition tw-bg-indigo-600 tw-text-white hover:tw-bg-indigo-700" @click="changeWeek(-1)">⬅️ 上一週</button>
        <button class="tw-px-4 tw-py-2 tw-rounded-md tw-text-sm tw-font-medium tw-transition tw-bg-indigo-600 tw-text-white hover:tw-bg-indigo-700" @click="changeWeek(1)">下一週 ➡️</button>
        <button class="tw-px-4 tw-py-2 tw-rounded-md tw-text-sm tw-font-medium tw-transition tw-bg-indigo-600 tw-text-white hover:tw-bg-indigo-700" @click="loadInitialData">🔄 重新載入</button>
        <button class="tw-px-4 tw-py-2 tw-rounded-md tw-text-sm tw-font-medium tw-transition disabled:tw-cursor-not-allowed" @click="sendWeekReminders" :disabled="isSendingWeek || !weekHasRemindable" :class="weekButtonClass">📨 {{ weekButtonText }}</button>
        <!-- New button for adding manual user -->
        <button class="tw-px-4 tw-py-2 tw-rounded-md tw-text-sm tw-font-medium tw-transition tw-bg-green-600 tw-text-white hover:tw-bg-green-700" @click="openAddManualUserModal">➕ 新增臨時用戶</button>
      </div>
      <div class="tw-text-center tw-mt-3 tw-text-xs tw-text-gray-500 tw-space-y-1">
        <div>提醒按鈕：<span class="tw-font-semibold tw-text-gray-700">白色</span>=可發送, <span class="tw-font-semibold tw-text-blue-600">藍色</span>=已發送, <span class="tw-font-semibold tw-text-red-600">紅色</span>=無可提醒對象</div>
        <div>預約時段：<span class="tw-px-1 tw-rounded tw-bg-red-200 tw-text-red-800 tw-font-semibold">紅色底</span> = 臨時用戶 (無法發送LINE提醒)</div>
      </div>
    </div>

    <!-- Loading Spinner -->
    <div v-if="isLoading" class="tw-flex tw-justify-center tw-items-center tw-py-10">
      <div class="tw-animate-spin tw-rounded-full tw-h-12 tw-w-12 tw-border-b-2 tw-border-indigo-500"></div>
      <p class="tw-ml-4 tw-text-gray-600">載入中...</p>
    </div>

    <!-- Schedule Grid -->
    <div v-else class="tw-grid tw-grid-cols-1 sm:tw-grid-cols-2 md:tw-grid-cols-3 lg:tw-grid-cols-5 tw-gap-3 tw-pb-4">
      <div v-for="dayData in weekSchedule" :key="dayData.date_info.date" 
           class="tw-rounded-lg tw-p-3 tw-shadow-lg tw-flex tw-flex-col tw-gap-y-3"
           :class="dayData.is_closed ? 'tw-bg-gray-100' : 'tw-bg-white'">
        <div 
          class="tw-text-white tw-p-2.5 tw-rounded-md tw-text-center"
          :class="dayData.is_closed ? 'tw-bg-gray-400' : 'tw-bg-gradient-to-r tw-from-indigo-600 tw-to-purple-700'">
          <h3 class="tw-text-base tw-font-bold">{{ dayData.date_info.day_name }}</h3>
          <p class="tw-text-sm tw-opacity-90">{{ dayData.date_info.display }}</p>
        </div>
        <div class="tw-flex-grow tw-space-y-1">
          <div v-if="dayData.is_closed" class="tw-flex-grow tw-flex tw-items-center tw-justify-center tw-text-center tw-text-gray-500 tw-font-bold tw-p-5 tw-bg-gray-200 tw-rounded-md">
            😴<br>本日休診
          </div>
          <template v-else>

            <div v-for="(apt, time, index) in dayData.appointments" :key="time" class="tw-flex tw-items-center tw-gap-2">
              <span class="tw-w-12 tw-text-right tw-text-sm tw-font-medium tw-text-gray-600">{{ time }}</span>
              <div 
                class="tw-relative tw-flex-1"
                @dragover.prevent="handleDragOver(dayData.date_info.date, time, apt)"
                @dragleave="handleDragLeave(dayData.date_info.date, time)"
                @drop="handleDrop(dayData.date_info.date, time)"
                :class="{ 'tw-bg-green-100 tw-border-green-400': isDragOver(`${dayData.date_info.date}-${time}`) }"
              >
                <div 
                  class="tw-w-full tw-p-1.5 tw-border tw-text-sm tw-rounded tw-cursor-pointer tw-truncate tw-flex tw-justify-between tw-items-center" 
                  :class="{ 
                    'tw-text-gray-500': !apt.user_id,
                    'tw-bg-red-200 tw-border-red-400 tw-text-red-800': apt.user_id?.startsWith('manual_'),
                    'tw-bg-white tw-border-gray-300 tw-text-gray-800': !apt.user_id?.startsWith('manual_'),
                    'tw-font-semibold': apt.user_id && apt.user_id.startsWith('manual_')
                  }" 
                  @click="toggleDropdown(dayData.date_info.date, time, index)">
                  {{ apt.user_name || '-- 未預約 --' }}
                  <span class="tw-ml-2 tw-text-gray-400 tw-text-xs">▼</span>
                </div>
                <div v-if="openSelect === `${dayData.date_info.date}-${time}`" class="tw-absolute tw-top-full tw-left-0 tw-right-0 tw-bg-white tw-border tw-border-gray-300 tw-rounded-md tw-max-h-48 tw-overflow-y-auto tw-z-10 tw-shadow-lg tw-mt-1">
                  <div v-if="selectStep === 1">
                    <div v-if="previousUser" class="tw-px-2.5 tw-py-2 tw-cursor-pointer tw-text-sm tw-text-blue-600 tw-font-bold tw-border-b hover:tw-bg-gray-100" @click.stop="selectUser(dayData.date_info.date, time, previousUser.id, previousUser.name)">
                      ➡️ 同上 ({{ previousUser.name }})
                    </div>
                    <div class="tw-px-2.5 tw-py-2 tw-cursor-pointer tw-text-sm tw-text-gray-800 hover:tw-bg-gray-100" @click.stop="selectUser(dayData.date_info.date, time, '', '-- 未預約 --')">-- 未預約 --</div>
                    <div v-for="key in sortedZhuyinKeys" :key="key" class="tw-px-2.5 tw-py-2 tw-cursor-pointer tw-text-sm tw-text-gray-800 hover:tw-bg-gray-100" @click.stop="renderUserOptions(key)">
                      {{ key }}
                    </div>
                  </div>
                  <div v-if="selectStep === 2">
                    <div class="tw-px-2.5 tw-py-2 tw-cursor-pointer tw-text-sm tw-font-bold tw-border-b tw-text-purple-700 hover:tw-bg-gray-100" @click.stop="selectStep = 1">← 返回注音</div>
                    <div v-for="user in usersInGroup" :key="user.id" class="tw-px-2.5 tw-py-2 tw-cursor-pointer tw-text-sm tw-text-gray-800 hover:tw-bg-gray-100" @click.stop="handleUserSelection(dayData.date_info.date, time, user)">
                      {{ user.name }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
        <!-- Waiting List Section -->
        <div v-if="!dayData.is_closed" class="tw-mt-4 tw-pt-3 tw-border-t">
            <h4 class="tw-text-sm tw-font-semibold tw-text-gray-500 tw-mb-2">備取名單</h4>
            <div class="tw-space-y-1 tw-text-sm">
                <div v-if="!dayData.waiting_list || dayData.waiting_list.length === 0" class="tw-text-gray-400 tw-text-xs tw-text-center tw-py-2">尚無備取</div>
                <div v-for="item in dayData.waiting_list" :key="item.id" 
                     class="tw-flex tw-items-center tw-justify-between tw-p-1.5 tw-bg-yellow-50 tw-border tw-border-yellow-200 tw-rounded tw-cursor-grab"
                     draggable="true"
                     @dragstart="handleDragStart($event, item)">
                    <span>{{ item.user_name }}</span>
                    <button @click="removeFromWaitingList(item.id, dayData.date_info.date)" class="tw-text-red-500 hover:tw-text-red-700 tw-text-xs">✕</button>
                </div>
            </div>
            <div class="tw-relative tw-mt-2">
              <button @click="toggleWaitingListDropdown(dayData.date_info.date)" class="tw-w-full tw-text-xs tw-text-center tw-py-1.5 tw-bg-gray-100 hover:tw-bg-gray-200 tw-rounded-md tw-text-gray-600">+ 新增備取</button>
              <!-- Waiting List User Selection Dropdown -->
              <div v-if="openSelect === `waiting-${dayData.date_info.date}`" class="tw-absolute tw-bottom-full tw-left-0 tw-right-0 tw-bg-white tw-border tw-border-gray-300 tw-rounded-md tw-max-h-48 tw-overflow-y-auto tw-z-10 tw-shadow-lg tw-mb-1">
                <div v-if="selectStep === 1">
                  <div v-for="key in sortedZhuyinKeys" :key="key" class="tw-px-2.5 tw-py-2 tw-cursor-pointer tw-text-sm tw-text-gray-800 hover:tw-bg-gray-100" @click.stop="renderUserOptions(key)">
                    {{ key }}
                  </div>
                </div>
                <div v-if="selectStep === 2">
                  <div class="tw-px-2.5 tw-py-2 tw-cursor-pointer tw-text-sm tw-font-bold tw-border-b tw-text-purple-700 hover:tw-bg-gray-100" @click.stop="selectStep = 1">← 返回注音</div>
                  <div v-for="user in usersInGroup" :key="user.id" class="tw-px-2.5 tw-py-2 tw-cursor-pointer tw-text-sm tw-text-gray-800 hover:tw-bg-gray-100" @click.stop="handleUserSelection(dayData.date_info.date, null, user)">
                    {{ user.name }}
                  </div>
                </div>
              </div>
            </div>
        </div>

        <button v-if="!dayData.is_closed" class="tw-mt-2 tw-w-full tw-px-4 tw-py-2 tw-rounded-md tw-text-sm tw-font-medium tw-transition disabled:tw-cursor-not-allowed" @click="sendDayReminders(dayData.date_info.date, dayData.date_info.day_name)" :disabled="isSendingDay[dayData.date_info.date] || !dayHasRemindable(dayData)" :class="dayButtonClass(dayData)">
           {{ dayButtonText(dayData) }}
        </button>
      </div>
    </div>

    <!-- Status Message -->
    <div v-if="status.show" class="tw-fixed tw-top-5 tw-right-5 tw-px-5 tw-py-4 tw-rounded-md tw-shadow-lg tw-text-white" :class="status.type === 'success' ? 'tw-bg-gray-800' : 'tw-bg-red-700'" >
      {{ status.message }}
    </div>

    <!-- Add Manual User Modal -->
    <div v-if="showAddManualUserModal" class="tw-fixed tw-inset-0 tw-bg-gray-600 tw-bg-opacity-50 tw-overflow-y-auto tw-h-full tw-w-full tw-z-50 tw-flex tw-justify-center tw-items-center">
      <div class="tw-relative tw-p-5 tw-border tw-w-96 tw-shadow-lg tw-rounded-md tw-bg-white">
        <h3 class="tw-text-lg tw-font-bold tw-mb-4">新增臨時用戶</h3>
        <input 
          type="text" 
          v-model="newManualUserName" 
          placeholder="請輸入用戶姓名" 
          class="tw-mt-1 tw-block tw-w-full tw-px-3 tw-py-2 tw-border tw-border-gray-300 tw-rounded-md tw-shadow-sm focus:tw-outline-none focus:tw-ring-indigo-500 focus:tw-border-indigo-500 sm:tw-text-sm"
          @keyup.enter="addManualUser"
        />
        <div class="tw-mt-4 tw-flex tw-justify-end tw-space-x-2">
          <button 
            @click="closeAddManualUserModal" 
            class="tw-px-4 tw-py-2 tw-bg-gray-300 tw-text-gray-800 tw-rounded-md hover:tw-bg-gray-400"
          >
            取消
          </button>
          <button 
            @click="addManualUser" 
            :disabled="isAddingManualUser || !newManualUserName.trim()"
            class="tw-px-4 tw-py-2 tw-bg-indigo-600 tw-text-white tw-rounded-md hover:tw-bg-indigo-700 disabled:tw-opacity-50 disabled:tw-cursor-not-allowed"
          >
            <span v-if="isAddingManualUser">新增中...</span>
            <span v-else>確定新增</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue';
import axios from 'axios';

const allUsers = ref([]);
const groupedUsers = ref({});
const weekSchedule = ref({});
const currentWeekOffset = ref(0);
const openSelect = ref(null); // Stores "date-time" string
const selectStep = ref(1); // 1 for zhuyin, 2 for users
const usersInGroup = ref([]);

const previousUser = ref(null); // To store user from the slot above
const status = ref({ show: false, message: '', type: 'info' });
const isSendingWeek = ref(false);
const isSendingDay = ref({});
const weekReminderSent = ref(false);
const dayReminderSent = ref({});

const draggedItem = ref(null);
const dragOverTarget = ref(null);

// New reactive properties for manual user modal
const showAddManualUserModal = ref(false);
const newManualUserName = ref('');
const isAddingManualUser = ref(false);

// New loading state
const isLoading = ref(true);

// --- Computed Properties ---
const weekTitle = computed(() => {
  if (currentWeekOffset.value === 0) return '本週預約';
  if (currentWeekOffset.value === 1) return '下週預約';
  if (currentWeekOffset.value === -1) return '上週預約';
  if (currentWeekOffset.value > 1) return `未來第 ${currentWeekOffset.value} 週`;
  return `過去第 ${Math.abs(currentWeekOffset.value)} 週`;
});

const userMap = computed(() => {
  const map = new Map();
  allUsers.value.forEach(user => { // 確保 user.id 存在且有效
    if (user && user.id !== undefined && user.id !== null) {
      map.set(user.id.toString(), user);
    }
  });
  return map;
});

const sortedZhuyinKeys = computed(() => {
  const zhuyinOrder = 'ㄅㄆㄇㄈㄉㄊㄋㄌㄍㄎㄏㄐㄑㄒㄓㄔㄕㄖㄗㄘㄙㄧㄨㄩㄚㄛㄜㄝㄞㄟㄠㄡㄢㄣㄤㄥㄦ#';
  return Object.keys(groupedUsers.value).sort((a, b) => {
    if (a === '#') return 1;
    if (b === '#') return -1;
    return zhuyinOrder.indexOf(a) - zhuyinOrder.indexOf(b);
  });
});

const weekHasRemindable = computed(() => {
  for (const date in weekSchedule.value) {
    if (dayHasRemindable(weekSchedule.value[date])) {
      return true;
    }
  }
  return false;
});

const weekButtonText = computed(() => {
  if (isSendingWeek.value) return '發送中...';
  if (weekReminderSent.value) return '本週提醒已發送';
  if (!weekHasRemindable.value) return '本週無可提醒對象';
  return '發送整週提醒';
});

const weekButtonClass = computed(() => {
  if (isSendingWeek.value) return 'tw-bg-gray-400 tw-text-white';
  if (!weekHasRemindable.value) return 'tw-bg-red-200 tw-text-red-700';
  if (weekReminderSent.value) return 'tw-bg-blue-600 tw-text-white';
  return 'tw-bg-white tw-text-gray-700 tw-border tw-border-gray-300 hover:tw-bg-gray-50';
});

function isDragOver(targetId) {
  return dragOverTarget.value === targetId;
}


function dayHasRemindable(dayData) {
  if (!dayData || dayData.is_closed || !dayData.appointments) return false;
  for (const time in dayData.appointments) {
    const apt = dayData.appointments[time];
    if (apt.user_id) {
      // Reliably check the userMap for the line_id.
      const user = userMap.value.get(apt.user_id.toString());
      // The backend API sends 'line_user_id'. We check for that and ensure it starts with 'U' for a real LINE user.
      if (user && user.line_user_id && user.line_user_id.startsWith('U')) { 
        return true; // Found at least one user with a line_id
      }
    }
  }
  return false;
}

function dayButtonText(dayData) {
  const date = dayData.date_info.date;
  if (isSendingDay.value[date]) return '發送中...';
  if (dayReminderSent.value[date]) return '本日提醒已發送';
  if (!dayHasRemindable(dayData)) return '本日無可提醒對象';
  return `📤 發送 ${dayData.date_info.day_name} 提醒`;
}

function dayButtonClass(dayData) {
  const date = dayData.date_info.date;
  if (isSendingDay.value[date]) return 'tw-bg-gray-400 tw-text-white';
  if (!dayHasRemindable(dayData)) return 'tw-bg-red-200 tw-text-red-700';
  if (dayReminderSent.value[date]) return 'tw-bg-blue-600 tw-text-white';
  return 'tw-bg-white tw-text-gray-700 tw-border tw-border-gray-300 hover:tw-bg-gray-50';
}


// --- Methods ---
function showStatus(message, type = 'success', duration = 3000) {
  status.value = { show: true, message, type };
  setTimeout(() => {
    status.value.show = false;
  }, duration);
}

function groupUsersByZhuyin(users) {
  const groups = users.reduce((acc, user) => {
    const initial = user.zhuyin ? user.zhuyin[0] : '#';
    if (!acc[initial]) acc[initial] = [];
    acc[initial].push(user);
    return acc;
  }, {});
  return groups;
}

async function loadSchedule() {
  isLoading.value = true; 
  try {
    const response = await axios.get(`/api/admin/get_week_appointments?offset=${currentWeekOffset.value}`);

    allUsers.value = response.data.users || []; // <--- Update allUsers here

    groupedUsers.value = groupUsersByZhuyin(allUsers.value); // <--- Re-group users here

    // 修正：直接使用後端傳來的 week_schedule，不再覆蓋 is_closed 狀態
    weekSchedule.value = response.data.week_schedule || {};
    showStatus('✅ 資料已更新', 'success');
  } catch (error) {
    showStatus('❌ 排程載入失敗', 'error');
    console.error("Schedule loading error:", error);
  } finally {
    // 無論成功或失敗，最後都要將載入狀態設為 false
    isLoading.value = false;
  }
}

async function loadInitialData() {
  showStatus('載入中...', 'info'); // loadSchedule now handles fetching users as well
  await loadSchedule();
}

function changeWeek(offset) {
  currentWeekOffset.value += offset;
  weekReminderSent.value = false; // Reset sent status for the new week
  dayReminderSent.value = {};
  loadSchedule();
}

function closeAllSelects() {
  openSelect.value = null;
  selectStep.value = 1;
  usersInGroup.value = [];
}

function toggleDropdown(date, time, index) {
  const selectId = `${date}-${time}`;
  if (openSelect.value === selectId) {
    closeAllSelects();
    previousUser.value = null;
  } else {
    openSelect.value = selectId;
    selectStep.value = 1; // Reset to zhuyin selection

    // Find previous user for the "copy from above" feature
    previousUser.value = null;
    if (index > 0) {
      const daySchedule = weekSchedule.value[date];
      if (daySchedule && daySchedule.appointments) {
        const timeSlots = Object.keys(daySchedule.appointments);
        const prevTime = timeSlots[index - 1];
        const prevApt = daySchedule.appointments[prevTime];
        if (prevApt && prevApt.user_id) {
          previousUser.value = { id: prevApt.user_id, name: prevApt.user_name };
        }
      }
    }
  }
}

function toggleWaitingListDropdown(date) {
  const selectId = `waiting-${date}`;
  if (openSelect.value === selectId) {
    closeAllSelects();
  } else {
    openSelect.value = selectId;
    selectStep.value = 1;
  }
}

function renderUserOptions(zhuyinInitial) {
  usersInGroup.value = groupedUsers.value[zhuyinInitial] || [];
  selectStep.value = 2;
}

async function selectUser(date, time, userId, userName, waitingListItemId = null) {
  const originalUserId = weekSchedule.value[date]?.appointments[time]?.user_id;
  const originalUserName = weekSchedule.value[date]?.appointments[time]?.user_name;

  closeAllSelects();

  // Optimistically update UI
  if (weekSchedule.value[date] && weekSchedule.value[date].appointments[time]) {
    weekSchedule.value[date].appointments[time].user_id = userId; // This might be a waiting list item ID
    weekSchedule.value[date].appointments[time].user_name = userName;
  }

  showStatus('儲存中...', 'info');
  try {
    const response = await axios.post('/api/admin/save_appointment', {
      date, time, user_id: userId, user_name: userName, waiting_list_item_id: waitingListItemId
    });
    if (response.data.status === 'success') {
      showStatus('✅ 預約已儲存', 'success');
    } else {
      throw new Error(response.data.message || '儲存失敗');
    }
  } catch (error) {
    showStatus(`❌ 儲存失敗: ${error.message || '未知錯誤'}`, 'error');
    // Revert optimistic update on failure
    if (weekSchedule.value[date] && weekSchedule.value[date].appointments[time]) {
      weekSchedule.value[date].appointments[time].user_id = originalUserId;
      weekSchedule.value[date].appointments[time].user_name = originalUserName;
    }
  }
}

async function addToWaitingList(date, user) {
  closeAllSelects();
  showStatus('新增備取中...', 'info');
  try {
    const response = await axios.post('/api/admin/waiting_list', {
      date,
      user_id: user.id,
      user_name: user.name
    });
    if (response.data.status === 'success') {
      if (!weekSchedule.value[date].waiting_list) {
        weekSchedule.value[date].waiting_list = [];
      }
      weekSchedule.value[date].waiting_list.push(response.data.item);
      showStatus('✅ 已新增至備取', 'success');
    } else {
      throw new Error(response.data.message || '新增失敗');
    }
  } catch (error) {
    showStatus(`❌ 新增備取失敗: ${error.message}`, 'error');
  }
}

async function removeFromWaitingList(itemId, date) {
    if (!confirm('確定要從備取名單中移除嗎？')) return;
    try {
        await axios.delete(`/api/admin/waiting_list/${itemId}`);
        const day = weekSchedule.value[date];
        if (day && day.waiting_list) {
            day.waiting_list = day.waiting_list.filter(item => item.id !== itemId);
        }
        showStatus('✅ 已從備取移除', 'success');
    } catch (error) {
        showStatus('❌ 移除失敗', 'error');
    }
}

function handleUserSelection(date, time, user) {
  if (openSelect.value.startsWith('waiting-')) {
    addToWaitingList(date, user);
  } else {
    selectUser(date, time, user.id, user.name);
  }
}

function handleDragStart(event, item) {
  draggedItem.value = item;
  event.dataTransfer.effectAllowed = 'move';
  event.dataTransfer.setData('text/plain', JSON.stringify(item));
}

function handleDragOver(date, time, apt) {
  if (draggedItem.value && !apt.user_id) {
    dragOverTarget.value = `${date}-${time}`;
  }
}

function handleDragLeave(date, time) {
  if (dragOverTarget.value === `${date}-${time}`) {
    dragOverTarget.value = null;
  }
}

async function handleDrop(date, time) {
  if (draggedItem.value && dragOverTarget.value === `${date}-${time}`) {
    await selectUser(date, time, draggedItem.value.user_id, draggedItem.value.user_name, draggedItem.value.id);
    // After successful drop and save, the backend will remove the waiting list item.
    // We just need to update the UI.
    weekSchedule.value[date].waiting_list = weekSchedule.value[date].waiting_list.filter(item => item.id !== draggedItem.value.id);
  }
  draggedItem.value = null;
  dragOverTarget.value = null;
}

async function sendWeekReminders() {
  // 修正：在確認訊息中加入日期範圍，讓管理員更清楚
  const dates = Object.keys(weekSchedule.value).sort();
  let dateRange = '';
  if (dates.length > 0) {
    const startDate = weekSchedule.value[dates[0]].date_info.display;
    const endDate = weekSchedule.value[dates[dates.length - 1]].date_info.display;
    dateRange = ` (${startDate} ~ ${endDate})`;
  }

  if (!confirm(`確定要發送「${weekTitle.value}」${dateRange} 的預約提醒嗎？`)) return;
  isSendingWeek.value = true;
  try {
    const response = await axios.post('/api/admin/send_appointment_reminders', { 
      type: 'week',
      offset: currentWeekOffset.value // 修正：將當前的週次偏移量傳給後端
    });
    const result = response.data;
    showStatus(`✅ 已發送 ${result.sent_count} 則提醒${result.failed_count > 0 ? `，${result.failed_count} 則失敗` : ''}`);
    if (result.sent_count > 0) weekReminderSent.value = true;
  } catch (error) {
    showStatus('❌ 發送失敗', 'error');
  } finally {
    isSendingWeek.value = false;
  }
}

async function sendDayReminders(date, dayName) {
  if (!confirm(`確定要發送 ${dayName} 的預約提醒嗎？`)) return;
  isSendingDay.value[date] = true;
  try {
    const response = await axios.post('/api/admin/send_appointment_reminders', { type: 'day', date: date });
    const result = response.data;
    if (result.sent_count > 0) dayReminderSent.value[date] = true;
    showStatus(`✅ 已發送 ${dayName} 的 ${result.sent_count} 則提醒${result.failed_count > 0 ? `，${result.failed_count} 則失敗` : ''}`);
  } catch (error) {
    showStatus('❌ 發送失敗', 'error');
  } finally {
    isSendingDay.value[date] = false;
  }
}

// New methods for manual user modal
function openAddManualUserModal() {
  showAddManualUserModal.value = true;
  newManualUserName.value = ''; // Clear previous input
}

function closeAddManualUserModal() {
  showAddManualUserModal.value = false;
}

async function addManualUser() {
  const name = newManualUserName.value.trim();
  if (!name) {
    showStatus('用戶姓名不能為空。', 'error');
    return;
  }

  isAddingManualUser.value = true;
  try {
    const response = await axios.post('/api/admin/users/add_manual', { name });
    if (response.data.status === 'success') {
      const newUser = response.data.user;
      allUsers.value.push(newUser); // Add to allUsers
      groupedUsers.value = groupUsersByZhuyin(allUsers.value); // Re-group users
      showStatus(`✅ 臨時用戶 "${newUser.name}" 已新增。`, 'success');
      closeAddManualUserModal();
    } else {
      throw new Error(response.data.message || '新增失敗');
    }
  } catch (error) {
    showStatus(`❌ 新增臨時用戶失敗: ${error.message || '未知錯誤'}`, 'error');
  } finally {
    isAddingManualUser.value = false;
  }
}

const handleClickOutside = (e) => {
    // Close dropdown if click is outside of any dropdown container
    if (!e.target.closest('.tw-relative')) {
        closeAllSelects();
    }
};

// --- Lifecycle Hooks ---
onMounted(() => {
  loadInitialData();
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});
</script>