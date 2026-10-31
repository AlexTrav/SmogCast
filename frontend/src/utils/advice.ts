import type { AqiLevel } from '../types'
import { LEVELS } from './aqi'

// советы по уровню воздуха, как в приложениях о качестве воздуха: спорт, окна, маска, очиститель и вывод на день.
// «У меня чувствительность» делает всё строже на одну ступень уровня (для детей, пожилых, астмы и болезней сердца)

export type Verdict = 'ok' | 'caution' | 'no'
export type Tip = 'sport' | 'windows' | 'mask' | 'purifier'
export const TIPS: Tip[] = ['sport', 'windows', 'mask', 'purifier']

// номер уровня 0 («хорошо») … 5 («опасно») с поправкой на чувствительность
export function effective(level: AqiLevel, sensitive: boolean): number {
  const index = LEVELS.findIndex((l) => l.key === level)
  return Math.min(LEVELS.length - 1, index + (sensitive ? 1 : 0))
}

// хорошо и умеренно – можно; «вредно для чувствительных» – осторожно; вредно и хуже – нельзя
export function verdict(level: AqiLevel, sensitive: boolean): Verdict {
  const e = effective(level, sensitive)
  return e <= 1 ? 'ok' : e === 2 ? 'caution' : 'no'
}

export function tips(level: AqiLevel, sensitive: boolean): { key: Tip; verdict: Verdict }[] {
  const v = verdict(level, sensitive)
  return TIPS.map((key) => ({ key, verdict: v }))
}
