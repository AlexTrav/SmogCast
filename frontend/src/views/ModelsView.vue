<script setup lang="ts">
import { Crosshair, Gauge, ShieldCheck, Target } from 'lucide-vue-next'
import { computed, defineAsyncComponent, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import ConfusionTable from '../components/models/ConfusionTable.vue'
import ModelRace from '../components/models/ModelRace.vue'
import RankingTable from '../components/models/RankingTable.vue'
import { useCountUp } from '../composables/useCountUp'
import { useLive } from '../composables/useLive'
import type { AppLocale, ModelsReport, Verify } from '../types'
import { formatNumber } from '../utils/format'

// графики – отдельными чанками вместе с ECharts
const HorizonChart = defineAsyncComponent(() => import('../components/models/HorizonChart.vue'))
const YesterdayChart = defineAsyncComponent(() => import('../components/models/YesterdayChart.vue'))

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { status } = useLive()
const report = ref<ModelsReport | null>(null)
const verify = ref<Verify | null>(null)

onMounted(async () => {
  try {
    report.value = await api.models()
  } catch {
    // плашка сервера покажет, что API недоступен
  }
})
// журнал «прогноз -> факт» перечитывается с каждым новым часом ряда
watch(
  () => status.value?.time,
  async () => {
    try {
      verify.value = await api.verify(7)
    } catch {
      // журнал остаётся прежним
    }
  },
  { immediate: true },
)

// главные итоги смеси по умолчанию на тестовом году, первые сутки прогноза
const head = computed(() => {
  const r = report.value?.test
  if (!r) return null
  const key = r.meta.default
  return { mae: r.models[key].buckets['1–24'], aqi: r.aqi[key]['1–24'] }
})
const percent = (v: number) => `${formatNumber(v * 100, lang.value, 0)} %`
const mae = useCountUp(computed(() => head.value?.mae.mae), 900)
const tiles = computed(() => {
  const h = head.value
  if (!h) return []
  return [
    { icon: Gauge, label: t('modelsPage.maeTile'), value: formatNumber(mae.value ?? h.mae.mae, lang.value, 2), note: t('modelsPage.maeNote') },
    { icon: Target, label: t('modelsPage.levelTile'), value: percent(h.aqi.level_exact), note: t('modelsPage.levelNote', { value: percent(h.aqi.level_within_one) }) },
    { icon: Crosshair, label: t('modelsPage.smogTile'), value: percent(h.aqi.smog_caught), note: t('modelsPage.smogNote', { value: percent(h.aqi.false_alarms) }) },
    { icon: ShieldCheck, label: t('modelsPage.coverTile'), value: percent(h.mae.cover80), note: t('modelsPage.coverNote') },
  ]
})
</script>

<template>
  <div class="mx-auto max-w-7xl px-4 pt-28 sm:px-6">
    <p class="eyebrow animate-rise">{{ t('modelsPage.eyebrow') }}</p>
    <h1 class="animate-rise mt-3 max-w-3xl text-4xl font-bold tracking-tight text-ink sm:text-5xl" style="animation-delay: 60ms">
      {{ t('modelsPage.title') }}
    </h1>
    <p class="animate-rise mt-4 max-w-3xl text-lg leading-relaxed text-muted" style="animation-delay: 120ms">{{ t('modelsPage.intro') }}</p>

    <dl class="mt-10 grid grid-cols-2 gap-4 lg:grid-cols-4">
      <template v-if="tiles.length">
        <div v-for="(tile, i) in tiles" :key="tile.label" v-reveal="i" class="card p-5">
          <dt class="flex items-center gap-2 text-sm font-medium text-muted">
            <component :is="tile.icon" class="h-4 w-4 text-primary" aria-hidden="true" />{{ tile.label }}
          </dt>
          <dd class="num mt-2 text-4xl font-semibold text-ink">{{ tile.value }}</dd>
          <dd class="mt-1 text-xs text-faint">{{ tile.note }}</dd>
        </div>
      </template>
      <div v-for="i in 4" v-else :key="i" class="card h-32 animate-pulse" />
    </dl>

    <!-- живой журнал -->
    <section v-reveal class="card mt-8 p-5 sm:p-7">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('modelsPage.live') }}</h2>
      <p class="mt-1 max-w-3xl text-sm text-muted">{{ t('modelsPage.liveText') }}</p>
      <div class="mt-6 grid gap-8 lg:grid-cols-2">
        <div>
          <h3 class="font-semibold text-ink">{{ t('modelsPage.race') }}</h3>
          <p class="mt-1 text-sm text-muted">{{ t('modelsPage.raceText') }}</p>
          <div class="mt-4">
            <ModelRace v-if="verify && Object.keys(verify.models).length" :verify="verify" />
            <p v-else class="rounded-2xl bg-surface-2 p-4 text-sm text-muted">{{ t('modelsPage.empty') }}</p>
          </div>
        </div>
        <div>
          <h3 class="font-semibold text-ink">{{ t('modelsPage.yesterday') }}</h3>
          <p class="mt-1 text-sm text-muted">{{ t('modelsPage.yesterdayText') }}</p>
          <div class="mt-4">
            <YesterdayChart v-if="verify?.yesterday" :data="verify.yesterday" />
            <p v-else class="rounded-2xl bg-surface-2 p-4 text-sm text-muted">{{ t('modelsPage.empty') }}</p>
          </div>
        </div>
      </div>
    </section>

    <section v-reveal class="card mt-8 p-5 sm:p-7">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('modelsPage.horizon') }}</h2>
      <p class="mt-1 max-w-3xl text-sm text-muted">{{ t('modelsPage.horizonText') }}</p>
      <div class="mt-4">
        <HorizonChart v-if="report" :mae-by-horizon="report.test.mae_by_horizon" />
        <div v-else class="h-96 animate-pulse rounded-2xl bg-surface-2" />
      </div>
    </section>

    <section v-reveal class="card mt-8 p-5 sm:p-7">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('modelsPage.ranking') }}</h2>
      <p class="mt-1 max-w-3xl text-sm text-muted">{{ t('modelsPage.rankingText') }}</p>
      <div class="mt-4">
        <RankingTable v-if="report" :report="report.test" />
        <div v-else class="h-96 animate-pulse rounded-2xl bg-surface-2" />
      </div>
    </section>

    <section v-reveal class="card mt-8 p-5 sm:p-7">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('modelsPage.confusion') }}</h2>
      <p class="mt-1 max-w-3xl text-sm text-muted">{{ t('modelsPage.confusionText') }}</p>
      <div class="mt-4">
        <ConfusionTable v-if="report" :matrix="report.test.confusion_24h" />
      </div>
    </section>
  </div>
</template>
