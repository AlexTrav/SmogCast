<script setup lang="ts">
import {
  BrainCircuit,
  ChartSpline,
  CloudDownload,
  Database,
  FlaskConical,
  Layers,
  MonitorSmartphone,
  Shuffle,
  TimerReset,
  Waves,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import { LINKS } from '../links'
import type { AppLocale, ModelsReport } from '../types'
import { formatNumber } from '../utils/format'
import { modelColor } from '../utils/models'

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const report = ref<ModelsReport | null>(null)
onMounted(async () => {
  try {
    report.value = await api.models()
  } catch {
    // плашка сервера покажет, что API недоступен
  }
})

// цифры проекта: часы ряда считаются от 01.09.2022 до сейчас; автотесты – pytest (сбор и база 29,
// исследование 11, модели 41, API 31) и Vitest сайта на момент последнего коммита
const SERIES_START = Date.UTC(2022, 8, 1)
const TESTS_TOTAL = 29 + 11 + 41 + 31 + 28
const facts = computed(() => [
  { value: formatNumber(Math.floor((Date.now() - SERIES_START) / 3_600_000), lang.value, 0), label: t('about.factHours') },
  { value: '7', label: t('about.factModels') },
  { value: '72', label: t('about.factHorizon') },
  { value: String(TESTS_TOTAL), label: t('about.factTests') },
])

// этапы проекта: данные, исследование, честная проверка, модели, ежечасная задача, сайт
const PIPELINE_ICONS = [CloudDownload, FlaskConical, TimerReset, BrainCircuit, Database, MonitorSmartphone]
const pipeline = computed(() =>
  PIPELINE_ICONS.map((icon, i) => ({ icon, title: t(`about.step${i + 1}Title`), text: t(`about.step${i + 1}Text`) })),
)
const models = computed(() => [
  { icon: ChartSpline, title: 'ARIMA', text: t('about.arimaText') },
  { icon: Waves, title: 'Prophet', text: t('about.prophetText') },
  { icon: BrainCircuit, title: 'LSTM', text: t('about.lstmText') },
  { icon: Layers, title: t('modelNames.arima+lstm+lstm_weather'), text: t('about.blendText') },
])

// сравнение моделей на тестовом году: средняя ошибка 1–72 ч, полоса – доля от худшей
const bars = computed(() => {
  const m = report.value?.test.models
  if (!m) return []
  const rows = Object.entries(m)
    .map(([key, v]) => ({ key, mae: v.mae_1_72 }))
    .sort((a, b) => a.mae - b.mae)
  const max = Math.max(...rows.map((r) => r.mae))
  return rows.map((r) => ({ ...r, width: (r.mae / max) * 100 }))
})

const stack = [
  'Python', 'pandas', 'statsmodels', 'Prophet', 'PyTorch', 'ONNX Runtime', 'Google Colab', 'FastAPI', 'PostgreSQL',
  'Neon', 'Vue 3', 'TypeScript', 'Tailwind CSS 4', 'vue-i18n', 'Apache ECharts', 'MapLibre GL', 'Vite', 'Vitest', 'pytest',
  'Docker', 'GitHub Actions', 'cron-job.org', 'Render', 'GitHub Pages', 'Open-Meteo', 'Copernicus CAMS',
]
</script>

<template>
  <div class="mx-auto max-w-7xl px-4 pt-28 sm:px-6">
    <p class="eyebrow animate-rise">{{ t('about.eyebrow') }}</p>
    <h1 class="animate-rise mt-3 max-w-3xl text-4xl font-bold tracking-tight text-ink sm:text-5xl" style="animation-delay: 60ms">
      {{ t('about.title') }}
    </h1>
    <p class="animate-rise mt-5 max-w-3xl text-lg leading-relaxed text-muted" style="animation-delay: 120ms">{{ t('about.intro') }}</p>

    <dl class="mt-10 grid grid-cols-2 gap-4 lg:grid-cols-4">
      <div v-for="(f, i) in facts" :key="f.label" v-reveal="i" class="card lift p-5">
        <dd class="num text-4xl font-bold text-primary">{{ f.value }}</dd>
        <dt class="mt-1 text-sm text-muted">{{ f.label }}</dt>
      </div>
    </dl>

    <!-- конвейер проекта: акцент-черта вместо номеров шагов -->
    <h2 v-reveal class="mt-20 text-3xl font-bold tracking-tight text-ink">{{ t('about.pipelineTitle') }}</h2>
    <ol class="mt-8 grid gap-x-6 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
      <li v-for="(step, i) in pipeline" :key="i" v-reveal="i % 3" class="relative border-t-2 border-line pt-5">
        <span class="absolute -top-0.5 left-0 h-0.5 w-12 bg-accent" />
        <component :is="step.icon" class="h-6 w-6 text-primary" aria-hidden="true" />
        <h3 class="mt-3 text-lg font-semibold text-ink">{{ step.title }}</h3>
        <p class="mt-1.5 text-[15px] leading-relaxed text-muted">{{ step.text }}</p>
      </li>
    </ol>

    <section class="mt-20 rounded-3xl bg-surface-2/70 p-6 sm:p-10">
      <h2 v-reveal class="text-3xl font-bold tracking-tight text-ink">{{ t('about.modelsTitle') }}</h2>
      <div class="mt-8 grid gap-5 md:grid-cols-2">
        <div v-for="(m, i) in models" :key="m.title" v-reveal="i" class="card lift p-6">
          <span class="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-on-primary">
            <component :is="m.icon" class="h-5 w-5" aria-hidden="true" />
          </span>
          <h3 class="mt-4 text-lg font-semibold text-ink">{{ m.title }}</h3>
          <p class="mt-2 text-[15px] leading-relaxed text-muted">{{ m.text }}</p>
        </div>
      </div>
    </section>

    <h2 v-reveal class="mt-20 text-3xl font-bold tracking-tight text-ink">{{ t('about.compareTitle') }}</h2>
    <p v-reveal class="mt-3 max-w-3xl text-muted">{{ t('about.compareText') }}</p>
    <div class="card mt-8 p-6 sm:p-8">
      <ul v-if="bars.length" class="space-y-3">
        <li v-for="b in bars" :key="b.key" class="grid grid-cols-[minmax(0,14rem)_1fr_3.5rem] items-center gap-3 text-sm">
          <span class="flex items-center gap-2 truncate text-ink" :class="b.key === report?.test.meta.default ? 'font-semibold' : ''">
            <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ background: modelColor(b.key) }" />
            <span class="truncate">{{ t(`modelNames.${b.key}`) }}</span>
          </span>
          <span class="h-3 overflow-hidden rounded-full bg-surface-2">
            <span class="block h-full rounded-full" :style="{ width: `${b.width}%`, background: modelColor(b.key) }" />
          </span>
          <span class="num text-right text-ink">{{ formatNumber(b.mae, lang, 2) }}</span>
        </li>
      </ul>
      <div v-else class="h-72 skeleton rounded-2xl bg-surface-2" />
      <RouterLink to="/models" class="btn-ghost mt-6">
        <Shuffle class="h-4 w-4" aria-hidden="true" />{{ t('about.moreModels') }}
      </RouterLink>
    </div>

    <div class="mt-20 grid gap-10 lg:grid-cols-2">
      <section v-reveal>
        <h2 class="text-2xl font-bold tracking-tight text-ink">{{ t('about.stackTitle') }}</h2>
        <div class="mt-5 flex flex-wrap gap-2">
          <span v-for="s in stack" :key="s" class="chip cursor-default">{{ s }}</span>
        </div>
      </section>
      <section v-reveal="1">
        <h2 class="text-2xl font-bold tracking-tight text-ink">{{ t('about.limitsTitle') }}</h2>
        <ul class="mt-5 space-y-3">
          <li v-for="n in 5" :key="n" class="flex gap-3 text-[15px] leading-relaxed text-muted">
            <span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />{{ t(`about.limit${n}`) }}
          </li>
        </ul>
      </section>
    </div>

    <section v-reveal class="card mt-20 flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8">
      <div>
        <h2 class="text-lg font-semibold text-ink">{{ t('about.authorTitle') }}</h2>
        <p class="mt-1 text-muted">{{ t('about.author') }}</p>
      </div>
      <div class="flex shrink-0 flex-wrap gap-2">
        <a :href="LINKS.github" target="_blank" rel="noopener" class="btn-ghost">GitHub ↗</a>
        <a :href="LINKS.api" target="_blank" rel="noopener" class="btn-ghost">API ↗</a>
      </div>
    </section>
  </div>
</template>
