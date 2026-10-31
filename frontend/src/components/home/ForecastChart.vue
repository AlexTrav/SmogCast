<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { GridComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'
import 'vue-echarts/style.css' // в vue-echarts 8 размеры контейнера графика задаёт его CSS
import { useI18n } from 'vue-i18n'
import { useTheme } from '../../composables/useTheme'
import type { AppLocale, Forecast } from '../../types'
import { WHO_24H } from '../../utils/aqi'
import { formatDateHour, formatDay, formatHour, formatNumber, localHour } from '../../utils/format'
import { MODEL_VAR } from '../../utils/models'

use([LineChart, GridComponent, TooltipComponent, MarkLineComponent, SVGRenderer])

// прогноз на 72 ч: веер интервалов 95 % и 80 %, линия прогноза, факт за двое суток до него и прогноз CAMS
const props = defineProps<{ forecast: Forecast; actual: { start: string; values: (number | null)[] } }>()
const seriesVar = computed(() => MODEL_VAR[props.forecast.model] ?? '--series-1')
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { theme } = useTheme()

const HOUR = 3_600_000
// ось времени – в часах Алматы (UTC+5 с марта 2024): ECharts ставит деления по UTC, поэтому точки сдвинуты
// на пояс, и деления каждые 6 ч приходятся на 00, 06, 12, 18 по местному времени
const OFFSET = 5 * HOUR
const STEP = 6 * HOUR

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function times(start: string, n: number): number[] {
  const t0 = new Date(start).getTime() + OFFSET
  return Array.from({ length: n }, (_, i) => t0 + i * HOUR)
}

const option = computed(() => {
  void theme.value // цвета берутся из CSS-переменных темы – пересчитываем при смене темы
  const c = {
    series: css(seriesVar.value),
    ink: css('--ink'),
    muted: css('--muted'),
    faint: css('--faint'),
    grid: css('--grid'),
    axis: css('--axis'),
    surface: css('--surface'),
    accent: css('--accent'),
  }
  const f = props.forecast
  const fx = times(f.start, f.pred.length)
  const ax = times(props.actual.start, props.actual.values.length)
  const now = new Date(f.issued_at).getTime() + OFFSET
  const lastActual = props.actual.values.at(-1) ?? null
  const xmin = Math.floor(Math.min(ax[0] ?? fx[0], fx[0]) / STEP) * STEP
  const xmax = Math.ceil(fx[fx.length - 1] / STEP) * STEP
  const pair = (xs: number[], ys: (number | null)[]) => xs.map((x, i) => [x, ys[i]])
  const diff = (hi: number[], lo: number[]) => hi.map((h, i) => h - lo[i])
  const band = (name: string, lo: number[], hi: number[], opacity: number) => [
    { name: `${name}-lo`, type: 'line', data: pair(fx, lo), stack: name, lineStyle: { opacity: 0 }, symbol: 'none', silent: true },
    {
      name, type: 'line', data: pair(fx, diff(hi, lo)), stack: name, lineStyle: { opacity: 0 }, symbol: 'none',
      areaStyle: { color: c.series, opacity }, silent: true,
    },
  ]
  return {
    animationDuration: 900,
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: c.surface,
      borderColor: c.axis,
      textStyle: { color: c.ink, fontFamily: 'Onest Variable' },
      axisPointer: { type: 'line', lineStyle: { color: c.faint } },
      formatter: (items: { seriesName: string; value: [number, number | null] }[]) => {
        const x = items[0]?.value[0]
        const row = (label: string, v: number | null | undefined) =>
          v == null ? '' : `<div style="display:flex;justify-content:space-between;gap:16px"><span>${label}</span><b>${formatNumber(v, lang.value)}</b></div>`
        const by = (name: string) => items.find((i) => i.seriesName === name)?.value[1]
        const i = fx.indexOf(x)
        const interval = i >= 0 ? `${formatNumber(f.lo80[i], lang.value)}–${formatNumber(f.hi80[i], lang.value)}` : ''
        return `<div style="font-size:12px;opacity:.7;margin-bottom:4px">${formatDateHour(new Date(x - OFFSET), lang.value)}</div>`
          + row(t('forecast.actual'), by('actual'))
          + row(t('forecast.pred'), by('pred'))
          + (interval ? `<div style="display:flex;justify-content:space-between;gap:16px"><span>${t('forecast.band80')}</span><b>${interval}</b></div>` : '')
          + row(t('forecast.cams'), by('cams'))
      },
    },
    xAxis: {
      type: 'value',
      min: xmin,
      max: xmax,
      interval: STEP,
      axisLine: { lineStyle: { color: c.axis } },
      axisTick: { show: false },
      axisLabel: {
        color: c.faint,
        hideOverlap: true,
        // в полночь – дата, в остальные деления – час
        formatter: (v: number) => {
          const d = new Date(v - OFFSET)
          return localHour(d) === 0 ? formatDay(d, lang.value) : formatHour(d, lang.value)
        },
      },
      splitLine: { show: true, lineStyle: { color: c.grid, type: 'dotted' } },
    },
    yAxis: {
      type: 'value',
      min: 0,
      axisLabel: { color: c.faint },
      splitLine: { lineStyle: { color: c.grid } },
    },
    series: [
      ...band('b95', f.lo95, f.hi95, 0.12),
      ...band('b80', f.lo80, f.hi80, 0.22),
      {
        name: 'actual', type: 'line', data: pair(ax, props.actual.values), symbol: 'none', smooth: 0.3,
        lineStyle: { color: c.ink, width: 2 },
        markLine: {
          silent: true, symbol: 'none',
          lineStyle: { color: c.faint, type: 'dashed', width: 1 },
          label: { color: c.muted, formatter: '{b}' },
          data: [
            { name: t('forecast.now'), xAxis: now, label: { position: 'insideEndTop' } },
            { name: t('forecast.whoLine'), yAxis: WHO_24H, label: { position: 'insideStartTop' } },
          ],
        },
      },
      { name: 'cams', type: 'line', data: pair(fx, f.cams), symbol: 'none', smooth: 0.3, lineStyle: { color: c.muted, width: 1.5, type: 'dashed' } },
      // линия прогноза продолжает факт от последнего известного часа – без разрыва
      { name: 'pred', type: 'line', data: [...(lastActual == null ? [] : [[now, lastActual]]), ...pair(fx, f.pred)], symbol: 'none', smooth: 0.3, lineStyle: { color: c.series, width: 2.5 } },
    ],
  }
})
</script>

<template>
  <!-- высота – у обёртки: CSS vue-echarts растягивает график на 100 % родителя -->
  <div class="h-80 w-full sm:h-96 lg:h-[30rem]">
    <VChart :option="option" autoresize />
  </div>
</template>
