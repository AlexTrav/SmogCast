<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, MarkLineComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { computed, shallowRef, watch } from 'vue'
import VChart from 'vue-echarts'
import 'vue-echarts/style.css'
import { useI18n } from 'vue-i18n'
import { useTheme } from '../../composables/useTheme'
import type { AppLocale } from '../../types'
import { WHO_24H } from '../../utils/aqi'
import { formatDate, formatHour, formatNumber, formatShortDate } from '../../utils/format'

use([LineChart, GridComponent, TooltipComponent, MarkLineComponent, DataZoomComponent, CanvasRenderer])

// весь почасовой ряд с 01.09.2022 (36 тыс. точек – canvas и прореживание LTTB): масштаб колесом и ползунком,
// щелчок по графику переносит машину времени на этот час, линия – выбранный час
const props = defineProps<{ start: string; values: (number | null)[]; selected: number }>()
const emit = defineEmits<{ select: [index: number] }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { theme } = useTheme()
const chart = shallowRef<InstanceType<typeof VChart> | null>(null)

const HOUR = 3_600_000
const t0 = computed(() => new Date(props.start).getTime())
const data = computed(() => props.values.map((v, i) => [t0.value + i * HOUR, v]))

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

// линии выбранного часа и нормы ВОЗ; при движении ползунка обновляются только они, а не весь ряд
// выбранный час – обычной переменной, а не реактивно: иначе каждый шаг ползунка пересобирал бы весь график
let current = props.selected
function markers(accent = css('--accent'), faint = css('--faint')) {
  return [
    { xAxis: t0.value + current * HOUR, lineStyle: { color: accent, width: 2, type: 'solid' } },
    { yAxis: WHO_24H, lineStyle: { color: faint, type: 'dashed', width: 1 } },
  ]
}

watch(
  () => props.selected,
  (value) => {
    current = value
    chart.value?.chart?.setOption({ series: [{ markLine: { data: markers() } }] })
  },
)

const option = computed(() => {
  void theme.value
  const c = { series: css('--series-1'), ink: css('--ink'), faint: css('--faint'), grid: css('--grid'), axis: css('--axis'), surface: css('--surface'), accent: css('--accent') }
  return {
    animation: false,
    grid: { left: 8, right: 16, top: 16, bottom: 64, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: c.surface,
      borderColor: c.axis,
      textStyle: { color: c.ink, fontFamily: 'Onest Variable' },
      formatter: (items: { value: [number, number | null] }[]) => {
        const [x, v] = items[0].value
        return `<div style="font-size:12px;opacity:.7">${formatDate(new Date(x), lang.value)}, ${formatHour(new Date(x), lang.value)}</div><b>${v == null ? '–' : formatNumber(v, lang.value)}</b> ${t('hero.unit')}`
      },
    },
    xAxis: {
      type: 'time',
      axisLine: { lineStyle: { color: c.axis } },
      axisLabel: { color: c.faint, hideOverlap: true, formatter: (v: number) => formatShortDate(new Date(v)) },
      splitLine: { show: false },
    },
    yAxis: { type: 'value', min: 0, axisLabel: { color: c.faint }, splitLine: { lineStyle: { color: c.grid } } },
    dataZoom: [
      { type: 'inside', minValueSpan: 24 * HOUR },
      { type: 'slider', height: 28, bottom: 12, borderColor: c.axis, fillerColor: `${c.series}22`, textStyle: { color: c.faint }, labelFormatter: (v: number) => formatShortDate(new Date(v)) },
    ],
    series: [
      {
        type: 'line',
        data: data.value,
        showSymbol: false,
        sampling: 'lttb',
        lineStyle: { color: c.series, width: 1.2 },
        areaStyle: { color: c.series, opacity: 0.08 },
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          data: markers(c.accent, c.faint),
        },
      },
    ],
  }
})

// щелчок в любом месте графика – ближайший час
function onClick(event: { offsetX: number; offsetY: number }) {
  const instance = chart.value?.chart
  if (!instance) return
  const [x] = instance.convertFromPixel({ seriesIndex: 0 }, [event.offsetX, event.offsetY]) as number[]
  const index = Math.round((x - t0.value) / HOUR)
  if (index >= 0 && index < props.values.length) emit('select', index)
}
</script>

<template>
  <div class="h-80 w-full sm:h-96">
    <VChart ref="chart" :option="option" autoresize @zr:click="onClick" />
  </div>
</template>
