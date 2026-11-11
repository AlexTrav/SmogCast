import type {
  DailyHistory,
  Explain,
  Forecast,
  HourlyHistory,
  ModelsReport,
  Performance,
  Recompute,
  Region,
  Status,
  Verify,
  Weather,
} from '../types'

// адрес API: в dev – .env.development, в сборке – аргумент Docker (по умолчанию API на Render)
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'https://smogcast-backend.onrender.com'

// бесплатный Render засыпает через 15 минут без запросов; пробуждение SmogCast по замеру 11.11.2026 – около
// 112 с (контейнер стартует за 2 с, остальное – подготовка машины Render). Ждём с запасом, иначе запрос
// обрывается раньше, чем сервер проснулся
const TIMEOUT_MS = 150_000
// если ответа нет дольше этого – скорее всего, сервер просыпается: показываем плашку
const SLOW_AFTER_MS = 2500
// пока Render будит сервис, его прокси отвечает 502/503/504
const WAKING_STATUSES = new Set([502, 503, 504])

// retryAfter – через сколько секунд можно повторить (ответ 429 у пересчёта)
export class ApiError extends Error {
  code: string
  status: number
  retryAfter: number

  constructor(code: string, status = 0, retryAfter = 0) {
    super(code)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.retryAfter = retryAfter
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
export async function request<T>(path: string, timeoutMs = TIMEOUT_MS, method: 'GET' | 'POST' = 'GET'): Promise<T> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  const slow = setTimeout(() => onServerSignal('slow'), SLOW_AFTER_MS)
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { method, signal: controller.signal, cache: 'no-cache' })
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
  if (res.status === 429) {
    // заголовок Retry-After браузер через CORS не отдаёт – причина и время ожидания есть в теле ответа
    const body = (await res.json().catch(() => null)) as { detail?: { error?: string; retry_after?: number } } | null
    throw new ApiError(body?.detail?.error ?? 'http_429', 429, body?.detail?.retry_after ?? 0)
  }
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
  // весь ряд: по часам (около 50 КБ со сжатием) и по суткам
  allHours: () => request<HourlyHistory>('/api/history?step=hour'),
  days: () => request<DailyHistory>('/api/history?step=day'),
  weather: () => request<Weather>('/api/weather'),
  explain: () => request<Explain>('/api/explain'),
  models: () => request<ModelsReport>('/api/models'),
  verify: (days = 7) => request<Verify>(`/api/verify?days=${days}`),
  performance: (hours = 48) => request<Performance>(`/api/performance?hours=${hours}`),
  // сетка CAMS 5x5 для карты: сутки назад и 3 суток вперёд
  region: () => request<Region>('/api/region'),
  // лёгкие модели заново на сервере; не чаще раза в 30 с (иначе ApiError too_often или busy)
  recompute: () => request<Recompute>('/api/recompute', TIMEOUT_MS, 'POST'),
}
