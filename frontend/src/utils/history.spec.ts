import { describe, expect, it } from 'vitest'
import { formatDate, formatShortDate } from './format'
import { hourIndex, worstWindow } from './history'

describe('история', () => {
  it('эпизод – окно с наибольшим средним, дни с пропуском пропускаются', () => {
    const means = [10, 20, 90, 95, 100, 30, null, 200]
    expect(worstWindow(means, 3)).toEqual({ from: 2, to: 4, mean: 95 })
    expect(worstWindow([1, null], 3)).toBeNull()
  })

  it('индекс часа в почасовом ряду', () => {
    expect(hourIndex('2022-09-01T00:00:00Z', '2022-09-02T05:00:00Z')).toBe(29)
  })

  it('даты с годом по Алматы', () => {
    expect(formatDate('2023-01-15T20:00:00Z', 'ru')).toBe('16 янв. 2023') // 02:00 16 января по UTC+6
    expect(formatDate('2023-01-15T12:00:00Z', 'kk')).toBe('15 қаң. 2023')
    expect(formatShortDate('2023-01-15T12:00:00Z')).toBe('15.01.2023')
  })
})
