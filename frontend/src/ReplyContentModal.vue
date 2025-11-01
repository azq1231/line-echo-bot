<template>
  <div v-if="show" class="tw-fixed tw-inset-0 tw-bg-gray-600 tw-bg-opacity-50 tw-overflow-y-auto tw-h-full tw-w-full tw-z-50 tw-flex tw-justify-center tw-items-center" @click.self="close">
    <div class="tw-relative tw-p-5 tw-border tw-w-full sm:tw-w-96 tw-shadow-lg tw-rounded-md tw-bg-white">
      <h3 class="tw-text-lg tw-font-bold tw-mb-4">用戶回覆內容</h3>
      <div class="tw-bg-gray-100 tw-p-3 tw-rounded-md tw-mb-4 tw-min-h-[60px]">
        <p class="tw-text-sm tw-text-gray-500">類型: <span class="tw-font-semibold tw-text-gray-800">{{ type }}</span></p>
        <p class="tw-text-sm tw-text-gray-500 tw-mt-1">內容:</p>
        <p class="tw-text-base tw-text-gray-800 tw-break-words">{{ content }}</p>
      </div>
      <div class="tw-mt-4 tw-flex tw-justify-end tw-space-x-2">
        <button 
          @click="close" 
          class="tw-px-4 tw-py-2 tw-bg-gray-300 tw-text-gray-800 tw-rounded-md hover:tw-bg-gray-400"
        >
          關閉
        </button>
        <button 
          v-if="!isConfirmed"
          @click="emit('confirm')" 
          class="tw-px-4 tw-py-2 tw-bg-green-600 tw-text-white tw-rounded-md hover:tw-bg-green-700"
        >
          ✅ 確認回覆
        </button>
        <button 
          v-else
          @click="emit('reset-status')" 
          class="tw-px-4 tw-py-2 tw-bg-red-600 tw-text-white tw-rounded-md hover:tw-bg-red-700"
        >
          🔄 標示為未回覆
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  show: Boolean,
  type: String,
  content: String,
  isConfirmed: Boolean,
});

const emit = defineEmits(['close', 'confirm', 'reset-status']);

const close = () => emit('close');
</script>