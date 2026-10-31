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

export interface Explain {
  issued_at: string
  start: string
  step: 'hour'
  prophet: {
    level: number[]
    daily: number[]
    yearly: number[]
    summary: {
      level: number
      yearly: number
      daily_low: { hour: number; factor: number }
      daily_high: { hour: number; factor: number }
    }
  } | null
  blend: { model: string; pred: number[]; parts: Record<string, number[]> }
  weather: { ratio: (number | null)[]; mean_24h: number } | null
}

// итоги честной проверки (model/reports/final): горизонты сгруппированы по суткам
export type Bucket = '1–24' | '25–48' | '49–72'

export interface BucketMetrics {
  mae: number
  rmse: number
  smape: number
  cover80: number
  width80: number
  cover95: number
  width95: number
  skill: number
}

export interface AqiScores {
  level_exact: number
  level_within_one: number
  smog_hours: number
  smog_caught: number
  false_alarms: number
}

export interface ModelsReport {
  selection: {
    default: string
    rule: string
    chosen_at: string
    ranking: { key: string; name: string; mae_1_72: number }[]
  }
  test: {
    meta: { period: string; start: string; default: string; intervals: string }
    models: Record<string, { name: string; mae_1_72: number; origins: number; buckets: Record<Bucket, BucketMetrics> }>
    dm_vs_default: Record<string, Record<Bucket, { mae_diff: number; dm: number; p_value: number }>>
    aqi: Record<string, Record<Bucket, AqiScores>>
    mae_by_horizon: Record<string, number[]>
    confusion_24h: number[][]
  }
}

// живой журнал «прогноз -> факт» за последние сутки (/api/verify)
export interface Verify {
  days: number
  default_model: string
  dates: string[]
  models: Record<string, { mae: number | null; hours: number; buckets: Record<Bucket, number | null>; daily: (number | null)[] }>
  yesterday: { issued_at: string; start: string; step: 'hour'; pred: number[]; lo80: number[]; hi80: number[]; actual: (number | null)[] } | null
}

export interface DailyHistory {
  start: string | null // первый день (местное время Алматы), YYYY-MM-DD
  step: 'day'
  timezone: string
  hours: number[]
  values: Record<string, { mean: (number | null)[]; max: (number | null)[] }>
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
