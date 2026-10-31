<script setup lang="ts">
import { useIntervalFn } from '@vueuse/core'
import { CalendarCheck, Cpu, Database, DownloadCloud, Gauge, Zap } from 'lucide-vue-next'
import { computed, defineAsyncComponent, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import type { AppLocale, Performance } from '../types'
import { formatNumber } from '../utils/format'

// график – отдельным чанком вместе с ECharts
const RunsChart = defineAsyncComponent(() => import('../components/perf/RunsChart.vue'))

const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const perf = ref<Performance | null>(null)

// сводка API меняется с каждым запросом – обновляем страницу раз в 30 секунд, пока она открыта
async function load() {
  try {
    perf.value = await api.performance(48)
  } catch {
    // плашка сервера покажет, что API недоступен
  }
}
onMounted(load)
useIntervalFn(load, 30_000)

const sec = (ms: number | undefined) => (ms == null ? '–' : formatNumber(ms / 1000, lang.value, 1))
const status = computed(() => perf.value?.api.paths['/api/status'])
const tiles = computed(() => {
  const p = perf.value
  if (!p) return []
  const s = p.summary
  return [
    { icon: DownloadCloud, label: t('perf.dataTile'), value: `${sec(s.data_ms?.p50)} ${t('perf.sec')}`, note: t('perf.p95', { value: sec(s.data_ms?.p95) }) },
    { icon: Cpu, label: t('perf.modelsTile'), value: `${sec(s.models_ms?.p50)} ${t('perf.sec')}`, note: t('perf.p95', { value: sec(s.models_ms?.p95) }) },
    { icon: CalendarCheck, label: t('perf.hoursTile'), value: `${s.hours_with_run_7d} / ${s.hours_expected_7d}`, note: t('perf.hoursNote', { value: formatNumber(s.success ?? 0, lang.value, 0) }) },
    { icon: Zap, label: t('perf.apiTile'), value: status.value ? `${formatNumber(status.value.p50_ms, lang.value, 1)} ${t('perf.ms')}` : '–', note: t('perf.apiNote') },
    { icon: Gauge, label: t('perf.lagTile'), value: p.data_runs.at(-1)?.lag_min != null ? `${p.data_runs.at(-1)!.lag_min} ${t('perf.min')}` : '–', note: t('perf.lagNote') },
    { icon: Database, label: t('perf.dbTile'), value: s.db_mb != null ? `${formatNumber(s.db_mb, lang.value, 1)} ${t('perf.mb')}` : '–', note: t('perf.dbNote') },
  ]
})
const paths = computed(() =>
  Object.entries(perf.value?.api.paths ?? {}).sort((a, b) => b[1].requests - a[1].requests),
)
const uptime = computed(() => {
  const s = perf.value?.api.uptime_s ?? 0
  return `${Math.floor(s / 3600)} ${t('perf.h')} ${Math.floor((s % 3600) / 60)} ${t('perf.min')}`
})
</script>

<template>
  <div class="mx-auto max-w-7xl px-4 pt-28 sm:px-6">
    <p class="eyebrow animate-rise">{{ t('perf.eyebrow') }}</p>
    <h1 class="animate-rise mt-3 max-w-3xl text-4xl font-bold tracking-tight text-ink sm:text-5xl" style="animation-delay: 60ms">
      {{ t('perf.title') }}
    </h1>
    <p class="animate-rise mt-4 max-w-3xl text-lg leading-relaxed text-muted" style="animation-delay: 120ms">{{ t('perf.intro') }}</p>

    <dl class="mt-10 grid grid-cols-2 gap-4 lg:grid-cols-3">
      <template v-if="tiles.length">
        <div v-for="(tile, i) in tiles" :key="tile.label" v-reveal="i % 3" class="card p-5">
          <dt class="flex items-center gap-2 text-sm font-medium text-muted">
            <component :is="tile.icon" class="h-4 w-4 text-primary" aria-hidden="true" />{{ tile.label }}
          </dt>
          <dd class="num mt-2 text-3xl font-semibold text-ink">{{ tile.value }}</dd>
          <dd class="mt-1 text-xs text-faint">{{ tile.note }}</dd>
        </div>
      </template>
      <div v-for="i in 6" v-else :key="i" class="card h-32 skeleton" />
    </dl>

    <section v-reveal class="card mt-8 p-5 sm:p-7">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('perf.runs') }}</h2>
      <p class="mt-1 max-w-3xl text-sm text-muted">{{ t('perf.runsText') }}</p>
      <div class="mt-4">
        <RunsChart v-if="perf" :perf="perf" />
        <div v-else class="h-80 skeleton rounded-2xl bg-surface-2" />
      </div>
    </section>

    <section v-reveal class="card mt-8 p-5 sm:p-7">
      <h2 class="text-xl font-bold tracking-tight text-ink sm:text-2xl">{{ t('perf.api') }}</h2>
      <p class="mt-1 max-w-3xl text-sm text-muted">{{ t('perf.apiText', { uptime }) }}</p>
      <div class="mt-4 overflow-x-auto">
        <table class="w-full min-w-[640px] text-sm">
          <thead>
            <tr class="border-b border-line text-left text-xs tracking-wide text-faint uppercase">
              <th class="py-2.5 pr-3 font-semibold">{{ t('perf.path') }}</th>
              <th class="px-3 py-2.5 text-right font-semibold">{{ t('perf.requests') }}</th>
              <th class="px-3 py-2.5 text-right font-semibold">p50</th>
              <th class="px-3 py-2.5 text-right font-semibold">p95</th>
              <th class="px-3 py-2.5 text-right font-semibold">max</th>
              <th class="py-2.5 pl-3 text-right font-semibold">304</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="[path, s] in paths" :key="path" class="border-b border-line/70 last:border-0">
              <td class="py-2.5 pr-3 font-medium text-ink">{{ path }}</td>
              <td class="num px-3 py-2.5 text-right text-muted">{{ s.requests }}</td>
              <td class="num px-3 py-2.5 text-right text-ink">{{ formatNumber(s.p50_ms, lang, 1) }} {{ t('perf.ms') }}</td>
              <td class="num px-3 py-2.5 text-right text-muted">{{ formatNumber(s.p95_ms, lang, 1) }} {{ t('perf.ms') }}</td>
              <td class="num px-3 py-2.5 text-right text-muted">{{ formatNumber(s.max_ms, lang, 1) }} {{ t('perf.ms') }}</td>
              <td class="num py-2.5 pl-3 text-right text-muted">{{ s.requests ? formatNumber((100 * s.not_modified) / s.requests, lang, 0) : 0 }} %</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="mt-4 text-sm text-faint">{{ t('perf.note') }}</p>
    </section>
  </div>
</template>
