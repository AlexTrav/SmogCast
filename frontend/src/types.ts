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
  // погода того же часа: °C, %, км/ч, откуда дует (°)
  weather: { temp: number | null; rh: number | null; wind: number | null; wind_dir: number | null }
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

// производительность системы (/api/performance): ежечасные запуски и скорость самого API
export interface Stats {
  p50: number
  p95: number
  max: number
}

export interface Performance {
  data_runs: { at: string; duration_ms: number; status: string; hours_added: number | null; lag_min: number | null; db_mb: number | null; cleaned_rows: number | null; snapshot_rows: number }[]
  model_runs: { at: string; issued_at: string; duration_ms: number; model_ms: Record<string, number>; status: string }[]
  summary: {
    data_ms: Stats | null
    models_ms: Stats | null
    model_ms: Record<string, Stats>
    success: number | null
    hours_with_run_7d: number
    hours_expected_7d: number
    db_mb: number | null
  }
  api: {
    started_at: string
    uptime_s: number
    paths: Record<string, { requests: number; p50_ms: number; p95_ms: number; max_ms: number; not_modified: number }>
  }
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

// кнопка «Пересчитать сейчас»: лёгкие модели заново от того же часа ряда; ms – время расчёта модели,
// load_ms – её загрузки (чтение ONNX),
// diff – наибольшее отличие от ежечасного расчёта (мкг/м³), cached – этот час уже пересчитывали
export interface RecomputeModel {
  model: string
  ms: number | null
  load_ms: number | null
  diff: number | null
  error: string | null
  pred: number[] | null
}

export interface Recompute {
  issued_at: string
  computed_at: string
  total_ms: number
  cached: boolean
  reused: string[]
  skipped: string[]
  models: RecomputeModel[]
}

// сетка CAMS 5x5 вокруг Алматы для карты: значения [час][широта][долгота], широты и долготы по возрастанию
export interface Region {
  issued_at: string
  lats: number[]
  lons: number[]
  start: string
  step: 'hour'
  hours: number
  pm2_5: (number | null)[][][]
  pm10: (number | null)[][][]
  wind: (number | null)[][][]
  wind_dir: (number | null)[][][]
}
