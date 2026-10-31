import { describe, expect, it } from 'vitest'
import type { Forecast } from '../types'
import { bestWindow, dayOutlook, hoursOf, windows } from './outlook'

// прогноз с 06:00 1 ноября по Алматы (01:00 UTC) на 72 ч; now – 05:30 того же дня
const NOW = new Date('2026-11-01T00:30:00Z')

function forecast(pred: number[]): Forecast {
  return { start: '2026-11-01T01:00:00Z', pred } as Forecast
}

describe('прогноз словами', () => {
  it('сутки по местному времени: сегодня – оставшиеся часы, четвёртые сутки отбрасываются', () => {
    const days = dayOutlook(hoursOf(forecast(Array.from({ length: 72 }, (_, i) => 10 + i))), NOW)
    expect(days.map((d) => [d.offset, d.hours.length])).toEqual([[0, 18], [1, 24], [2, 24]])
    expect(days[0]).toMatchObject({ min: 10, max: 27, level: 'moderate', worst: 'moderate' })
    expect(days[0].best.time.toISOString()).toBe('2026-11-01T01:00:00.000Z')
  })

  it('прогулка – самые чистые 2 часа с 7:00 до 22:00, проветривание – самый чистый час', () => {
    // 06:00 – самый чистый час, но для прогулки рано; 21:00–23:00 чище всего, но позже 22:00
    const pred = Array.from({ length: 72 }, () => 40)
    pred[0] = 3 // 06:00
    pred[7] = 8 // 13:00
    pred[8] = 9 // 14:00
    pred[15] = 1 // 21:00
    pred[16] = 1 // 22:00
    const [today] = dayOutlook(hoursOf(forecast(pred)), NOW)
    const { walk, air } = windows(today)
    expect(walk?.start.toISOString()).toBe('2026-11-01T08:00:00.000Z') // 13:00 по Алматы
    expect(walk?.end.toISOString()).toBe('2026-11-01T10:00:00.000Z')
    expect(walk).toMatchObject({ mean: 8.5, level: 'good' })
    expect(air?.start.toISOString()).toBe('2026-11-01T16:00:00.000Z') // 21:00
  })

  it('окна нет, если в сутках не осталось подходящих часов', () => {
    const late = hoursOf({ start: '2026-11-01T17:00:00Z', pred: [5, 5] } as Forecast) // 22:00 и 23:00
    expect(bestWindow(late, 2, 7, 22)).toBeNull()
    expect(bestWindow(late, 1, 6, 24)?.mean).toBe(5)
  })
})
