<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AppLocale } from '../../types'
import { LEVEL_COLOR, LEVELS, levelOf } from '../../utils/aqi'
import { formatNumber } from '../../utils/format'

// шкала уровней US AQI: шесть отрезков равной ширины с порогами EPA и отметка текущего PM2.5
const props = defineProps<{ pm: number }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const current = computed(() => levelOf(props.pm))

// положение отметки: внутри своего отрезка – пропорционально концентрации
const marker = computed(() => {
  let low = 0
  for (const [i, l] of LEVELS.entries()) {
    const high = Number.isFinite(l.upTo) ? l.upTo : 500
    if (props.pm <= high || i === LEVELS.length - 1) {
      const inside = Math.min(1, Math.max(0, (props.pm - low) / (high - low)))
      return ((i + inside) / LEVELS.length) * 100
    }
    low = high
  }
  return 100
})
</script>

<template>
  <div>
    <div class="relative pt-6">
      <span
        class="absolute top-0 -translate-x-1/2 rounded-full bg-ink px-2 py-0.5 text-xs font-semibold text-bg num"
        :style="{ left: `${marker}%` }"
      >
        {{ formatNumber(pm, lang) }}
      </span>
      <span class="absolute top-5 h-4 w-0.5 -translate-x-1/2 bg-ink" :style="{ left: `${marker}%` }" />
      <div class="flex h-3 gap-0.5 overflow-hidden rounded-full">
        <span v-for="l in LEVELS" :key="l.key" class="flex-1" :style="{ background: LEVEL_COLOR[l.key] }" />
      </div>
    </div>
    <ul class="mt-4 space-y-1.5 text-sm">
      <li v-for="l in LEVELS" :key="l.key" class="flex items-center gap-2 text-muted">
        <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ background: LEVEL_COLOR[l.key] }" />
        <span :class="l.key === current ? 'font-semibold text-ink' : ''">{{ t(`levels.${l.key}`) }}</span>
        <span class="num ml-auto text-xs text-faint">{{ Number.isFinite(l.upTo) ? `≤${formatNumber(l.upTo, lang)}` : '' }}</span>
      </li>
    </ul>
  </div>
</template>
