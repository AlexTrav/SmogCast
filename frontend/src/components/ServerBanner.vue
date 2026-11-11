<script setup lang="ts">
import { LoaderCircle, TriangleAlert } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import { useServerStatus } from '../composables/useServerStatus'

const { t } = useI18n()
const { status, wake } = useServerStatus()
</script>

<template>
  <!-- бесплатный Render засыпает через 15 минут без запросов – предупреждаем, что первый ответ займёт 1–2 минуты -->
  <Transition
    enter-from-class="opacity-0 -translate-y-2"
    leave-to-class="opacity-0 -translate-y-2"
    enter-active-class="transition duration-300"
    leave-active-class="transition duration-300"
  >
    <div
      v-if="status === 'waking' || status === 'down'"
      class="fixed inset-x-4 top-[4.5rem] z-40 mx-auto w-fit max-w-[calc(100%-2rem)] rounded-2xl border px-4 py-2.5 text-center text-sm shadow-lg backdrop-blur-md"
      :class="status === 'waking' ? 'border-accent/40 bg-accent-soft/95 text-ink' : 'border-aqi-unhealthy/40 bg-surface/95 text-aqi-unhealthy'"
      role="status"
    >
      <span v-if="status === 'waking'" class="inline-flex items-center gap-2">
        <LoaderCircle class="h-4 w-4 animate-spin" />
        {{ t('status.waking') }}
      </span>
      <span v-else class="inline-flex items-center gap-2">
        <TriangleAlert class="h-4 w-4" />
        {{ t('status.down') }}
        <button class="font-semibold underline underline-offset-2" @click="wake">{{ t('status.retry') }}</button>
      </span>
    </div>
  </Transition>
</template>
