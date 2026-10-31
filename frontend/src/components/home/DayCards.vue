<script setup lang="ts">
import { CircleAlert, CircleCheck, CircleX } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSensitive } from '../../composables/useSensitive'
import type { AppLocale } from '../../types'
import { verdict } from '../../utils/advice'
import { LEVEL_COLOR } from '../../utils/aqi'
import { formatDay, formatHour, formatNumber } from '../../utils/format'
import type { DayOutlook } from '../../utils/outlook'
import { LEVEL_ICON } from '../levelIcons'
import TermHint from '../TermHint.vue'

// сегодня, завтра, послезавтра: какой будет день (уровень по среднему), разброс и когда хуже и лучше всего;
// нажатие на карточку показывает эти сутки в почасовой ленте
defineProps<{ days: DayOutlook[]; selected: number }>()
defineEmits<{ select: [offset: number] }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const NAMES = ['outlook.today', 'outlook.tomorrow', 'outlook.after']
const FEW = 4
// вывод на день по среднему уровню суток; при «У меня чувствительность» – строже на ступень
const { sensitive } = useSensitive()
const MARK = { ok: CircleCheck, caution: CircleAlert, no: CircleX }
const MARK_COLOR = { ok: 'text-aqi-good', caution: 'text-aqi-sensitive', no: 'text-aqi-unhealthy' }
</script>

<template>
  <ul class="grid gap-3 sm:grid-cols-3">
    <li v-for="d in days" :key="d.offset" class="relative">
      <!-- «?» вне кнопки карточки: вложенная кнопка в кнопке недопустима -->
      <span class="absolute top-3.5 right-3.5 z-10"><TermHint term="dayCard" /></span>
      <button
        v-ripple
        class="day-card group relative flex h-full w-full flex-col overflow-hidden rounded-2xl border bg-surface p-4 text-left transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 hover:shadow-lg"
        :class="selected === d.offset ? 'border-primary shadow-md' : 'border-line hover:border-faint'"
        :aria-pressed="selected === d.offset"
        @click="$emit('select', d.offset)"
      >
        <!-- полоса цвета уровня сверху: цвет дублируется значком и подписью -->
        <span class="absolute inset-x-0 top-0 h-1" :style="{ background: LEVEL_COLOR[d.level] }" />
        <span class="flex items-baseline gap-2 pr-7">
          <span class="font-semibold text-ink">{{ NAMES[d.offset] ? t(NAMES[d.offset]) : formatDay(d.date, lang) }}</span>
          <span v-if="NAMES[d.offset]" class="text-xs text-faint">{{ formatDay(d.date, lang) }}</span>
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
        <span class="mt-3 flex items-center gap-1.5 text-sm font-semibold text-ink">
          <component :is="MARK[verdict(d.level, sensitive)]" class="h-4 w-4 shrink-0" :class="MARK_COLOR[verdict(d.level, sensitive)]" aria-hidden="true" />
          {{ t(`tips.day_${verdict(d.level, sensitive)}`) }}
        </span>
        <span v-if="d.hours.length >= FEW" class="mt-2 space-y-0.5 text-sm">
          <span class="block text-ink">{{ t('outlook.peak', { time: formatHour(d.peak.time, lang) }) }}</span>
          <span class="block text-muted">{{ t('outlook.best', { time: formatHour(d.best.time, lang) }) }}</span>
        </span>
      </button>
    </li>
  </ul>
</template>
