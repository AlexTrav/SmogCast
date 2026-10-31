<script setup lang="ts">
import { ChartSpline, ChevronDown, Compass } from 'lucide-vue-next'
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
import TourGuide from '../components/home/TourGuide.vue'
import TermHint from '../components/TermHint.vue'
import { useLive } from '../composables/useLive'
import { useSensitive } from '../composables/useSensitive'
import type { Explain, Forecast, Weather } from '../types'
import { localDay } from '../utils/format'
import { dayOutlook, hoursOf } from '../utils/outlook'

const { t } = useI18n()
const { status } = useLive()
const { sensitive } = useSensitive()
const tour = ref<InstanceType<typeof TourGuide> | null>(null)

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
          <div class="flex flex-wrap items-start justify-between gap-3">
            <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('outlook.title') }}</h2>
            <button class="inline-flex items-center gap-1.5 text-sm font-medium text-primary-strong hover:underline" @click="tour?.start()">
              <Compass class="h-4 w-4" aria-hidden="true" />{{ t('tour.start') }}
            </button>
          </div>
          <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('outlook.subtitle') }}</p>
          <DayCards v-if="days.length" class="mt-5" data-tour="days" :days="days" :selected="day" @select="day = $event" />
          <div v-else class="mt-5 grid gap-3 sm:grid-cols-3">
            <div v-for="i in 3" :key="i" class="h-44 animate-pulse rounded-2xl bg-surface-2" />
          </div>
          <h3 class="mt-6 text-sm font-semibold text-muted">{{ t('outlook.hourly') }}</h3>
          <HourlyStrip v-if="points.length" class="mt-2" :points="points" :now="current" :day="day" />
          <div v-else class="mt-2 h-32 animate-pulse rounded-2xl bg-surface-2" />

          <button class="btn-ghost mt-5" data-tour="more" :aria-expanded="expanded" aria-controls="details" @click="expanded = !expanded">
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
        <section class="card p-5 sm:p-6" data-tour="best">
          <h2 class="text-lg font-bold tracking-tight text-ink">{{ t('outlook.windowsTitle') }}</h2>
          <p class="mt-1 text-sm text-muted">{{ t('outlook.windowsSubtitle') }}</p>
          <!-- переключатель-тумблер: настоящий чекбокс (role="switch") спрятан, рисуется его «дорожка» -->
          <label class="mt-4 flex cursor-pointer items-center justify-between gap-3 rounded-xl bg-surface-2 px-3.5 py-2.5">
            <span>
              <span class="block text-sm font-medium text-ink">{{ t('sensitive.label') }}</span>
              <span class="block text-xs text-muted">{{ t('sensitive.hint') }}</span>
            </span>
            <input v-model="sensitive" type="checkbox" role="switch" class="peer sr-only" />
            <span
              class="relative h-6 w-11 shrink-0 rounded-full bg-line transition-colors peer-checked:bg-primary peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary after:absolute after:top-0.5 after:left-0.5 after:h-5 after:w-5 after:rounded-full after:bg-white after:shadow after:transition-transform peer-checked:after:translate-x-5"
              aria-hidden="true"
            />
          </label>
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
          <h2 class="flex items-center gap-2 text-lg font-bold tracking-tight text-ink">{{ t('forecast.scale') }} <TermHint term="aqi" /></h2>
          <p class="mt-1 text-sm text-muted">{{ t('forecast.scaleNote') }}</p>
          <div class="mt-4">
            <LevelScale v-if="status" :pm="status.pm2_5" />
          </div>
        </section>
      </div>
    </div>
    <TourGuide ref="tour" :ready="days.length > 0" />
  </div>
</template>
