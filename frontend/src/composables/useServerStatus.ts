import { ref } from 'vue'
import { api, listenServer } from '../api/client'

export type ServerStatus = 'unknown' | 'waking' | 'ready' | 'down'

// одно состояние на весь сайт: плашку обновляет любой запрос к API
const status = ref<ServerStatus>('unknown')
let pending: Promise<void> | null = null

listenServer((signal) => {
  status.value = signal === 'slow' ? 'waking' : signal === 'ok' ? 'ready' : 'down'
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
