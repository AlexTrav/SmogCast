import { describe, expect, it } from 'vitest'
import { aqiOf, hazeOpacity, levelOf, skyColors } from './aqi'
import { countdown, formatDateHour, formatHour, formatNumber, localDay, localHour, nextRun } from './format'

describe('уровни US AQI', () => {
  it('совпадают с порогами EPA 2024 и бэкендом', () => {
    expect([0, 9.0, 9.1, 35.4, 35.5, 55.4, 55.5, 125.4, 125.5, 225.4, 225.5].map(levelOf)).toEqual([
      'good', 'good', 'moderate', 'moderate', 'sensitive', 'sensitive', 'unhealthy', 'unhealthy',
      'very_unhealthy', 'very_unhealthy', 'hazardous',
    ])
  })

  it('индекс AQI совпадает с EPA и бэкендом', () => {
    expect([0, 9.0, 9.1, 35.4, 35.5, 55.4, 125.4, 225.4, 325.4, 600].map(aqiOf)).toEqual([
      0, 50, 51, 100, 101, 150, 200, 300, 500, 500,
    ])
  })

  it('усекают концентрацию до 0,1, а не округляют', () => {
    expect(levelOf(9.09)).toBe('good')
  })

  it('дымка растёт с PM2.5 и ограничена', () => {
    expect(hazeOpacity(3)).toBe(0)
    expect(hazeOpacity(45)).toBeGreaterThan(hazeOpacity(20))
    expect(hazeOpacity(900)).toBe(0.6)
  })

  it('у каждого уровня своё небо днём и ночью', () => {
    expect(skyColors('good', false)).not.toEqual(skyColors('good', true))
    expect(skyColors('good', false)).not.toEqual(skyColors('hazardous', false))
  })
})

describe('форматирование', () => {
  it('числа с запятой по-русски и по-казахски, с точкой по-английски', () => {
    expect(formatNumber(48.9, 'ru')).toBe('48,9')
    expect(formatNumber(48.9, 'kk')).toBe('48,9')
    expect(formatNumber(48.9, 'en')).toBe('48.9')
  })

  it('время – 24-часовое, месяцы по-казахски свои, не зависят от браузера', () => {
    const t = '2026-11-01T16:00:00Z' // 21:00 1 ноября по Алматы
    expect(formatHour(t, 'en')).toBe('21:00')
    expect(formatDateHour(t, 'kk')).toBe('1 қар., 21:00')
    expect(formatDateHour(t, 'ru')).toBe('1 нояб., 21:00')
    expect(formatDateHour(t, 'en')).toBe('1 Nov, 21:00')
  })

  it('день и час – по Алматы (UTC+5)', () => {
    const late = new Date('2026-10-31T20:30:00Z') // 01:30 1 ноября по Алматы
    expect(localDay(late)).toBe('2026-11-01')
    expect(localDay(late, -2)).toBe('2026-10-30')
    expect(localHour(late)).toBe(1)
  })

  it('следующий запуск – ближайшее xx:17 UTC', () => {
    expect(nextRun(new Date('2026-10-31T16:05:00Z'), 17).toISOString()).toBe('2026-10-31T16:17:00.000Z')
    expect(nextRun(new Date('2026-10-31T16:17:00Z'), 17).toISOString()).toBe('2026-10-31T17:17:00.000Z')
    expect(nextRun(new Date('2026-10-31T23:40:00Z'), 17).toISOString()).toBe('2026-11-01T00:17:00.000Z')
  })

  it('обратный отсчёт – мм:сс', () => {
    expect(countdown(754_000)).toBe('12:34')
    expect(countdown(-5)).toBe('0:00')
  })
})
