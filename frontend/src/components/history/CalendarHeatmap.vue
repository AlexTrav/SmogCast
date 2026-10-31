<script setup lang="ts">
import { HeatmapChart } from 'echarts/charts'
import { CalendarComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { computed, onMounted, ref } from 'vue'
import VChart from 'vue-echarts'
import 'vue-echarts/style.css'
import { useI18n } from 'vue-i18n'
import { useTheme } from '../../composables/useTheme'
import type { AppLocale } from '../../types'
import { LEVELS } from '../../utils/aqi'
import { formatDate, formatNumber } from '../../utils/format'

use([HeatmapChart, CalendarComponent, TooltipComponent, VisualMapComponent, SVGRenderer])

// календарь за все годы, как у GitHub: клетка – сутки, цвет – уровень US AQI по среднему PM2.5 за сутки;
// щелчок по дню переносит машину времени на полдень этого дня
const props = defineProps<{ start: string; means: (number | null)[] }>()
const emit = defineEmits<{ select: [day: string] }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { theme } = useTheme()

const DAY = 86_400_000
const days = computed(() => {
  const t0 = Date.parse(`${props.start}T00:00:00Z`)
  return props.means.map((v, i) => [new Date(t0 + i * DAY).toISOString().slice(0, 10), v])
})
const years = computed(() => [...new Set(days.value.map(([d]) => (d as string).slice(0, 4)))])
const CELL = 20 // клетка – квадрат: «авто» ширина в ECharts схлопывается под высоту
// подписи месяцев: в ECharts встроены только английские и китайские
const MONTHS: Record<AppLocale, string[]> = {
  ru: ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'],
  kk: ['қаң', 'ақп', 'нау', 'сәу', 'мам', 'мау', 'шіл', 'там', 'қыр', 'қаз', 'қар', 'жел'],
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
}
const ROW = 7 * CELL + 34

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

const option = computed(() => {
  void theme.value
  const c = { ink: css('--ink'), faint: css('--faint'), line: css('--line'), surface: css('--surface'), bg: css('--surface-2') }
  const KEYS = ['--color-aqi-good', '--color-aqi-moderate', '--color-aqi-sensitive', '--color-aqi-unhealthy', '--color-aqi-very-unhealthy', '--color-aqi-hazardous']
  let low = 0
  const pieces = LEVELS.map((l, i) => {
    const piece = { gt: low, lte: Number.isFinite(l.upTo) ? l.upTo : 10_000, color: css(KEYS[i]), label: t(`levels.${l.key}`) }
    low = piece.lte
    return piece
  })
  pieces[0] = { ...pieces[0], gt: -1 }
  return {
    tooltip: {
      backgroundColor: c.surface,
      borderColor: c.line,
      textStyle: { color: c.ink, fontFamily: 'Onest Variable' },
      formatter: (p: { value: [string, number | null] }) =>
        `${formatDate(`${p.value[0]}T12:00:00Z`, lang.value)}<br/><b>${p.value[1] == null ? '–' : formatNumber(p.value[1], lang.value)}</b> ${t('hero.unit')}`,
    },
    visualMap: { type: 'piecewise', show: false, pieces, outOfRange: { color: c.bg } },
    calendar: years.value.map((y, i) => ({
      top: 26 + i * ROW,
      left: 64,
      range: y,
      cellSize: CELL,
      splitLine: { show: false },
      itemStyle: { color: c.bg, borderColor: c.surface, borderWidth: 2 },
      yearLabel: { show: true, position: 'left', color: c.faint, fontFamily: 'Onest Variable', fontSize: 14, margin: 36 },
      monthLabel: { color: c.faint, fontFamily: 'Onest Variable', nameMap: MONTHS[lang.value] },
      dayLabel: { show: false },
    })),
    series: years.value.map((y, i) => ({
      type: 'heatmap',
      coordinateSystem: 'calendar',
      calendarIndex: i,
      data: days.value.filter(([d]) => (d as string).startsWith(y)),
    })),
  }
})

const height = computed(() => `${26 + years.value.length * ROW}px`)

// на узком экране календарь прокручивается вбок – открываем его на последних месяцах
const scroller = ref<HTMLElement | null>(null)
onMounted(() => {
  if (scroller.value) scroller.value.scrollLeft = scroller.value.scrollWidth
})

function onClick(params: { value?: unknown }) {
  const value = params.value as [string, number | null] | undefined
  if (value) emit('select', value[0])
}
</script>

<template>
  <div ref="scroller" class="overflow-x-auto">
    <div class="min-w-[1140px]" :style="{ height }">
      <VChart :option="option" autoresize @click="onClick" />
    </div>
  </div>
</template>
