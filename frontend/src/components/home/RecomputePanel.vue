<script setup lang="ts">
import { CircleCheck, Cpu, RefreshCw, TriangleAlert } from 'lucide-vue-next'
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ApiError, api } from '../../api/client'
import type { AppLocale, Recompute } from '../../types'
import { formatHour, formatNumber } from '../../utils/format'
import { modelColor } from '../../utils/models'

// «Пересчитать сейчас»: сервер заново считает быстрые модели от того же часа и возвращает время каждой;
// сервер разрешает нажатие раз в 30 с с адреса – кнопка сама показывает, сколько ждать
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)

const result = ref<Recompute | null>(null)
const running = ref(false)
const problem = ref<'tooOften' | 'busy' | 'failed' | null>(null)
const wait = ref(0)
let timer: ReturnType<typeof setInterval> | undefined

function cooldown(seconds: number) {
  wait.value = seconds
  clearInterval(timer)
  timer = setInterval(() => {
    wait.value = Math.max(0, wait.value - 1)
    if (wait.value === 0) {
      clearInterval(timer)
      if (problem.value === 'tooOften') problem.value = null
    }
  }, 1000)
}
onBeforeUnmount(() => clearInterval(timer))

async function run() {
  running.value = true
  problem.value = null
  try {
    result.value = await api.recompute()
    cooldown(30)
  } catch (err) {
    const code = err instanceof ApiError ? err.code : ''
    problem.value = code === 'too_often' ? 'tooOften' : code === 'busy' ? 'busy' : 'failed'
    if (err instanceof ApiError && err.retryAfter) cooldown(err.retryAfter)
  } finally {
    running.value = false
  }
}

// время по моделям: полоса – доля от самой долгой, чтобы разница «миллисекунды против десятков» была видна
const timings = computed(() => {
  const rows = (result.value?.models ?? []).filter((m) => m.ms != null)
  const max = Math.max(...rows.map((m) => m.ms as number), 1)
  return rows.map((m) => ({ ...m, width: Math.max(2, ((m.ms as number) / max) * 100) }))
})
const modelsMs = computed(() => timings.value.reduce((sum, m) => sum + (m.ms ?? 0), 0))
// наибольшее отличие от ежечасного расчёта среди моделей, которые есть в обоих; null – сравнить не с чем
const diff = computed(() => {
  const values = (result.value?.models ?? []).flatMap((m) => (m.diff == null ? [] : [m.diff]))
  return values.length ? Math.max(...values) : null
})
</script>

<template>
  <div class="rounded-2xl border border-line bg-surface-2/50 p-4 sm:p-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="flex items-start gap-3">
        <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary-strong">
          <Cpu class="h-4.5 w-4.5" aria-hidden="true" />
        </span>
        <div>
          <h3 class="font-semibold text-ink">{{ t('recompute.title') }}</h3>
          <p class="text-sm text-muted">{{ t('recompute.text') }}</p>
        </div>
      </div>
      <button v-ripple class="btn-ghost disabled:cursor-not-allowed disabled:opacity-60" :disabled="running || wait > 0" @click="run">
        <RefreshCw class="h-4 w-4" :class="running ? 'animate-spin' : ''" aria-hidden="true" />
        <span class="num">{{ running ? t('recompute.running') : wait > 0 ? t('recompute.wait', { s: wait }) : t('recompute.button') }}</span>
      </button>
    </div>

    <p v-if="problem" class="mt-3 flex items-center gap-2 text-sm text-ink" role="status">
      <TriangleAlert class="h-4 w-4 shrink-0 text-accent" aria-hidden="true" />
      {{ t(`recompute.${problem}`, { s: wait }) }}
    </p>

    <div v-if="result" class="mt-4 space-y-3" aria-live="polite">
      <p class="text-sm text-ink">
        <span class="font-semibold">{{ t('recompute.done', { s: formatNumber(modelsMs / 1000, lang, 2) }) }}</span>
        <span class="text-muted">, {{ t('recompute.total', { s: formatNumber(result.total_ms / 1000, lang, 2) }) }}</span>
      </p>
      <ul class="space-y-1.5">
        <li v-for="m in timings" :key="m.model" class="grid grid-cols-[minmax(0,9rem)_1fr_4.5rem] items-center gap-3 text-sm">
          <span class="flex items-center gap-2 truncate text-ink">
            <span class="h-2 w-2 shrink-0 rounded-full" :style="{ background: modelColor(m.model) }" />
            <span class="truncate">{{ t(`modelNames.${m.model}`) }}</span>
          </span>
          <span class="h-2 overflow-hidden rounded-full bg-surface">
            <span class="block h-full rounded-full" :style="{ width: `${m.width}%`, background: modelColor(m.model) }" />
          </span>
          <span class="num text-right text-muted">
            {{ m.error ? t('recompute.error') : t('recompute.ms', { n: formatNumber(m.ms as number, lang, 1) }) }}
          </span>
        </li>
      </ul>
      <p v-if="diff != null" class="flex items-center gap-2 text-sm text-ink">
        <CircleCheck class="h-4 w-4 shrink-0 text-aqi-good" aria-hidden="true" />
        {{ diff < 0.05 ? t('recompute.same') : t('recompute.diff', { value: formatNumber(diff, lang) }) }}
      </p>
      <p v-if="result.cached" class="text-sm text-muted">{{ t('recompute.cached', { time: formatHour(result.computed_at, lang) }) }}</p>
      <p class="text-xs leading-relaxed text-faint">{{ t('recompute.heavy') }}</p>
    </div>
  </div>
</template>
