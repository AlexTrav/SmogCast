<script setup lang="ts">
import { BarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'
import 'vue-echarts/style.css'
import { useI18n } from 'vue-i18n'
import { useTheme } from '../../composables/useTheme'
import type { AppLocale, Performance } from '../../types'
import { formatHour, formatNumber } from '../../utils/format'
import { MODEL_VAR } from '../../utils/models'

use([BarChart, GridComponent, LegendComponent, TooltipComponent, SVGRenderer])

// ежечасные запуски: столбик – один час, сегменты – сбор данных и время каждой модели (секунды);
// модели быстрее секунды (LSTM, базовые) в сумме почти не видны – это и есть результат
const props = defineProps<{ perf: Performance }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { theme } = useTheme()

const MODELS = ['arima', 'prophet', 'lstm', 'lstm_weather', 'profile_7d', 'seasonal_24']

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

const option = computed(() => {
  void theme.value
  const c = { ink: css('--ink'), muted: css('--muted'), faint: css('--faint'), grid: css('--grid'), axis: css('--axis'), surface: css('--surface') }
  // столбик – запуск моделей, подпись – время запуска (вручную в один час можно запустить несколько раз);
  // сбор данных того же запуска – по часу начала
  const hours = props.perf.model_runs.map((r) => r.at)
  const dataBy = new Map(props.perf.data_runs.map((r) => [r.at.slice(0, 13), r.duration_ms]))
  const seconds = (ms: number | undefined) => (ms == null ? 0 : ms / 1000)
  const series = [
    {
      name: t('perf.collect'),
      data: props.perf.model_runs.map((r) => seconds(dataBy.get(r.at.slice(0, 13)))),
      color: c.faint,
    },
    ...MODELS.map((m) => ({
      name: t(`modelNames.${m}`),
      data: props.perf.model_runs.map((r) => seconds(r.model_ms[m])),
      color: css(MODEL_VAR[m]),
    })),
  ]
  return {
    grid: { left: 8, right: 16, top: 56, bottom: 8, containLabel: true },
    legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 12, itemHeight: 8, textStyle: { color: c.muted, fontFamily: 'Onest Variable' } },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: c.surface,
      borderColor: c.axis,
      textStyle: { color: c.ink, fontFamily: 'Onest Variable' },
      valueFormatter: (v: number) => `${formatNumber(v, lang.value, 1)} ${t('perf.sec')}`,
    },
    xAxis: {
      type: 'category',
      data: hours.map((h) => formatHour(h, lang.value)),
      axisLine: { lineStyle: { color: c.axis } },
      axisTick: { show: false },
      axisLabel: { color: c.faint, hideOverlap: true },
    },
    yAxis: { type: 'value', name: t('perf.sec'), nameTextStyle: { color: c.faint }, axisLabel: { color: c.faint }, splitLine: { lineStyle: { color: c.grid } } },
    series: series.map((s) => ({
      name: s.name,
      type: 'bar',
      stack: 'run',
      data: s.data,
      itemStyle: { color: s.color, borderColor: c.surface, borderWidth: 1 },
      barMaxWidth: 28,
    })),
  }
})
</script>

<template>
  <div class="h-80 w-full">
    <VChart :option="option" autoresize />
  </div>
</template>
