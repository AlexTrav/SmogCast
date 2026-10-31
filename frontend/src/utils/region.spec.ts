import { describe, expect, it } from 'vitest'
import type { Region } from '../types'
import { cellsAt, cellsGeoJSON, hourTime, nowHour } from './region'

const LATS = [42.5, 42.9, 43.3, 43.7, 44.1]
const LONS = [76.1, 76.5, 76.9, 77.3, 77.7]
const grid = (v: (i: number, j: number) => number | null) => [LATS.map((_, i) => LONS.map((_, j) => v(i, j)))]

const REGION = {
  issued_at: '2026-10-31T17:00:00Z', lats: LATS, lons: LONS, start: '2026-10-30T18:00:00Z', step: 'hour', hours: 96,
  pm2_5: grid((i, j) => (i === 0 && j === 0 ? null : 10 * i + j)),
  pm10: grid(() => 1), wind: grid(() => 5), wind_dir: grid(() => 90),
} as Region

describe('сетка для карты', () => {
  it('клетки за час: пустые пропускаются, Алматы – клетка с центром 43,3° / 76,9°', () => {
    const cells = cellsAt(REGION, 0)
    expect(cells).toHaveLength(24)
    expect(cells.filter((c) => c.city).map((c) => [c.lat, c.lon])).toEqual([[43.3, 76.9]])
    expect(cells.find((c) => c.city)).toMatchObject({ pm: 22, level: 'moderate', wind: 5, dir: 90 })
  })

  it('клетка – квадрат 0,4° вокруг узла с цветом уровня', () => {
    const geo = cellsGeoJSON(REGION, 0, { good: 'g', moderate: 'm', sensitive: 's', unhealthy: 'u', very_unhealthy: 'v', hazardous: 'h' })
    const city = geo.features.find((f) => f.properties.city)!
    expect(city.properties.color).toBe('m')
    const ring = city.geometry.coordinates[0]
    expect(ring[0][0]).toBeCloseTo(76.7)
    expect(ring[2][1]).toBeCloseTo(43.5)
  })

  it('час «сейчас» – по времени выпуска, время часа – от начала сетки', () => {
    expect(nowHour(REGION)).toBe(23)
    expect(hourTime(REGION, 23).toISOString()).toBe('2026-10-31T17:00:00.000Z')
  })
})
