<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import ExplainCard from '../components/home/ExplainCard.vue'
import FactorList from '../components/home/FactorList.vue'
import LevelScale from '../components/home/LevelScale.vue'
import RecomputePanel from '../components/home/RecomputePanel.vue'
import SkyHero from '../components/home/SkyHero.vue'
import { useLive } from '../composables/useLive'
import type { AppLocale, Explain, Forecast, Weather } from '../types'
import { formatDateHour, formatNumber, localDay } from '../utils/format'
import { DEFAULT_MODEL, modelColor, sortModels } from '../utils/models'

// график – отдельным чанком вместе с ECharts: первый экран (небо) появляется без него
const ForecastChart = defineAsyncComponent(() => import('../components/home/ForecastChart.vue'))

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { status } = useLive()

const model = ref(DEFAULT_MODEL)
const forecast = ref<Forecast | null>(null)
const actual = ref<{ start: string; values: (number | null)[] } | null>(null)
const weather = ref<Weather | null>(null)
const explain = ref<Explain | null>(null)

// всё, что зависит от часа ряда, перечитывается, когда ежечасная задача дописала новый час
async function load() {
  const now = new Date()
  const [f, h, w, e] = await Promise.allSettled([
    api.forecast(model.value),
    api.hours(localDay(now, -2), localDay(now)),
    api.weather(),
    api.explain(),
  ])
  if (f.status === 'fulfilled') forecast.value = f.value
  if (h.status === 'fulfilled' && h.value.start) actual.value = { start: h.value.start, values: h.value.values.pm2_5 }
  if (w.status === 'fulfilled') weather.value = w.value
  if (e.status === 'fulfilled') explain.value = e.value
}
watch(() => status.value?.time, load, { immediate: true })

async function pick(key: string) {
  model.value = key
  try {
    forecast.value = await api.forecast(key)
  } catch {
    // ошибку покажет плашка сервера; график остаётся прежним
  }
}

const models = computed(() => sortModels(forecast.value?.models ?? []))
// ветер в ближайший час – для дрейфа частиц и стрелки над городом
const wind = computed(() => weather.value?.values.wind?.[0] ?? null)
const windDir = computed(() => weather.value?.values.wind_dir?.[0] ?? null)

const extremes = computed(() => {
  const f = forecast.value
  if (!f) return null
  const hour = (i: number) => new Date(new Date(f.start).getTime() + i * 3_600_000)
  const peak = f.pred.indexOf(Math.max(...f.pred))
  const low = f.pred.indexOf(Math.min(...f.pred))
  return {
    peak: { value: f.pred[peak], time: hour(peak) },
    low: { value: f.pred[low], time: hour(low) },
  }
})
</script>

<template>
  <div>
    <SkyHero :wind="wind" :wind-dir="windDir" />

    <div class="relative z-10 mx-auto -mt-20 grid max-w-7xl gap-6 px-4 sm:px-6 lg:grid-cols-3">
      <!-- прогноз на 72 часа -->
      <section class="card p-5 sm:p-7 lg:col-span-2">
        <div class="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('forecast.title') }}</h2>
            <p class="mt-1 max-w-xl text-sm text-muted">{{ t('forecast.subtitle') }}</p>
          </div>
          <div v-if="extremes" class="flex gap-6 text-right">
            <div>
              <p class="eyebrow">{{ t('forecast.peak') }}</p>
              <p class="num text-2xl font-semibold text-ink">{{ formatNumber(extremes.peak.value, lang) }}</p>
              <p class="text-xs text-faint">{{ formatDateHour(extremes.peak.time, lang) }}</p>
            </div>
            <div>
              <p class="eyebrow">{{ t('forecast.min') }}</p>
              <p class="num text-2xl font-semibold text-ink">{{ formatNumber(extremes.low.value, lang) }}</p>
              <p class="text-xs text-faint">{{ formatDateHour(extremes.low.time, lang) }}</p>
            </div>
          </div>
        </div>

        <!-- выбор модели: у каждой свой закреплённый цвет -->
        <div v-if="models.length" class="mt-5 flex flex-wrap gap-2" role="radiogroup" :aria-label="t('forecast.model')">
          <button
            v-for="key in models"
            :key="key"
            role="radio"
            :aria-checked="model === key"
            class="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors"
            :class="model === key ? 'border-ink bg-ink text-bg' : 'border-line text-muted hover:border-faint hover:text-ink'"
            @click="pick(key)"
          >
            <span class="h-2 w-2 rounded-full" :style="{ background: modelColor(key) }" />
            {{ t(`modelNames.${key}`) }}
          </button>
        </div>

        <!-- легенда: у каждой серии своя форма линии, а не только цвет -->
        <ul class="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted">
          <li class="flex items-center gap-2"><span class="h-0.5 w-5 rounded bg-ink" />{{ t('forecast.actual') }}</li>
          <li class="flex items-center gap-2">
            <span class="h-[3px] w-5 rounded" :style="{ background: modelColor(model) }" />{{ t('forecast.pred') }}
          </li>
          <li class="flex items-center gap-2">
            <span class="h-3 w-5 rounded-sm" :style="{ background: `color-mix(in srgb, ${modelColor(model)} 34%, transparent)` }" />
            {{ t('forecast.band80') }}
          </li>
          <li class="flex items-center gap-2">
            <span class="h-3 w-5 rounded-sm" :style="{ background: `color-mix(in srgb, ${modelColor(model)} 14%, transparent)` }" />
            {{ t('forecast.band95') }}
          </li>
          <li class="flex items-center gap-2"><span class="w-5 border-t-2 border-dashed border-muted" />{{ t('forecast.cams') }}</li>
        </ul>
        <div class="mt-3">
          <ForecastChart v-if="forecast && actual" :forecast="forecast" :actual="actual" />
          <div v-else class="h-80 animate-pulse rounded-2xl bg-surface-2 sm:h-96" />
        </div>
        <!-- те же значения таблицей: для экранного диктора и для тех, кому удобнее цифры -->
        <details v-if="forecast" class="group mt-4 text-sm">
          <summary class="cursor-pointer font-medium text-muted hover:text-ink">{{ t('forecast.table') }}</summary>
          <div class="mt-3 max-h-80 overflow-auto rounded-2xl border border-line">
            <table class="w-full">
              <thead class="sticky top-0 bg-surface text-left text-xs text-faint uppercase">
                <tr>
                  <th class="px-3 py-2 font-semibold">{{ t('forecast.time') }}</th>
                  <th class="px-3 py-2 text-right font-semibold">{{ t('forecast.pred') }}</th>
                  <th class="px-3 py-2 text-right font-semibold">{{ t('forecast.band80') }}</th>
                  <th class="px-3 py-2 text-right font-semibold">{{ t('forecast.cams') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(v, i) in forecast.pred" :key="i" class="border-t border-line/70">
                  <td class="px-3 py-1.5 text-muted">{{ formatDateHour(new Date(new Date(forecast.start).getTime() + i * 3_600_000), lang) }}</td>
                  <td class="num px-3 py-1.5 text-right text-ink">{{ formatNumber(v, lang) }}</td>
                  <td class="num px-3 py-1.5 text-right text-muted">{{ formatNumber(forecast.lo80[i], lang) }}–{{ formatNumber(forecast.hi80[i], lang) }}</td>
                  <td class="num px-3 py-1.5 text-right text-muted">{{ forecast.cams[i] == null ? '–' : formatNumber(forecast.cams[i] as number, lang) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </details>
        <RecomputePanel class="mt-5" />
      </section>

      <div class="space-y-6">
        <section class="card p-5 sm:p-6">
          <h2 class="text-lg font-bold tracking-tight text-ink">{{ t('factors.title') }}</h2>
          <p class="mt-1 text-sm text-muted">{{ t('factors.subtitle') }}</p>
          <div class="mt-4">
            <FactorList v-if="weather" :factors="weather.factors" />
            <div v-else class="h-64 animate-pulse rounded-2xl bg-surface-2" />
          </div>
        </section>
        <section class="card p-5 sm:p-6">
          <h2 class="text-lg font-bold tracking-tight text-ink">{{ t('forecast.scale') }}</h2>
          <p class="mt-1 text-sm text-muted">{{ t('forecast.scaleNote') }}</p>
          <div class="mt-4">
            <LevelScale v-if="status" :pm="status.pm2_5" />
          </div>
        </section>
      </div>

      <!-- почему такой прогноз -->
      <section v-reveal class="card p-5 sm:p-7 lg:col-span-3">
        <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('explain.title') }}</h2>
        <p class="mt-1 max-w-3xl text-sm text-muted">{{ t('explain.subtitle') }}</p>
        <div class="mt-6">
          <ExplainCard v-if="explain" :explain="explain" />
          <div v-else class="h-40 animate-pulse rounded-2xl bg-surface-2" />
        </div>
      </section>
    </div>
  </div>
</template>
