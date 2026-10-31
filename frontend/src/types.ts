// ответы API SmogCast (backend/api): время – UTC в ISO 8601, концентрации – мкг/м³
export type AppLocale = 'ru' | 'kk' | 'en'

export type AqiLevel = 'good' | 'moderate' | 'sensitive' | 'unhealthy' | 'very_unhealthy' | 'hazardous'

export interface Status {
  time: string
  pm2_5: number
  pm10: number
  aqi: number
  level: AqiLevel
  change_24h: number | null
  data_run: { at: string; duration_ms: number; status: string; hours_added: number | null } | null
  model_run: { at: string; issued_at: string; duration_ms: number; status: string } | null
  default_model: string
  schedule_minute: number
  timezone: string
}

export interface Forecast {
  issued_at: string
  model: string
  default_model: string
  models: string[]
  start: string
  step: 'hour'
  pred: number[]
  lo80: number[]
  hi80: number[]
  lo95: number[]
  hi95: number[]
  cams: (number | null)[]
}

export interface HourlyHistory {
  start: string | null
  step: 'hour'
  values: Record<string, (number | null)[]>
}

export interface Factor {
  key: 'cold' | 'calm' | 'dry' | 'heating'
  active: boolean
  value: number | null
  threshold: number | null
}

export interface Weather {
  issued_at: string | null
  start: string
  step: 'hour'
  values: Record<string, (number | null)[]>
  factors: Factor[]
}
