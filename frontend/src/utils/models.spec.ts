import { describe, expect, it } from 'vitest'
import { DEFAULT_MODEL, modelColor, sortModels } from './models'

describe('модели на сайте', () => {
  it('смесь по умолчанию первой, дальше – закреплённый порядок, незнакомые – в конце', () => {
    expect(sortModels(['prophet', 'new_model', 'arima', DEFAULT_MODEL])).toEqual([DEFAULT_MODEL, 'arima', 'prophet', 'new_model'])
  })

  it('цвет следует за моделью, а не за её местом', () => {
    expect(modelColor('arima')).toBe('var(--series-2)')
    expect(modelColor(DEFAULT_MODEL)).toBe('var(--series-1)')
    expect(modelColor('unknown')).toBe('var(--faint)')
  })
})
