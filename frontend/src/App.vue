<template>
  <div class="max-w-screen-2xl mx-auto font-sans">
    <div class="bg-white p-5 rounded-lg shadow-md mb-5">
      <div class="text-center mb-4">
        <h2 class="text-xl font-bold text-indigo-600">{{ weekTitle }}</h2>
      </div>
      <div class="flex flex-wrap gap-2 justify-center">
        <button class="px-4 py-2 rounded-md text-sm font-medium transition bg-indigo-600 text-white hover:bg-indigo-700" @click="changeWeek(-1)">⬅️ 上一週</button>
        <button class="px-4 py-2 rounded-md text-sm font-medium transition bg-indigo-600 text-white hover:bg-indigo-700" @click="changeWeek(1)">下一週 ➡️</button>
        <button class="px-4 py-2 rounded-md text-sm font-medium transition bg-indigo-600 text-white hover:bg-indigo-700" @click="loadInitialData">🔄 重新載入</button>
        <button class="px-4 py-2 rounded-md text-sm font-medium transition bg-green-600 text-white hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed" @click="sendWeekReminders" :disabled="isSendingWeek">📨 {{ isSendingWeek ? '發送中...' : '發送整週提醒' }}</button>
      </div>
    </div>

    <!-- Schedule Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 pb-4">
      <div v-for="dayData in weekSchedule" :key="dayData.date_info.date" class="bg-white rounded-lg p-3 shadow-lg flex flex-col gap-y-3">
        <div class="bg-gradient-to-r from-indigo-600 to-purple-700 text-white p-2.5 rounded-md text-center">
          <h3 class="text-base font-bold">{{ dayData.date_info.day_name }}</h3>
          <p class="text-sm opacity-90">{{ dayData.date_info.display }}</p>
        </div>
        <div class="flex-grow space-y-1">
          <div v-if="dayData.is_closed" class="text-center text-red-600 font-bold p-5 bg-red-50 rounded-md">😴<br>本日休診</div>
          <template v-else>
            <div v-for="(apt, time, index) in dayData.appointments" :key="time" class="flex items-center gap-2">
              <span class="w-12 text-right text-sm font-medium text-gray-600">{{ time }}</span>
              <div class="relative flex-1">
                <div 
                  class="w-full p-1.5 border border-gray-300 text-sm rounded bg-white cursor-pointer truncate flex justify-between items-center text-gray-800" 
                  :class="{ 'text-gray-500': !apt.user_id }" 
                  @click="toggleDropdown(dayData.date_info.date, time, index)">
                  {{ apt.user_name || '-- 未預約 --' }}
                  <span class="ml-2 text-gray-400 text-xs">▼</span>
                </div>
                <div v-if="openSelect === `${dayData.date_info.date}-${time}`" class="absolute top-full left-0 right-0 bg-white border border-gray-300 rounded-md max-h-48 overflow-y-auto z-10 shadow-lg mt-1">
                  <div v-if="selectStep === 1">
                    <div v-if="previousUser" class="px-2.5 py-2 cursor-pointer text-sm text-blue-600 font-bold border-b hover:bg-gray-100" @click.stop="selectUser(dayData.date_info.date, time, previousUser.id, previousUser.name)">
                      ➡️ 同上 ({{ previousUser.name }})
                    </div>
                    <div class="px-2.5 py-2 cursor-pointer text-sm text-gray-800 hover:bg-gray-100" @click.stop="selectUser(dayData.date_info.date, time, '', '-- 未預約 --')">-- 未預約 --</div>
                    <div v-for="key in sortedZhuyinKeys" :key="key" class="px-2.5 py-2 cursor-pointer text-sm text-gray-800 hover:bg-gray-100" @click.stop="renderUserOptions(key)">
                      {{ key }}
                    </div>
                  </div>
                  <div v-if="selectStep === 2">
                    <div class="px-2.5 py-2 cursor-pointer text-sm font-bold border-b text-purple-700 hover:bg-gray-100" @click.stop="selectStep = 1">← 返回注音</div>
                    <div v-for="user in usersInGroup" :key="user.id" class="px-2.5 py-2 cursor-pointer text-sm text-gray-800 hover:bg-gray-100" @click.stop="selectUser(dayData.date_info.date, time, user.id, user.name)">
                      {{ user.name }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
        <button v-if="!dayData.is_closed" class="mt-2 w-full px-4 py-2 rounded-md text-sm font-medium transition bg-green-600 text-white hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed" @click="sendDayReminders($event, dayData.date_info.date, dayData.date_info.day_name)" :disabled="isSendingDay[dayData.date_info.date]">
           {{ isSendingDay[dayData.date_info.date] ? '發送中...' : `📤 發送 ${dayData.date_info.day_name} 提醒` }}
        </button>
      </div>
    </div>

    <!-- Status Message -->
    <div v-if="status.show" class="fixed top-5 right-5 px-5 py-4 rounded-md shadow-lg text-white" :class="status.type === 'success' ? 'bg-gray-800' : 'bg-red-700'" >
      {{ status.message }}
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

// --- Computed Properties ---
const weekTitle = computed(() => {
  if (currentWeekOffset.value === 0) return '本週預約';
  if (currentWeekOffset.value === 1) return '下週預約';
  if (currentWeekOffset.value === -1) return '上週預約';
  if (currentWeekOffset.value > 1) return `未來第 ${currentWeekOffset.value} 週`;
  return `過去第 ${Math.abs(currentWeekOffset.value)} 週`;
});

const sortedZhuyinKeys = computed(() => {
  const zhuyinOrder = 'ㄅㄆㄇㄈㄉㄊㄋㄌㄍㄎㄏㄐㄑㄒㄓㄔㄕㄖㄗㄘㄙㄧㄨㄩㄚㄛㄜㄝㄞㄟㄠㄡㄢㄣㄤㄥㄦ#';
  return Object.keys(groupedUsers.value).sort((a, b) => {
    if (a === '#') return 1;
    if (b === '#') return -1;
    return zhuyinOrder.indexOf(a) - zhuyinOrder.indexOf(b);
  });
});

// --- Methods ---
function showStatus(message, type = 'success', duration = 3000) {
  status.value = { show: true, message, type };
  setTimeout(() => {
    status.value.show = false;
  }, duration);
}

async function loadUsers() {
  try {
    const response = await axios.get('/api/admin/users');
    allUsers.value = response.data.users || [];
    groupedUsers.value = groupUsersByZhuyin(allUsers.value);
  } catch (error) {
    showStatus('❌ 用戶載入失敗', 'error');
  }
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
  try {
    const response = await axios.get(`/api/admin/get_week_appointments?offset=${currentWeekOffset.value}`);
    const schedule = response.data.week_schedule || {};

    // The API doesn't explicitly provide an `is_closed` flag per day.
    // We deduce it based on whether there are any appointment slots.
    for (const dateKey in schedule) {
        if (Object.prototype.hasOwnProperty.call(schedule, dateKey)) {
            const day = schedule[dateKey];
            // Assuming if a day has no appointment slots, it's considered closed.
            day.is_closed = !day.appointments || Object.keys(day.appointments).length === 0;
        }
    }
    weekSchedule.value = schedule;
    showStatus('✅ 資料已更新', 'success');
  } catch (error) {
    showStatus('❌ 排程載入失敗', 'error');
    console.error("Schedule loading error:", error);
  }
}

async function loadInitialData() {
  showStatus('載入中...', 'info');
  await Promise.all([loadUsers(), loadSchedule()]);
}

function changeWeek(offset) {
  currentWeekOffset.value += offset;
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

function renderUserOptions(zhuyinInitial) {
  usersInGroup.value = groupedUsers.value[zhuyinInitial] || [];
  selectStep.value = 2;
}

async function selectUser(date, time, userId, userName) {
  const originalUserName = weekSchedule.value[date]?.appointments[time]?.user_name;
  const originalUserId = weekSchedule.value[date]?.appointments[time]?.user_id;

  closeAllSelects();

  // Optimistically update UI
  if (weekSchedule.value[date] && weekSchedule.value[date].appointments[time]) {
    weekSchedule.value[date].appointments[time].user_id = userId;
    weekSchedule.value[date].appointments[time].user_name = userName;
  }

  showStatus('儲存中...', 'info');
  try {
    const response = await axios.post('/api/admin/save_appointment', {
      date, time, user_id: userId, user_name: userName
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

async function sendWeekReminders() {
  if (!confirm('確定要發送整週的預約提醒嗎？')) return;
  isSendingWeek.value = true;
  try {
    const response = await axios.post('/api/admin/send_appointment_reminders', { type: 'week' });
    const result = response.data;
    showStatus(`✅ 已發送 ${result.sent_count} 則提醒${result.failed_count > 0 ? `，${result.failed_count} 則失敗` : ''}`);
  } catch (error) {
    showStatus('❌ 發送失敗', 'error');
  } finally {
    isSendingWeek.value = false;
  }
}

async function sendDayReminders(event, date, dayName) {
  if (!confirm(`確定要發送 ${dayName} 的預約提醒嗎？`)) return;
  isSendingDay.value[date] = true;
  try {
    const response = await axios.post('/api/admin/send_appointment_reminders', { type: 'day', date: date });
    const result = response.data;
    showStatus(`✅ 已發送 ${dayName} 的 ${result.sent_count} 則提醒${result.failed_count > 0 ? `，${result.failed_count} 則失敗` : ''}`);
  } catch (error) {
    showStatus('❌ 發送失敗', 'error');
  } finally {
    isSendingDay.value[date] = false;
  }
}

const handleClickOutside = (e) => {
    // Close dropdown if click is outside of any custom-select-container
    if (!e.target.closest('.relative')) {
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