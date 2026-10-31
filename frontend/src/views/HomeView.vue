<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import FactorList from '../components/home/FactorList.vue'
import LevelScale from '../components/home/LevelScale.vue'
import SkyHero from '../components/home/SkyHero.vue'
import { useLive } from '../composables/useLive'
import type { AppLocale, Forecast, Weather } from '../types'
import { formatDateHour, formatNumber, localDay } from '../utils/format'

// график – отдельным чанком вместе с ECharts: первый экран (небо) появляется без него
const ForecastChart = defineAsyncComponent(() => import('../components/home/ForecastChart.vue'))

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { status } = useLive()

const forecast = ref<Forecast | null>(null)
const actual = ref<{ start: string; values: (number | null)[] } | null>(null)
const weather = ref<Weather | null>(null)

// данные графика и погоды перечитываются, когда в ряду появляется новый час
async function load() {
  const now = new Date()
  const [f, h, w] = await Promise.allSettled([api.forecast(), api.hours(localDay(now, -2), localDay(now)), api.weather()])
  if (f.status === 'fulfilled') forecast.value = f.value
  if (h.status === 'fulfilled' && h.value.start) actual.value = { start: h.value.start, values: h.value.values.pm2_5 }
  if (w.status === 'fulfilled') weather.value = w.value
}
watch(() => status.value?.time, load, { immediate: true })

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
    <SkyHero />

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
        <!-- легенда: у каждой серии своя форма линии, а не только цвет -->
        <ul class="mt-5 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted">
          <li class="flex items-center gap-2"><span class="h-0.5 w-5 rounded bg-ink" />{{ t('forecast.actual') }}</li>
          <li class="flex items-center gap-2"><span class="h-[3px] w-5 rounded" style="background: var(--series-1)" />{{ t('forecast.pred') }}</li>
          <li class="flex items-center gap-2"><span class="h-3 w-5 rounded-sm" style="background: color-mix(in srgb, var(--series-1) 34%, transparent)" />{{ t('forecast.band80') }}</li>
          <li class="flex items-center gap-2"><span class="h-3 w-5 rounded-sm" style="background: color-mix(in srgb, var(--series-1) 14%, transparent)" />{{ t('forecast.band95') }}</li>
          <li class="flex items-center gap-2"><span class="w-5 border-t-2 border-dashed border-muted" />{{ t('forecast.cams') }}</li>
        </ul>
        <div class="mt-3">
          <ForecastChart v-if="forecast && actual" :forecast="forecast" :actual="actual" />
          <div v-else class="h-80 animate-pulse rounded-2xl bg-surface-2 sm:h-96" />
        </div>
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
    </div>
  </div>
</template>
