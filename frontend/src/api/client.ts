import type { Explain, Forecast, HourlyHistory, Status, Weather } from '../types'

// адрес API: в dev – .env.development, в сборке – аргумент Docker (по умолчанию API на Render)
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'https://smogcast-backend.onrender.com'

// бесплатный Render засыпает и просыпается около минуты – ждём дольше обычного
const TIMEOUT_MS = 75_000
// если ответа нет дольше этого – скорее всего, сервер просыпается: показываем плашку
const SLOW_AFTER_MS = 2500
// пока Render будит сервис, его прокси отвечает 502/503/504
const WAKING_STATUSES = new Set([502, 503, 504])

export class ApiError extends Error {
  code: string
  status: number

  constructor(code: string, status = 0) {
    super(code)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

// каждый запрос сообщает, в каком состоянии сервер: плашка «Сервер просыпается…» видна на любой странице
export type ServerSignal = 'slow' | 'ok' | 'fail'
let onServerSignal: (signal: ServerSignal) => void = () => {}
export function listenServer(listener: (signal: ServerSignal) => void) {
  onServerSignal = listener
}

// cache: 'no-cache' – браузер переспрашивает сервер с If-None-Match и, пока данные те же, получает пустой 304,
// а тело берёт из своего кэша: опрос раз в минуту почти ничего не стоит
export async function request<T>(path: string, timeoutMs = TIMEOUT_MS): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  const slow = setTimeout(() => onServerSignal('slow'), SLOW_AFTER_MS)
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { signal: controller.signal, cache: 'no-cache' })
  } catch (err) {
    onServerSignal('fail')
    throw new ApiError((err as Error).name === 'AbortError' ? 'timeout' : 'network')
  } finally {
    clearTimeout(timer)
    clearTimeout(slow)
  }
  if (WAKING_STATUSES.has(res.status)) {
    onServerSignal('fail')
    throw new ApiError('waking', res.status)
  }
  onServerSignal('ok') // сервер ответил – даже ошибкой 4xx, значит, он не спит
  if (!res.ok) throw new ApiError(`http_${res.status}`, res.status)
  return res.json() as Promise<T>
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),
  status: () => request<Status>('/api/status'),
  forecast: (model?: string) =>
    request<Forecast>(`/api/forecast${model ? `?model=${encodeURIComponent(model)}` : ''}`),
  // часы ряда за дни from..to (местное время Алматы, YYYY-MM-DD)
  hours: (from: string, to: string, fields = 'pm2_5') =>
    request<HourlyHistory>(`/api/history?step=hour&from=${from}&to=${to}&fields=${fields}`),
  weather: () => request<Weather>('/api/weather'),
  explain: () => request<Explain>('/api/explain'),
}
