<script setup lang="ts">
import { useTimeoutFn } from '@vueuse/core'
import { Sparkles } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useLive } from '../composables/useLive'
import type { AppLocale } from '../types'
import { formatHour } from '../utils/format'

// уведомление «Новые данные за ЧЧ:00»: ежечасная задача дописала новый час ряда, страница уже обновилась
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { freshHour } = useLive()
const visible = ref(false)
const { start } = useTimeoutFn(() => (visible.value = false), 7000, { immediate: false })

watch(freshHour, (hour) => {
  if (!hour) return
  visible.value = true
  start()
})
</script>

<template>
  <div class="pointer-events-none fixed inset-x-4 bottom-20 z-50 flex justify-center md:inset-x-auto md:right-6 md:bottom-6" aria-live="polite">
    <Transition
      enter-from-class="opacity-0 translate-y-3"
      leave-to-class="opacity-0 translate-y-3"
      enter-active-class="transition duration-300"
      leave-active-class="transition duration-300"
    >
      <p
        v-if="visible && freshHour"
        class="pointer-events-auto flex items-center gap-2 rounded-2xl border border-line bg-surface px-4 py-3 text-sm font-medium text-ink shadow-xl"
      >
        <Sparkles class="h-4 w-4 text-accent" aria-hidden="true" />
        {{ t('forecast.fresh', { time: formatHour(freshHour, lang) }) }}
      </p>
    </Transition>
  </div>
</template>
