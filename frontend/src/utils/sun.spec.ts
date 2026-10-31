import { describe, expect, it } from 'vitest'
import { formatHour } from './format'
import { skyPhase, sunTimes } from './sun'

const minutes = (d: Date) => {
  const [h, m] = formatHour(d, 'ru').split(':').map(Number)
  return h * 60 + m
}

describe('восход и закат в Алматы', () => {
  // с 01.03.2024 Алматы – UTC+5, поэтому солнце встаёт на час «раньше», чем по прежнему UTC+6
  it('1 ноября: восход около 06:30, закат около 16:45 по Алматы', () => {
    const { sunrise, sunset } = sunTimes(new Date('2026-11-01T06:00:00Z'))
    expect(Math.abs(minutes(sunrise) - (6 * 60 + 30))).toBeLessThan(15)
    expect(Math.abs(minutes(sunset) - (16 * 60 + 45))).toBeLessThan(15)
  })

  it('летом день длиннее, чем зимой, а солнечный полдень – около 12:00', () => {
    const length = (iso: string) => {
      const { sunrise, sunset } = sunTimes(new Date(iso))
      return sunset.getTime() - sunrise.getTime()
    }
    expect(length('2026-06-21T06:00:00Z') / 3_600_000).toBeGreaterThan(15)
    expect(length('2026-12-21T06:00:00Z') / 3_600_000).toBeLessThan(9.5)
    const { sunrise, sunset } = sunTimes(new Date('2026-03-20T06:00:00Z'))
    const noon = minutes(new Date((sunrise.getTime() + sunset.getTime()) / 2))
    expect(Math.abs(noon - 12 * 60)).toBeLessThan(30)
  })

  it('фазы неба по времени суток', () => {
    const { sunrise, sunset } = sunTimes(new Date('2026-11-01T06:00:00Z'))
    expect(skyPhase(new Date(sunrise.getTime() - 3 * 3_600_000))).toBe('night')
    expect(skyPhase(new Date(sunrise.getTime() + 10 * 60_000))).toBe('dawn')
    expect(skyPhase(new Date(sunrise.getTime() + 3 * 3_600_000))).toBe('day')
    expect(skyPhase(new Date(sunset.getTime() - 10 * 60_000))).toBe('dusk')
    expect(skyPhase(new Date(sunset.getTime() + 3 * 3_600_000))).toBe('night')
  })
})
