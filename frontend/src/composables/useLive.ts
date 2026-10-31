import { useIntervalFn } from '@vueuse/core'
import { computed, effectScope, ref } from 'vue'
import { api } from '../api/client'
import type { Status } from '../types'
import { nextRun } from '../utils/format'

const POLL_MS = 60_000
// ежечасная задача стартует в xx:17 UTC и идёт около 3 минут – после этого ждём новый час ряда
const RUN_MINUTES = 4

// живое состояние на весь сайт: последний час ряда, опрос раз в минуту (почти всегда – пустой 304),
// метка «новые данные», когда час сменился
const status = ref<Status | null>(null)
const error = ref<string | null>(null)
const freshHour = ref<string | null>(null) // время нового часа – для уведомления «Новые данные за ЧЧ:00»
let started = false
const now = ref(new Date()) // часы для обратного отсчёта, тикают раз в секунду

async function refresh() {
  try {
    const next = await api.status()
    if (status.value && next.time !== status.value.time) freshHour.value = next.time
    status.value = next
    error.value = null
  } catch (e) {
    error.value = (e as Error).message
  }
}

export function useLive() {
  if (!started) {
    started = true
    refresh()
    // отдельная область: таймеры не должны остановиться, когда уйдёт со страницы первый компонент
    effectScope(true).run(() => {
      useIntervalFn(refresh, POLL_MS)
      useIntervalFn(() => (now.value = new Date()), 1000)
    })
  }
  const minute = computed(() => status.value?.schedule_minute ?? 17)
  const next = computed(() => nextRun(now.value, minute.value))
  // пока задача идёт (xx:17 + 4 мин), показываем «идёт обновление»
  const updating = computed(() => {
    const m = now.value.getUTCMinutes()
    return m >= minute.value && m < minute.value + RUN_MINUTES
  })
  return { status, error, freshHour, now, next, updating, refresh }
}
