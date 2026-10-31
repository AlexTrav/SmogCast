import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test as base, expect, type Page } from '@playwright/test'

// общее для всех тестов: подмена API сохранёнными ответами (fixtures/ – снимок настоящего API за один час),
// закреплённые часы браузера и настройки сайта в localStorage (тема, язык, пройдена ли экскурсия)

const FIXTURES = join(dirname(fileURLToPath(import.meta.url)), '..', 'fixtures')
const API = 'http://api.test'
const HOUR = 3_600_000
// «сейчас» – через 40 минут после последнего часа данных в фикстурах (00:40 по Алматы 1 ноября)
export const NOW = new Date('2026-10-31T19:40:00Z')

const cache = new Map<string, unknown>()
export function fixture<T = any>(name: string): T {
  if (!cache.has(name)) cache.set(name, JSON.parse(readFileSync(join(FIXTURES, `${name}.json`), 'utf-8')))
  return structuredClone(cache.get(name)) as T
}

const iso = (ms: number) => new Date(ms).toISOString().replace('.000Z', 'Z')

// часы ряда за дни from..to по местному времени Алматы (UTC+5) – вырезаются из всего ряда
function hours(from: string | null, to: string | null) {
  const all = fixture('all-hours')
  if (!from || !to) return all
  const start = Date.parse(all.start)
  const i0 = Math.max(0, (Date.parse(`${from}T00:00:00+05:00`) - start) / HOUR)
  const i1 = (Date.parse(`${to}T00:00:00+05:00`) + 24 * HOUR - start) / HOUR
  return { start: iso(start + i0 * HOUR), step: 'hour', values: { pm2_5: all.values.pm2_5.slice(i0, i1) } }
}

function forecast(model: string | null) {
  const main = fixture('forecast')
  if (!model || model === main.model) return main
  try {
    return fixture(`forecast-${model}`)
  } catch {
    return { ...main, model } // для моделей без своего снимка – прогноз смеси под их именем
  }
}

export interface Setup {
  theme?: 'light' | 'dark'
  locale?: 'ru' | 'kk' | 'en'
  tour?: boolean // показать экскурсию первого визита
  calm?: boolean // «уменьшить движение»: без анимаций (по умолчанию – тесты проверяют суть, а не анимации)
  frozen?: boolean // часы стоят (для скриншотов: отсчёт до обновления не меняется); иначе идут от NOW
}

export async function prepare(
  page: Page,
  { theme = 'light', locale = 'ru', tour = false, calm = true, frozen = false }: Setup = {},
) {
  let recomputes = 0
  await page.route(`${API}/**`, async (route) => {
    const url = new URL(route.request().url())
    const q = url.searchParams
    const json = (body: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
    switch (url.pathname) {
      case '/api/health': return json({ status: 'ok' })
      case '/api/status': return json(fixture('status'))
      case '/api/forecast': return json(forecast(q.get('model')))
      case '/api/history': return json(q.get('step') === 'day' ? fixture('days') : hours(q.get('from'), q.get('to')))
      case '/api/weather': return json(fixture('weather'))
      case '/api/explain': return json(fixture('explain'))
      case '/api/models': return json(fixture('models'))
      case '/api/verify': return json(fixture('verify'))
      case '/api/performance': return json(fixture('performance'))
      case '/api/region': return json(fixture('region'))
      case '/api/recompute':
        // первое нажатие – результат пересчёта, повторное – сервер просит подождать, как настоящий
        return recomputes++ === 0 ? json(fixture('recompute')) : json({ detail: { error: 'too_often', retry_after: 28 } }, 429)
      default: return json({ detail: 'not found' }, 404)
    }
  })
  // карта: подложка CARTO – пустой стиль, плитки рельефа не нужны (тесты без внешней сети)
  await page.route('https://basemaps.cartocdn.com/**', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify({ version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': '#e8eef5' } }] }) }),
  )
  await page.route('https://s3.amazonaws.com/**', (route) => route.abort())
  // замороженные часы останавливают и таймеры страницы – поэтому только для скриншотов
  if (frozen) await page.clock.setFixedTime(NOW)
  else {
    await page.clock.install({ time: NOW })
    await page.clock.resume()
  }
  if (calm) await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.addInitScript(([th, lo, tr]) => {
    localStorage.setItem('smogcast-theme', th as string)
    localStorage.setItem('smogcast-locale', lo as string)
    if (!tr) localStorage.setItem('smogcast-tour', 'done')
  }, [theme, locale, tour] as const)
}

// ошибки страницы собираются – тест падает, если на странице было исключение JavaScript
export const test = base.extend<{ errors: string[] }>({
  errors: async ({ page }, use) => {
    const errors: string[] = []
    page.on('pageerror', (e) => errors.push(e.message))
    await use(errors)
    expect(errors, 'исключения JavaScript на странице').toEqual([])
  },
})
export { expect }
