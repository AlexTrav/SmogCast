import { computed, ref } from 'vue'
import { ApiError, api } from '../api/client'
import type { Recompute } from '../types'
import { useLive } from './useLive'

// «Пересчитать прогноз»: сервер заново считает быстрые модели от последнего часа ряда (POST /api/recompute),
// а сайт заодно перечитывает свежее состояние. Новые данные приходят раз в час, поэтому цифра до нового
// часа не меняется – кнопка показывает, что расчёт живой, быстрый и воспроизводимый; сервер разрешает нажатие раз в 30 с с адреса –
// кнопка сама показывает, сколько ждать. Состояние общее: результат не пропадает при переходах по сайту
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

export function useRecompute() {
  const { refresh } = useLive()

  async function run() {
    running.value = true
    problem.value = null
    try {
      const [answer] = await Promise.all([api.recompute(), refresh()])
      result.value = answer
      cooldown(30)
    } catch (err) {
      const code = err instanceof ApiError ? err.code : ''
      problem.value = code === 'too_often' ? 'tooOften' : code === 'busy' ? 'busy' : 'failed'
      if (err instanceof ApiError && err.retryAfter) cooldown(err.retryAfter)
    } finally {
      running.value = false
    }
  }

  // плашка закрывается всегда; сколько ждать до следующего нажатия, видно на самой кнопке
  function close() {
    result.value = null
    problem.value = null
  }

  // время расчёта моделей без загрузки; наибольшее отличие от ежечасного расчёта (null – сравнить не с чем)
  const modelsMs = computed(() => (result.value?.models ?? []).reduce((sum, m) => sum + (m.ms ?? 0), 0))
  const diff = computed(() => {
    const values = (result.value?.models ?? []).flatMap((m) => (m.diff == null ? [] : [m.diff]))
    return values.length ? Math.max(...values) : null
  })

  return { result, running, problem, wait, run, close, modelsMs, diff }
}
