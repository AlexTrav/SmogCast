<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AppLocale } from '../../types'
import { LEVEL_COLOR } from '../../utils/aqi'
import { formatDay, formatHour, formatNumber } from '../../utils/format'
import type { DayOutlook } from '../../utils/outlook'
import { LEVEL_ICON } from '../levelIcons'

// сегодня, завтра, послезавтра: какой будет день (уровень по среднему), разброс и когда хуже и лучше всего;
// нажатие на карточку показывает эти сутки в почасовой ленте
defineProps<{ days: DayOutlook[]; selected: number }>()
defineEmits<{ select: [offset: number] }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const NAMES = ['outlook.today', 'outlook.tomorrow', 'outlook.after']
const FEW = 4
</script>

<template>
  <ul class="grid gap-3 sm:grid-cols-3">
    <li v-for="d in days" :key="d.offset">
      <button
        v-ripple
        class="day-card group relative flex h-full w-full flex-col overflow-hidden rounded-2xl border bg-surface p-4 text-left transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 hover:shadow-lg"
        :class="selected === d.offset ? 'border-primary shadow-md' : 'border-line hover:border-faint'"
        :aria-pressed="selected === d.offset"
        @click="$emit('select', d.offset)"
      >
        <!-- полоса цвета уровня сверху: цвет дублируется значком и подписью -->
        <span class="absolute inset-x-0 top-0 h-1" :style="{ background: LEVEL_COLOR[d.level] }" />
        <span class="flex items-baseline justify-between gap-2">
          <span class="font-semibold text-ink">{{ t(NAMES[d.offset]) }}</span>
          <span class="text-xs text-faint">{{ formatDay(d.date, lang) }}</span>
        </span>
        <span class="mt-3 flex items-center gap-2.5">
          <span
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-ink"
            :style="{ background: `color-mix(in srgb, ${LEVEL_COLOR[d.level]} 28%, transparent)` }"
          >
            <component :is="LEVEL_ICON[d.level]" class="h-5 w-5" aria-hidden="true" />
          </span>
          <span class="text-lg leading-tight font-bold text-ink">{{ t(`levels.${d.level}`) }}</span>
        </span>
        <!-- от суток осталось несколько часов – разброс и «хуже/лучше всего» не имеют смысла -->
        <span v-if="d.hours.length < FEW" class="num mt-3 text-sm text-muted">
          {{ t('outlook.rest', { value: formatNumber(d.hours.reduce((a, h) => a + h.pm, 0) / d.hours.length, lang, 0) }) }}
        </span>
        <span v-else class="num mt-3 text-sm text-muted">
          {{ t('outlook.range', { min: formatNumber(d.min, lang, 0), max: formatNumber(d.max, lang, 0) }) }}
        </span>
        <span v-if="d.hours.length >= FEW" class="mt-2 space-y-0.5 text-sm">
          <span class="block text-ink">{{ t('outlook.peak', { time: formatHour(d.peak.time, lang) }) }}</span>
          <span class="block text-muted">{{ t('outlook.best', { time: formatHour(d.best.time, lang) }) }}</span>
        </span>
      </button>
    </li>
  </ul>
</template>
