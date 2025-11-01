<template>
  <div v-if="show" class="tw-fixed tw-inset-0 tw-bg-gray-600 tw-bg-opacity-50 tw-overflow-y-auto tw-h-full tw-w-full tw-z-50 tw-flex tw-justify-center tw-items-center" @click.self="close">
    <div class="tw-relative tw-p-5 tw-border tw-w-96 tw-shadow-lg tw-rounded-md tw-bg-white">
      <h3 class="tw-text-lg tw-font-bold tw-mb-4">新增臨時用戶</h3>
      <input 
        type="text" 
        v-model="name" 
        placeholder="請輸入用戶姓名" 
        class="tw-mt-1 tw-block tw-w-full tw-px-3 tw-py-2 tw-border tw-border-gray-300 tw-rounded-md tw-shadow-sm focus:tw-outline-none focus:tw-ring-indigo-500 focus:tw-border-indigo-500 sm:tw-text-sm"
        @keyup.enter="submit"
      />
      <div class="tw-mt-4 tw-flex tw-justify-end tw-space-x-2">
        <button 
          @click="close" 
          class="tw-px-4 tw-py-2 tw-bg-gray-300 tw-text-gray-800 tw-rounded-md hover:tw-bg-gray-400"
        >
          取消
        </button>
        <button 
          @click="submit" 
          :disabled="isAdding || !name.trim()"
          class="tw-px-4 tw-py-2 tw-bg-indigo-600 tw-text-white tw-rounded-md hover:tw-bg-indigo-700 disabled:tw-opacity-50 disabled:tw-cursor-not-allowed"
        >
          <span v-if="isAdding">新增中...</span>
          <span v-else>確定新增</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';

const props = defineProps({
  show: Boolean,
  isAdding: Boolean,
});

const emit = defineEmits(['close', 'submit']);

const name = ref('');

watch(() => props.show, (newVal) => {
  if (newVal) {
    name.value = ''; // Clear input when modal opens
  }
});

const close = () => emit('close');
const submit = () => {
  if (name.value.trim()) {
    emit('submit', name.value.trim());
  }
};
</script>