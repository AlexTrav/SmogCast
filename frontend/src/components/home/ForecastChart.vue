<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { GridComponent, MarkAreaComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'
import 'vue-echarts/style.css' // в vue-echarts 8 размеры контейнера графика задаёт его CSS
import { useI18n } from 'vue-i18n'
import { useTheme } from '../../composables/useTheme'
import type { AppLocale, Forecast } from '../../types'
import { LEVELS, WHO_24H, levelOf } from '../../utils/aqi'
import { formatDateHour, formatDay, formatHour, formatNumber, localHour } from '../../utils/format'
import { MODEL_VAR } from '../../utils/models'

use([LineChart, GridComponent, TooltipComponent, MarkLineComponent, MarkAreaComponent, SVGRenderer])

// прогноз на hours часов вперёд: факт за последние сутки, линия каждой выбранной модели, фон – полосы уровней
// AQI; веер интервалов (только для одной модели) и прогноз CAMS – по переключателям
const props = defineProps<{
  forecasts: Forecast[]
  actual: { start: string; values: (number | null)[] }
  hours: number
  band: boolean
  cams: boolean
}>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { theme } = useTheme()

const HOUR = 3_600_000
// ось времени – в часах Алматы (UTC+5 с марта 2024): ECharts ставит деления по UTC, поэтому точки сдвинуты
// на пояс, и деления приходятся на 00, 06, 12, 18 (на сутках – каждые 3 ч) по местному времени
const OFFSET = 5 * HOUR
const PAST = 24 // часов факта перед прогнозом
const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

function times(start: string, n: number, from = 0): number[] {
  const t0 = new Date(start).getTime() + OFFSET
  return Array.from({ length: n }, (_, i) => t0 + (from + i) * HOUR)
}

// полосы уровней на фоне: цвет уровня очень бледно, подпись уровня – у правого края
const LEVEL_VAR: Record<string, string> = {
  good: '--color-aqi-good',
  moderate: '--color-aqi-moderate',
  sensitive: '--color-aqi-sensitive',
  unhealthy: '--color-aqi-unhealthy',
  very_unhealthy: '--color-aqi-very-unhealthy',
  hazardous: '--color-aqi-hazardous',
}

const option = computed(() => {
  void theme.value // цвета берутся из CSS-переменных темы – пересчитываем при смене темы
  const dark = theme.value === 'dark'
  const c = { ink: css('--ink'), muted: css('--muted'), faint: css('--faint'), grid: css('--grid'), axis: css('--axis'), surface: css('--surface') }
  const list = props.forecasts
  const lead = list[0]
  const n = Math.min(props.hours, lead.pred.length)
  const single = list.length === 1
  const fx = times(lead.start, n)
  const cut = <T,>(values: T[]) => values.slice(0, n)
  const past = Math.min(PAST, props.actual.values.length)
  const ax = times(props.actual.start, past, props.actual.values.length - past)
  const av = props.actual.values.slice(-past)
  const now = new Date(lead.issued_at).getTime() + OFFSET
  const lastActual = av.at(-1) ?? null
  const step = (n <= 24 ? 3 : 6) * HOUR
  const xmin = Math.floor(Math.min(ax[0] ?? fx[0], fx[0]) / step) * step
  const xmax = Math.ceil(fx[n - 1] / step) * step
  const pair = (xs: number[], ys: (number | null)[]) => xs.map((x, i) => [x, ys[i]])

  // верх оси – по видимым значениям, чтобы на приближении линия не прижималась к низу
  const visible = [
    ...av, ...list.flatMap((f) => cut(f.pred)),
    ...(props.band && single ? cut(lead.hi95) : []), ...(props.cams ? cut(lead.cams) : []),
  ].filter((v): v is number => v != null)
  const ymax = Math.max(20, Math.ceil((Math.max(...visible) * 1.12) / 10) * 10)
  // на узком экране подписи уровней налезают на линии – остаются только цветные полосы (уровень – в подсказке)
  const wide = window.innerWidth >= 640
  let low = 0
  const bands = LEVELS.flatMap((l) => {
    const high = Number.isFinite(l.upTo) ? l.upTo : 500
    const from = low
    low = high
    if (from >= ymax) return []
    return [[
      {
        yAxis: from, itemStyle: { color: css(LEVEL_VAR[l.key]), opacity: dark ? 0.1 : 0.12 },
        label: { show: wide, position: 'insideTopRight', color: c.faint, fontSize: 10, formatter: t(`levels.${l.key}`) },
      },
      { yAxis: Math.min(high, ymax) },
    ]]
  })

  const band = (name: string, color: string, lo: number[], hi: number[], opacity: number) => [
    { id: `${name}-lo`, name: `${name}-lo`, type: 'line', data: pair(fx, cut(lo)), stack: name, lineStyle: { opacity: 0 }, symbol: 'none', silent: true },
    {
      id: name, name, type: 'line', data: pair(fx, cut(hi).map((h, i) => h - lo[i])), stack: name, lineStyle: { opacity: 0 },
      symbol: 'none', areaStyle: { color, opacity }, silent: true,
    },
  ]
  const leadColor = css(MODEL_VAR[lead.model] ?? '--series-1')

  return {
    // первая прорисовка – линии «рисуются» слева направо; смена горизонта и моделей перетекает плавно
    animation: !still,
    animationDuration: 1100,
    animationEasing: 'cubicOut' as const,
    animationDurationUpdate: 600,
    grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: c.surface,
      borderColor: c.axis,
      textStyle: { color: c.ink, fontFamily: 'Onest Variable' },
      axisPointer: { type: 'line', lineStyle: { color: c.faint } },
      // подсказка словами: «Смесь: около 31 мкг/м³ – Умеренно»
      formatter: (items: { seriesId: string; value: [number, number | null] }[]) => {
        const x = items[0]?.value[0]
        const i = fx.indexOf(x)
        const row = (label: string, v: number | null | undefined, words = true) =>
          v == null ? '' : `<div style="display:flex;justify-content:space-between;gap:16px"><span>${label}</span><span><b>${formatNumber(v, lang.value, 0)}</b>${words ? ` · ${t(`levels.${levelOf(v)}`)}` : ''}</span></div>`
        const by = (id: string) => items.find((it) => it.seriesId === id)?.value[1]
        const models = i < 0 ? '' : list.map((f) => row(t(`modelNames.${f.model}`), f.pred[i])).join('')
        const interval = i >= 0 && props.band && single
          ? `<div style="font-size:12px;opacity:.75">${t('forecast.tipBand', { lo: formatNumber(lead.lo80[i], lang.value, 0), hi: formatNumber(lead.hi80[i], lang.value, 0) })}</div>`
          : ''
        return `<div style="font-size:12px;opacity:.7;margin-bottom:4px">${formatDateHour(new Date(x - OFFSET), lang.value)} · ${t('forecast.unit')}</div>`
          + row(t('forecast.actual'), by('actual')) + models + interval
          + (props.cams && i >= 0 ? row(t('forecast.cams'), lead.cams[i], false) : '')
      },
    },
    xAxis: {
      type: 'value',
      min: xmin,
      max: xmax,
      interval: step,
      axisLine: { lineStyle: { color: c.axis } },
      axisTick: { show: false },
      axisLabel: {
        color: c.faint,
        hideOverlap: true,
        // в полночь под часом – дата: отдельная подпись даты пропадала бы при защите от наложения
        formatter: (v: number) => {
          const d = new Date(v - OFFSET)
          return localHour(d) === 0 ? `${formatHour(d, lang.value)}
${formatDay(d, lang.value)}` : formatHour(d, lang.value)
        },
      },
      splitLine: { show: true, lineStyle: { color: c.grid, type: 'dotted' } },
    },
    yAxis: { type: 'value', min: 0, max: ymax, axisLabel: { color: c.faint }, splitLine: { lineStyle: { color: c.grid } } },
    series: [
      ...(props.band && single ? [...band('b95', leadColor, lead.lo95, lead.hi95, 0.12), ...band('b80', leadColor, lead.lo80, lead.hi80, 0.22)] : []),
      {
        id: 'actual', name: 'actual', type: 'line', data: pair(ax, av), symbol: 'none', smooth: 0.3,
        lineStyle: { color: c.ink, width: 2 },
        markArea: { silent: true, data: bands },
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
      ...(props.cams ? [{ id: 'cams', name: 'cams', type: 'line', data: pair(fx, cut(lead.cams)), symbol: 'none', smooth: 0.3, lineStyle: { color: c.muted, width: 1.5, type: 'dashed' } }] : []),
      // линия каждой модели продолжает факт от последнего известного часа – без разрыва
      ...list.map((f, k) => ({
        id: `m:${f.model}`, name: f.model, type: 'line', symbol: 'none', smooth: 0.3, z: 3 + (list.length - k),
        data: [...(lastActual == null ? [] : [[now, lastActual]]), ...pair(fx, cut(f.pred))],
        lineStyle: { color: css(MODEL_VAR[f.model] ?? '--faint'), width: k === 0 ? 2.5 : 2 },
      })),
    ],
  }
})
</script>

<template>
  <!-- высота – у обёртки: CSS vue-echarts растягивает график на 100 % родителя; replaceMerge – серии с теми же id
       плавно перетекают при смене горизонта и моделей, лишние убираются -->
  <div class="h-80 w-full sm:h-96 lg:h-[30rem]">
    <VChart :option="option" :update-options="{ replaceMerge: ['series'] }" autoresize />
  </div>
</template>
