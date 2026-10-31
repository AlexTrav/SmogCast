<script setup lang="ts">
import { Check } from 'lucide-vue-next'
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../../api/client'
import type { AppLocale, Forecast } from '../../types'
import { formatDateHour, formatNumber } from '../../utils/format'
import { modelColor, sortModels } from '../../utils/models'
import RecomputePanel from './RecomputePanel.vue'

// график – отдельным чанком вместе с ECharts: загружается, только когда раскрыли подробности
const ForecastChart = defineAsyncComponent(() => import('./ForecastChart.vue'))

// подробный прогноз: модели галочками (можно сравнить несколько на одном графике), горизонт 1/2/3 суток,
// веер и CAMS – по переключателям; таблица значений и «Пересчитать сейчас»
const props = defineProps<{ main: Forecast; actual: { start: string; values: (number | null)[] } | null }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)

const selected = ref<string[]>([props.main.model])
const cache = ref<Record<string, Forecast>>({})
const hours = ref(72)
const band = ref(false)
const cams = ref(false)
const HORIZONS = [24, 48, 72]

async function fetchModel(key: string) {
  try {
    const f = await api.forecast(key)
    cache.value = { ...cache.value, [key]: f }
  } catch {
    // ошибку покажет плашка сервера; модель просто не появится на графике
  }
}

// новый час: смесь пришла сверху, остальные выбранные модели перечитываются
watch(
  () => props.main,
  (main) => {
    cache.value = { [main.model]: main }
    selected.value.filter((k) => k !== main.model).forEach(fetchModel)
  },
  { immediate: true },
)

function toggle(key: string) {
  if (selected.value.includes(key)) {
    if (selected.value.length > 1) selected.value = selected.value.filter((k) => k !== key)
    return
  }
  selected.value = [...selected.value, key]
  if (!cache.value[key]) fetchModel(key)
}

const models = computed(() => sortModels(props.main.models))
const shown = computed(() => sortModels(selected.value).flatMap((k) => (cache.value[k] ? [cache.value[k]] : [])))
const lead = computed(() => shown.value[0] ?? props.main)
const single = computed(() => shown.value.length === 1)

const hourOf = (f: Forecast, i: number) => new Date(new Date(f.start).getTime() + i * 3_600_000)
const extremes = computed(() => {
  const pred = lead.value.pred.slice(0, hours.value)
  const peak = pred.indexOf(Math.max(...pred))
  const low = pred.indexOf(Math.min(...pred))
  return {
    peak: { value: pred[peak], time: hourOf(lead.value, peak) },
    low: { value: pred[low], time: hourOf(lead.value, low) },
  }
})
</script>

<template>
  <div>
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h3 class="text-lg font-bold tracking-tight text-ink">{{ t('forecast.title') }}</h3>
        <p class="mt-1 max-w-xl text-sm text-muted">{{ t('forecast.subtitle') }}</p>
      </div>
      <div class="flex gap-6 text-right">
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

    <!-- горизонт и переключатели -->
    <div class="mt-5 flex flex-wrap items-center gap-x-5 gap-y-3">
      <div class="inline-flex rounded-full border border-line p-0.5" role="radiogroup" :aria-label="t('forecast.horizon')">
        <button
          v-for="h in HORIZONS"
          :key="h"
          role="radio"
          :aria-checked="hours === h"
          class="rounded-full px-3.5 py-1 text-sm transition-colors"
          :class="hours === h ? 'bg-ink text-bg' : 'text-muted hover:text-ink'"
          @click="hours = h"
        >
          {{ t(`forecast.h${h}`) }}
        </button>
      </div>
      <label class="inline-flex cursor-pointer items-center gap-2 text-sm text-muted" :class="single ? '' : 'cursor-not-allowed opacity-50'">
        <input v-model="band" type="checkbox" class="h-4 w-4 accent-primary" :disabled="!single" />
        {{ t('forecast.showBand') }}
      </label>
      <label class="inline-flex cursor-pointer items-center gap-2 text-sm text-muted">
        <input v-model="cams" type="checkbox" class="h-4 w-4 accent-primary" />
        {{ t('forecast.showCams') }}
      </label>
    </div>
    <p v-if="!single" class="mt-2 text-xs text-faint">{{ t('forecast.bandOne') }}</p>

    <!-- модели галочками: у каждой свой закреплённый цвет, можно выбрать несколько -->
    <p class="mt-5 text-sm font-medium text-muted">{{ t('forecast.compare') }}</p>
    <div class="mt-2 flex flex-wrap gap-2" role="group" :aria-label="t('forecast.compare')">
      <button
        v-for="key in models"
        :key="key"
        role="checkbox"
        :aria-checked="selected.includes(key)"
        class="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors"
        :class="selected.includes(key) ? 'border-ink bg-surface-2 text-ink' : 'border-line text-muted hover:border-faint hover:text-ink'"
        @click="toggle(key)"
      >
        <span
          class="flex h-4 w-4 items-center justify-center rounded"
          :style="{ background: selected.includes(key) ? modelColor(key) : 'transparent', boxShadow: `inset 0 0 0 1.5px ${modelColor(key)}` }"
        >
          <Check v-if="selected.includes(key)" class="h-3 w-3 text-white" aria-hidden="true" />
        </span>
        {{ t(`modelNames.${key}`) }}
      </button>
    </div>

    <!-- легенда: у каждой серии своя форма линии, а не только цвет -->
    <ul class="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted">
      <li class="flex items-center gap-2"><span class="h-0.5 w-5 rounded bg-ink" />{{ t('forecast.actual') }}</li>
      <li v-for="f in shown" :key="f.model" class="flex items-center gap-2">
        <span class="h-[3px] w-5 rounded" :style="{ background: modelColor(f.model) }" />{{ t(`modelNames.${f.model}`) }}
      </li>
      <template v-if="band && single">
        <li class="flex items-center gap-2">
          <span class="h-3 w-5 rounded-sm" :style="{ background: `color-mix(in srgb, ${modelColor(lead.model)} 34%, transparent)` }" />
          {{ t('forecast.band80') }}
        </li>
        <li class="flex items-center gap-2">
          <span class="h-3 w-5 rounded-sm" :style="{ background: `color-mix(in srgb, ${modelColor(lead.model)} 14%, transparent)` }" />
          {{ t('forecast.band95') }}
        </li>
      </template>
      <li v-if="cams" class="flex items-center gap-2"><span class="w-5 border-t-2 border-dashed border-muted" />{{ t('forecast.cams') }}</li>
      <li class="flex items-center gap-2 text-faint">{{ t('forecast.bandsNote') }}</li>
    </ul>
    <div class="mt-3">
      <ForecastChart v-if="actual && shown.length" :forecasts="shown" :actual="actual" :hours="hours" :band="band" :cams="cams" />
      <div v-else class="h-80 animate-pulse rounded-2xl bg-surface-2 sm:h-96" />
    </div>

    <!-- те же значения таблицей: для экранного диктора и для тех, кому удобнее цифры -->
    <details class="group mt-4 text-sm">
      <summary class="cursor-pointer font-medium text-muted hover:text-ink">{{ t('forecast.table') }}</summary>
      <div class="mt-3 max-h-80 overflow-auto rounded-2xl border border-line">
        <table class="w-full">
          <thead class="sticky top-0 bg-surface text-left text-xs text-faint uppercase">
            <tr>
              <th class="px-3 py-2 font-semibold">{{ t('forecast.time') }}</th>
              <th class="px-3 py-2 text-right font-semibold">{{ t(`modelNames.${lead.model}`) }}</th>
              <th class="px-3 py-2 text-right font-semibold">{{ t('forecast.band80') }}</th>
              <th class="px-3 py-2 text-right font-semibold">{{ t('forecast.cams') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(v, i) in lead.pred.slice(0, hours)" :key="i" class="border-t border-line/70">
              <td class="px-3 py-1.5 text-muted">{{ formatDateHour(hourOf(lead, i), lang) }}</td>
              <td class="num px-3 py-1.5 text-right text-ink">{{ formatNumber(v, lang) }}</td>
              <td class="num px-3 py-1.5 text-right text-muted">{{ formatNumber(lead.lo80[i], lang) }}–{{ formatNumber(lead.hi80[i], lang) }}</td>
              <td class="num px-3 py-1.5 text-right text-muted">{{ lead.cams[i] == null ? '–' : formatNumber(lead.cams[i] as number, lang) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
    <RecomputePanel class="mt-5" />
  </div>
</template>
