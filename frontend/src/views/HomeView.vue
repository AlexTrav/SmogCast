<script setup lang="ts">
import { ChartSpline, ChevronDown } from 'lucide-vue-next'
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import BestTimes from '../components/home/BestTimes.vue'
import DayCards from '../components/home/DayCards.vue'
import ExplainCard from '../components/home/ExplainCard.vue'
import FactorList from '../components/home/FactorList.vue'
import HourlyStrip from '../components/home/HourlyStrip.vue'
import LevelScale from '../components/home/LevelScale.vue'
import RecomputePanel from '../components/home/RecomputePanel.vue'
import SkyHero from '../components/home/SkyHero.vue'
import { useLive } from '../composables/useLive'
import type { AppLocale, Explain, Forecast, Weather } from '../types'
import { formatDateHour, formatNumber, localDay } from '../utils/format'
import { DEFAULT_MODEL, modelColor, sortModels } from '../utils/models'
import { dayOutlook, hoursOf } from '../utils/outlook'

// график – отдельным чанком вместе с ECharts: первый экран (небо) появляется без него
const ForecastChart = defineAsyncComponent(() => import('../components/home/ForecastChart.vue'))

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { status } = useLive()

const model = ref(DEFAULT_MODEL)
// карточки дней и лента – всегда по смеси по умолчанию; выбор модели меняет только подробный график
const main = ref<Forecast | null>(null)
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
  if (f.status === 'fulfilled') {
    forecast.value = f.value
    if (f.value.model === f.value.default_model) main.value = f.value
    else api.forecast().then((d) => (main.value = d)).catch(() => {})
  }
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

// прогноз простыми словами: часы смеси, сутки сегодня/завтра/послезавтра; выбранные сутки – в ленте
const points = computed(() => (main.value ? hoursOf(main.value) : []))
const days = computed(() => dayOutlook(points.value, new Date()))
const day = ref(0)
const current = computed(() => (status.value ? { pm: status.value.pm2_5, time: status.value.time } : null))
// подробный график с моделями – по кнопке, ECharts загружается только тогда
const expanded = ref(false)
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

    <div class="relative z-10 mx-auto -mt-20 grid max-w-7xl grid-cols-1 gap-6 px-4 sm:px-6 lg:grid-cols-3">
      <!-- min-w-0: длинная лента по часам не должна раздвигать колонку сетки -->
      <div class="min-w-0 space-y-6 lg:col-span-2">
        <!-- прогноз простыми словами: сутки, лента по часам, подробности по кнопке -->
        <section class="card p-5 sm:p-7">
          <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('outlook.title') }}</h2>
          <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('outlook.subtitle') }}</p>
          <DayCards v-if="days.length" class="mt-5" :days="days" :selected="day" @select="day = $event" />
          <div v-else class="mt-5 grid gap-3 sm:grid-cols-3">
            <div v-for="i in 3" :key="i" class="h-44 animate-pulse rounded-2xl bg-surface-2" />
          </div>
          <h3 class="mt-6 text-sm font-semibold text-muted">{{ t('outlook.hourly') }}</h3>
          <HourlyStrip v-if="points.length" class="mt-2" :points="points" :now="current" :day="day" />
          <div v-else class="mt-2 h-32 animate-pulse rounded-2xl bg-surface-2" />

          <button class="btn-ghost mt-5" :aria-expanded="expanded" aria-controls="details" @click="expanded = !expanded">
            <ChartSpline class="h-4 w-4" aria-hidden="true" />
            {{ expanded ? t('outlook.less') : t('outlook.more') }}
            <ChevronDown class="h-4 w-4 transition-transform" :class="expanded ? 'rotate-180' : ''" aria-hidden="true" />
          </button>

          <div v-if="expanded" id="details" class="mt-6 border-t border-line pt-6">
            <div class="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h3 class="text-lg font-bold tracking-tight text-ink">{{ t('forecast.title') }}</h3>
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
          </div>
        </section>

        <!-- почему такой прогноз -->
        <section v-reveal class="card p-5 sm:p-7">
          <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('explain.title') }}</h2>
          <p class="mt-1 max-w-3xl text-sm text-muted">{{ t('explain.subtitle') }}</p>
          <div class="mt-6">
            <ExplainCard v-if="explain" :explain="explain" />
            <div v-else class="h-40 animate-pulse rounded-2xl bg-surface-2" />
          </div>
        </section>
      </div>

      <div class="min-w-0 space-y-6">
        <section class="card p-5 sm:p-6">
          <h2 class="text-lg font-bold tracking-tight text-ink">{{ t('outlook.windowsTitle') }}</h2>
          <p class="mt-1 text-sm text-muted">{{ t('outlook.windowsSubtitle') }}</p>
          <div class="mt-4">
            <BestTimes v-if="days.length" :days="days" />
            <div v-else class="h-40 animate-pulse rounded-2xl bg-surface-2" />
          </div>
        </section>
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
    </div>
  </div>
</template>
