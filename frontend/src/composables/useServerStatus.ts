import { ref } from 'vue'
import { api, listenServer } from '../api/client'

export type ServerStatus = 'unknown' | 'waking' | 'ready' | 'down'

// одно состояние на весь сайт: плашку обновляет любой запрос к API
const status = ref<ServerStatus>('unknown')
// растёт, когда сервер ответил после сна или сбоя: страница по нему заново загружает свои данные
const epoch = ref(0)
let pending: Promise<void> | null = null
let waking = false // идёт пробуждение – неудачные запросы ещё не значат, что сервер недоступен
// сервер отвечал недавно – значит, он не спит: один медленный или зависший запрос плашку не включает
const ALIVE_MS = 30_000
// будим не дольше 5 минут: обычное пробуждение бесплатного Render – до ~2 минут
const WAKE_LIMIT_MS = 300_000
const WAKE_PAUSE_MS = 3000
let lastOk = 0

listenServer((signal) => {
  if (signal === 'ok') {
    if (status.value === 'waking' || status.value === 'down') epoch.value++
    lastOk = Date.now()
    status.value = 'ready'
  } else if (Date.now() - lastOk > ALIVE_MS) {
    status.value = signal === 'slow' || waking ? 'waking' : 'down'
  }
})

export function useServerStatus() {
  // будит API при открытии сайта и стучится, пока он не ответит: бесплатный Render засыпает через 15 минут
  // без запросов, а пробуждение может занять больше, чем ждёт один запрос
  function wake(): Promise<void> {
    pending ??= (async () => {
      waking = true
      const until = Date.now() + WAKE_LIMIT_MS
      try {
        for (;;) {
          try {
            await api.health()
            return
          } catch {
            if (Date.now() > until) {
              status.value = 'down'
              return
            }
            await new Promise((resolve) => setTimeout(resolve, WAKE_PAUSE_MS))
          }
        }
      } finally {
        waking = false
        pending = null
      }
    })()
    return pending
  }
  return { status, epoch, wake }
}
