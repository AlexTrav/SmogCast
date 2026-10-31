<script setup lang="ts">
import { CalendarRange, Clock3, CloudSun, Layers, Gauge } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AppLocale, Explain } from '../../types'
import { formatNumber } from '../../utils/format'
import { modelColor } from '../../utils/models'

// «почему такой прогноз»: уровень × сезон × суточный ход (части Prophet), влияние погоды на LSTM
// и из каких моделей сложена смесь по умолчанию
const props = defineProps<{ explain: Explain }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)

const factor = (v: number) => `×${formatNumber(v, lang.value, 2)}`
const hour = (h: number) => `${String(h).padStart(2, '0')}:00`
const percent = (ratio: number) => {
  const p = (ratio - 1) * 100
  return `${p > 0 ? '+' : p < 0 ? '−' : '±'}${formatNumber(Math.abs(p), lang.value)} %`
}

const items = computed(() => {
  const out: { icon: unknown; title: string; value: string; text: string }[] = []
  const p = props.explain.prophet
  if (p) {
    out.push({ icon: Gauge, title: t('explain.level'), value: formatNumber(p.summary.level, lang.value), text: t('explain.levelText') })
    out.push({
      icon: CalendarRange,
      title: t('explain.season'),
      value: factor(p.summary.yearly),
      text: p.summary.yearly >= 1 ? t('explain.seasonUp') : t('explain.seasonDown'),
    })
    out.push({
      icon: Clock3,
      title: t('explain.daily'),
      value: `${factor(p.summary.daily_low.factor)}…${factor(p.summary.daily_high.factor)}`,
      text: t('explain.dailyText', { high: hour(p.summary.daily_high.hour), low: hour(p.summary.daily_low.hour) }),
    })
  }
  const w = props.explain.weather
  if (w) {
    out.push({ icon: CloudSun, title: t('explain.weather'), value: percent(w.mean_24h), text: t('explain.weatherText', { value: percent(w.mean_24h) }) })
  }
  return out
})

// части смеси на ближайший час, цвет – закреплённый за моделью цвет серии
const parts = computed(() =>
  Object.entries(props.explain.blend.parts).map(([key, values]) => ({ key, value: values[0], color: modelColor(key) })),
)
</script>

<template>
  <div class="grid gap-6 lg:grid-cols-[1fr_18rem]">
    <ul class="grid gap-4 sm:grid-cols-2">
      <li v-for="(item, i) in items" :key="item.title" v-reveal="i" class="rounded-2xl border border-line bg-surface-2/50 p-4">
        <div class="flex items-center gap-2 text-sm font-semibold text-muted">
          <component :is="item.icon" class="h-4 w-4 text-primary" aria-hidden="true" />
          {{ item.title }}
        </div>
        <p class="num mt-2 text-2xl font-semibold text-ink">{{ item.value }}</p>
        <p class="mt-1 text-sm text-muted">{{ item.text }}</p>
      </li>
    </ul>
    <div v-reveal="2" class="rounded-2xl border border-line p-4">
      <div class="flex items-center gap-2 text-sm font-semibold text-muted">
        <Layers class="h-4 w-4 text-primary" aria-hidden="true" />
        {{ t('explain.blend') }}
      </div>
      <p class="mt-1 text-sm text-muted">{{ t('explain.blendText') }}</p>
      <ul class="mt-4 space-y-2.5">
        <li v-for="p in parts" :key="p.key" class="flex items-center gap-3 text-sm">
          <span class="h-2.5 w-2.5 rounded-full" :style="{ background: p.color }" />
          <span class="text-ink">{{ t(`modelNames.${p.key}`) }}</span>
          <span class="num ml-auto text-ink">{{ formatNumber(p.value, lang) }}</span>
        </li>
        <li class="flex items-center gap-3 border-t border-line pt-2.5 text-sm font-semibold">
          <span class="h-2.5 w-2.5 rounded-full" :style="{ background: modelColor(explain.blend.model) }" />
          <span class="text-ink">{{ t(`modelNames.${explain.blend.model}`) }}</span>
          <span class="num ml-auto text-ink">{{ formatNumber(explain.blend.pred[0], lang) }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>
