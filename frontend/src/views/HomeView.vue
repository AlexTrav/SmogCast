<script setup lang="ts">
import { ChartSpline, ChevronDown } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import BestTimes from '../components/home/BestTimes.vue'
import DayCards from '../components/home/DayCards.vue'
import ExplainCard from '../components/home/ExplainCard.vue'
import FactorList from '../components/home/FactorList.vue'
import ForecastDetails from '../components/home/ForecastDetails.vue'
import HourlyStrip from '../components/home/HourlyStrip.vue'
import LevelScale from '../components/home/LevelScale.vue'
import SkyHero from '../components/home/SkyHero.vue'
import { useLive } from '../composables/useLive'
import type { Explain, Forecast, Weather } from '../types'
import { localDay } from '../utils/format'
import { dayOutlook, hoursOf } from '../utils/outlook'

const { t } = useI18n()
const { status } = useLive()

// прогноз смеси по умолчанию: по нему карточки дней, лента и «когда выйти»; другие модели – в подробностях
const main = ref<Forecast | null>(null)
const actual = ref<{ start: string; values: (number | null)[] } | null>(null)
const weather = ref<Weather | null>(null)
const explain = ref<Explain | null>(null)

// всё, что зависит от часа ряда, перечитывается, когда ежечасная задача дописала новый час
async function load() {
  const now = new Date()
  const [f, h, w, e] = await Promise.allSettled([
    api.forecast(),
    api.hours(localDay(now, -2), localDay(now)),
    api.weather(),
    api.explain(),
  ])
  if (f.status === 'fulfilled') main.value = f.value
  if (h.status === 'fulfilled' && h.value.start) actual.value = { start: h.value.start, values: h.value.values.pm2_5 }
  if (w.status === 'fulfilled') weather.value = w.value
  if (e.status === 'fulfilled') explain.value = e.value
}
watch(() => status.value?.time, load, { immediate: true })

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
            <ForecastDetails v-if="main" :main="main" :actual="actual" />
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
