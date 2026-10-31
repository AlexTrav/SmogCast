// порядок моделей на сайте и закреплённые цвета серий (палитра в style.css проверена валидатором dataviz):
// цвет следует за моделью, а не за её местом в рейтинге
export const DEFAULT_MODEL = 'arima+lstm+lstm_weather'

export const MODEL_ORDER = [DEFAULT_MODEL, 'arima', 'lstm_weather', 'lstm', 'prophet', 'profile_7d', 'seasonal_24']

export const MODEL_VAR: Record<string, string> = {
  [DEFAULT_MODEL]: '--series-1',
  arima: '--series-2',
  lstm_weather: '--series-3',
  lstm: '--series-4',
  prophet: '--series-5',
  profile_7d: '--series-6',
  seasonal_24: '--series-7',
}

// модели и смеси, у которых нет своего цвета (базовая «как час назад», запасные смеси, прогноз CAMS) – нейтральные
export const REFERENCE = 'cams'

export function modelColor(key: string): string {
  return `var(${MODEL_VAR[key] ?? '--faint'})`
}

export function sortModels(keys: string[]): string[] {
  const rank = (k: string) => (MODEL_ORDER.includes(k) ? MODEL_ORDER.indexOf(k) : MODEL_ORDER.length)
  return [...keys].sort((a, b) => rank(a) - rank(b))
}
