<script setup lang="ts">
import { Info } from 'lucide-vue-next'
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import TimeMachine from '../components/history/TimeMachine.vue'
import type { DailyHistory, HourlyHistory } from '../types'
import { LEVEL_COLOR, LEVELS } from '../utils/aqi'
import { hourIndex, worstWindow } from '../utils/history'

// графики – отдельными чанками вместе с ECharts
const CalendarHeatmap = defineAsyncComponent(() => import('../components/history/CalendarHeatmap.vue'))
const SeriesChart = defineAsyncComponent(() => import('../components/history/SeriesChart.vue'))

const { t } = useI18n()
const hours = ref<HourlyHistory | null>(null)
const days = ref<DailyHistory | null>(null)
const selected = ref(0) // выбранный час – общий для машины времени, календаря и графика ряда

onMounted(async () => {
  const [h, d] = await Promise.allSettled([api.allHours(), api.days()])
  if (h.status === 'fulfilled') {
    hours.value = h.value
    selected.value = h.value.values.pm2_5.length - 1 // начинаем с последнего часа
  }
  if (d.status === 'fulfilled') days.value = d.value
})

const pm = computed(() => hours.value?.values.pm2_5 ?? [])
const means = computed(() => days.value?.values.pm2_5.mean ?? [])

// худшая неделя смога за всё время – в часах ряда (от полуночи первого дня до конца последнего, по Алматы)
const episode = computed(() => {
  const window = worstWindow(means.value, 7)
  if (!window || !hours.value?.start || !days.value?.start) return null
  const first = new Date(`${days.value.start}T00:00:00Z`)
  const dayStart = (i: number) => new Date(first.getTime() + i * 86_400_000)
  // полночь по Алматы раньше полуночи UTC на 5–6 ч: берём полдень дня и отступаем на 12 ч – погрешность в час не важна
  const from = hourIndex(hours.value.start, new Date(dayStart(window.from).getTime() - 6 * 3_600_000))
  const to = hourIndex(hours.value.start, new Date(dayStart(window.to + 1).getTime() - 6 * 3_600_000)) - 1
  return { from: Math.max(0, from), to: Math.min(pm.value.length - 1, to) }
})

// день из календаря – полдень этого дня по Алматы
function selectDay(day: string) {
  if (!hours.value?.start) return
  selected.value = Math.min(pm.value.length - 1, Math.max(0, hourIndex(hours.value.start, `${day}T07:00:00Z`)))
}
</script>

<template>
  <div class="mx-auto max-w-7xl px-4 pt-28 sm:px-6">
    <p class="eyebrow animate-rise">{{ t('history.eyebrow') }}</p>
    <h1 class="animate-rise mt-3 max-w-3xl text-4xl font-bold tracking-tight text-ink sm:text-5xl" style="animation-delay: 60ms">
      {{ t('history.title') }}
    </h1>
    <p class="animate-rise mt-4 max-w-3xl text-lg leading-relaxed text-muted" style="animation-delay: 120ms">{{ t('history.intro') }}</p>

    <section class="mt-10">
      <TimeMachine v-if="hours?.start" v-model="selected" :start="hours.start" :values="pm" :episode="episode" />
      <div v-else class="h-80 skeleton rounded-3xl bg-surface-2" />
    </section>

    <section v-reveal class="card mt-8 p-5 sm:p-7">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('history.calendar') }}</h2>
      <p class="mt-1 text-sm text-muted">{{ t('history.calendarText') }}</p>
      <ul class="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted">
        <li v-for="l in LEVELS" :key="l.key" class="flex items-center gap-2">
          <span class="h-3 w-3 rounded-sm" :style="{ background: LEVEL_COLOR[l.key] }" />{{ t(`levels.${l.key}`) }}
        </li>
      </ul>
      <div class="mt-4">
        <CalendarHeatmap v-if="days?.start" :start="days.start" :means="means" @select="selectDay" />
        <div v-else class="h-[600px] skeleton rounded-2xl bg-surface-2" />
      </div>
    </section>

    <section v-reveal class="card mt-8 p-5 sm:p-7">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('history.series') }}</h2>
      <p class="mt-1 text-sm text-muted">{{ t('history.seriesText') }}</p>
      <div class="mt-4">
        <SeriesChart v-if="hours?.start" :start="hours.start" :values="pm" :selected="selected" @select="(i) => (selected = i)" />
        <div v-else class="h-96 skeleton rounded-2xl bg-surface-2" />
      </div>
      <p class="mt-4 flex gap-2 text-sm text-faint">
        <Info class="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        {{ t('history.cycles') }}
      </p>
    </section>
  </div>
</template>
