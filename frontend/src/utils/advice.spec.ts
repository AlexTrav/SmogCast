import { describe, expect, it } from 'vitest'
import { effective, tips, verdict } from './advice'

describe('советы по уровню', () => {
  it('хорошо и умеренно – можно, вредно для чувствительных – осторожно, хуже – нельзя', () => {
    expect([verdict('good', false), verdict('moderate', false), verdict('sensitive', false), verdict('unhealthy', false)])
      .toEqual(['ok', 'ok', 'caution', 'no'])
  })

  it('чувствительность – строже на одну ступень, но не выше «опасно»', () => {
    expect(verdict('moderate', true)).toBe('caution')
    expect(verdict('sensitive', true)).toBe('no')
    expect(effective('hazardous', true)).toBe(5)
  })

  it('четыре совета по одному уровню', () => {
    expect(tips('unhealthy', false).map((t) => `${t.key}:${t.verdict}`)).toEqual(['sport:no', 'windows:no', 'mask:no', 'purifier:no'])
  })
})
