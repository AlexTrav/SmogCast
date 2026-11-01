import { ref } from 'vue'
import { api, listenServer } from '../api/client'

export type ServerStatus = 'unknown' | 'waking' | 'ready' | 'down'

// одно состояние на весь сайт: плашку обновляет любой запрос к API
const status = ref<ServerStatus>('unknown')
let pending: Promise<void> | null = null
// сервер отвечал недавно – значит, он не спит: один медленный или зависший запрос плашку не включает
const ALIVE_MS = 30_000
let lastOk = 0

listenServer((signal) => {
  if (signal === 'ok') {
    lastOk = Date.now()
    status.value = 'ready'
  } else if (Date.now() - lastOk > ALIVE_MS) {
    status.value = signal === 'slow' ? 'waking' : 'down'
  }
})

export function useServerStatus() {
  // будит API при открытии сайта: бесплатный Render засыпает через 15 минут без запросов
  function wake(): Promise<void> {
    pending ??= api
      .health()
      .then(() => {})
      .catch(() => {})
      .finally(() => {
        pending = null
      })
    return pending
  }
  return { status, wake }
}
