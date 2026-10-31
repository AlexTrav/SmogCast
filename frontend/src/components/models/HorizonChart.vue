<script setup lang="ts">
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { computed } from 'vue'
import VChart from 'vue-echarts'
import 'vue-echarts/style.css'
import { useI18n } from 'vue-i18n'
import { useTheme } from '../../composables/useTheme'
import type { AppLocale } from '../../types'
import { formatNumber } from '../../utils/format'
import { MODEL_ORDER, MODEL_VAR } from '../../utils/models'

use([LineChart, GridComponent, LegendComponent, TooltipComponent, SVGRenderer])

// MAE на тестовом году для каждого часа вперёд: модели со своими цветами, базовая «как час назад» – пунктиром
const props = defineProps<{ maeByHorizon: Record<string, number[]> }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { theme } = useTheme()

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}

const option = computed(() => {
  void theme.value
  const c = { ink: css('--ink'), muted: css('--muted'), faint: css('--faint'), grid: css('--grid'), axis: css('--axis'), surface: css('--surface') }
  const keys = [...MODEL_ORDER, 'persistence'].filter((k) => props.maeByHorizon[k])
  return {
    animationDuration: 900,
    grid: { left: 8, right: 16, top: 56, bottom: 28, containLabel: true },
    legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 14, itemHeight: 4, textStyle: { color: c.muted, fontFamily: 'Onest Variable' } },
    tooltip: {
      trigger: 'axis',
      backgroundColor: c.surface,
      borderColor: c.axis,
      textStyle: { color: c.ink, fontFamily: 'Onest Variable' },
      valueFormatter: (v: number) => formatNumber(v, lang.value, 2),
    },
    xAxis: {
      type: 'category',
      data: Array.from({ length: 72 }, (_, i) => i + 1),
      name: t('modelsPage.hoursAhead'),
      nameLocation: 'middle',
      nameGap: 26,
      nameTextStyle: { color: c.faint },
      axisLine: { lineStyle: { color: c.axis } },
      axisTick: { show: false },
      axisLabel: { color: c.faint, interval: 11 },
    },
    yAxis: { type: 'value', min: 0, axisLabel: { color: c.faint }, splitLine: { lineStyle: { color: c.grid } } },
    series: keys.map((k) => ({
      name: t(`modelNames.${k}`),
      type: 'line',
      data: props.maeByHorizon[k],
      showSymbol: false,
      smooth: 0.2,
      lineStyle: MODEL_VAR[k]
        ? { color: css(MODEL_VAR[k]), width: k === MODEL_ORDER[0] ? 3 : 1.8 }
        : { color: c.faint, width: 1.5, type: 'dashed' },
      itemStyle: { color: MODEL_VAR[k] ? css(MODEL_VAR[k]) : c.faint },
      z: k === MODEL_ORDER[0] ? 10 : 2,
    })),
  }
})
</script>

<template>
  <div class="h-96 w-full">
    <VChart :option="option" autoresize />
  </div>
</template>
