<script setup lang="ts">
import { CalendarRange, Clock3, CloudSun, Layers, Gauge } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AppLocale, Explain } from '../../types'
import { formatHour, formatNumber } from '../../utils/format'
import { modelColor } from '../../utils/models'
import TermHint from '../TermHint.vue'

// «почему такой прогноз» словами: обычный фон, влияние сезона, суточный ход (части Prophet), влияние погоды
// (LSTM с погодой против LSTM без неё) и из каких моделей сложена смесь; числа – мелко, с подсказкой «?»
const props = defineProps<{ explain: Explain }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)

const NEUTRAL = 0.05 // влияние меньше 5 % – «почти не влияет»
const percent = (ratio: number) => formatNumber(Math.abs(ratio - 1) * 100, lang.value, 0)
// час суток Prophet – по местному времени Алматы
const hour = (h: number) => `${String(h).padStart(2, '0')}:00`

const items = computed(() => {
  const out: { icon: unknown; term: string; title: string; head: string; text: string }[] = []
  const p = props.explain.prophet
  if (p) {
    const s = p.summary
    out.push({
      icon: Gauge, term: 'exLevel', title: t('explain.level'),
      head: t('explain.levelHead', { value: formatNumber(s.level, lang.value, 0) }),
      text: t('explain.levelText'),
    })
    out.push({
      icon: CalendarRange, term: 'exSeason', title: t('explain.season'),
      head: Math.abs(s.yearly - 1) < NEUTRAL
        ? t('explain.seasonNone')
        : t(s.yearly > 1 ? 'explain.seasonUp' : 'explain.seasonDown', { value: percent(s.yearly) }),
      text: t('explain.seasonText'),
    })
    out.push({
      icon: Clock3, term: 'exDaily', title: t('explain.daily'),
      head: t('explain.dailyHead', { high: hour(s.daily_high.hour), low: hour(s.daily_low.hour) }),
      text: t('explain.dailyText', { times: formatNumber(s.daily_high.factor / s.daily_low.factor, lang.value, 1) }),
    })
  }
  const w = props.explain.weather
  if (w) {
    out.push({
      icon: CloudSun, term: 'exWeather', title: t('explain.weather'),
      head: Math.abs(w.mean_24h - 1) < 0.03
        ? t('explain.weatherNone')
        : t(w.mean_24h > 1 ? 'explain.weatherUp' : 'explain.weatherDown', { value: percent(w.mean_24h) }),
      text: t('explain.weatherText'),
    })
  }
  return out
})

// части смеси на ближайший час, цвет – закреплённый за моделью цвет серии
const parts = computed(() =>
  Object.entries(props.explain.blend.parts).map(([key, values]) => ({ key, value: values[0], color: modelColor(key) })),
)
const firstHour = computed(() => formatHour(props.explain.start, lang.value))
</script>

<template>
  <div class="grid gap-6 lg:grid-cols-[1fr_18rem]">
    <ul class="grid gap-4 sm:grid-cols-2">
      <li v-for="(item, i) in items" :key="item.term" v-reveal="i" class="rounded-2xl border border-line bg-surface-2/50 p-4">
        <div class="flex items-center gap-2 text-sm font-semibold text-muted">
          <component :is="item.icon" class="h-4 w-4 text-primary" aria-hidden="true" />
          {{ item.title }}
          <TermHint :term="item.term" class="ml-auto" />
        </div>
        <p class="mt-2 text-lg leading-snug font-semibold text-ink">{{ item.head }}</p>
        <p class="mt-1 text-sm text-muted">{{ item.text }}</p>
      </li>
    </ul>
    <div v-reveal="2" class="rounded-2xl border border-line p-4">
      <div class="flex items-center gap-2 text-sm font-semibold text-muted">
        <Layers class="h-4 w-4 text-primary" aria-hidden="true" />
        {{ t('explain.blend') }}
        <TermHint term="blend" class="ml-auto" />
      </div>
      <p class="mt-1 text-sm text-muted">{{ t('explain.blendText', { time: firstHour }) }}</p>
      <ul class="mt-4 space-y-2.5">
        <li v-for="p in parts" :key="p.key" class="flex items-center gap-2 text-sm">
          <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ background: p.color }" />
          <span class="text-ink">{{ t(`modelNames.${p.key}`) }}</span>
          <TermHint :term="`model_${p.key}`" />
          <span class="num ml-auto text-ink">{{ formatNumber(p.value, lang, 0) }}</span>
        </li>
        <li class="flex items-center gap-2 border-t border-line pt-2.5 text-sm font-semibold">
          <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ background: modelColor(explain.blend.model) }" />
          <span class="text-ink">{{ t('explain.result') }}</span>
          <span class="num ml-auto text-ink">{{ formatNumber(explain.blend.pred[0], lang, 0) }}</span>
        </li>
      </ul>
      <p class="mt-3 text-xs text-faint">{{ t('explain.unit') }}</p>
    </div>
  </div>
</template>
