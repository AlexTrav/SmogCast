<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'
import 'vue-echarts/style.css'
import { useI18n } from 'vue-i18n'
import { useTheme } from '../../composables/useTheme'
import type { AppLocale, Verify } from '../../types'
import { formatDateHour, formatHour, formatNumber } from '../../utils/format'

use([LineChart, GridComponent, TooltipComponent, SVGRenderer])

// прогноз смеси, выпущенный сутки назад: интервал 80 %, линия прогноза и факт там, где он уже наступил
const props = defineProps<{ data: NonNullable<Verify['yesterday']> }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { theme } = useTheme()

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

const option = computed(() => {
  void theme.value
  const c = { series: css('--series-1'), ink: css('--ink'), faint: css('--faint'), grid: css('--grid'), axis: css('--axis'), surface: css('--surface') }
  const t0 = new Date(props.data.start).getTime()
  const x = props.data.pred.map((_, i) => t0 + i * 3_600_000)
  const pair = (ys: (number | null)[]) => x.map((v, i) => [v, ys[i]])
  return {
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: c.surface,
      borderColor: c.axis,
      textStyle: { color: c.ink, fontFamily: 'Onest Variable' },
      formatter: (items: { seriesName: string; value: [number, number | null] }[]) => {
        const by = (n: string) => items.find((i) => i.seriesName === n)?.value[1]
        const row = (label: string, v: number | null | undefined) => (v == null ? '' : `<div>${label}: <b>${formatNumber(v, lang.value)}</b></div>`)
        return `<div style="font-size:12px;opacity:.7">${formatDateHour(new Date(items[0].value[0]), lang.value)}</div>${row(t('forecast.pred'), by('pred'))}${row(t('forecast.actual'), by('actual'))}`
      },
    },
    xAxis: { type: 'time', axisLine: { lineStyle: { color: c.axis } }, axisLabel: { color: c.faint, hideOverlap: true, formatter: (v: number) => formatHour(new Date(v), lang.value) }, splitLine: { show: false } },
    yAxis: { type: 'value', min: 0, axisLabel: { color: c.faint }, splitLine: { lineStyle: { color: c.grid } } },
    series: [
      { name: 'lo', type: 'line', data: pair(props.data.lo80), stack: 'band', lineStyle: { opacity: 0 }, symbol: 'none', silent: true },
      { name: 'band', type: 'line', data: pair(props.data.hi80.map((h, i) => h - props.data.lo80[i])), stack: 'band', lineStyle: { opacity: 0 }, symbol: 'none', areaStyle: { color: c.series, opacity: 0.18 }, silent: true },
      { name: 'pred', type: 'line', data: pair(props.data.pred), symbol: 'none', smooth: 0.3, lineStyle: { color: c.series, width: 2.5 } },
      { name: 'actual', type: 'line', data: pair(props.data.actual), symbol: 'none', smooth: 0.3, lineStyle: { color: c.ink, width: 2 } },
    ],
  }
})
</script>

<template>
  <div class="h-72 w-full">
    <VChart :option="option" autoresize />
  </div>
</template>
