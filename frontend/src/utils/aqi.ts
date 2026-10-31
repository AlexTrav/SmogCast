import type { AqiLevel } from '../types'
import type { SkyPhase } from './sun'

// уровни US AQI по PM2.5 (EPA, 2024) – верхние границы включительно, как в backend/api/levels.py
export const LEVELS: { key: AqiLevel; upTo: number }[] = [
  { key: 'good', upTo: 9.0 },
  { key: 'moderate', upTo: 35.4 },
  { key: 'sensitive', upTo: 55.4 },
  { key: 'unhealthy', upTo: 125.4 },
  { key: 'very_unhealthy', upTo: 225.4 },
  { key: 'hazardous', upTo: Infinity },
]

export const WHO_24H = 15 // суточная норма ВОЗ, мкг/м³

// индекс US AQI 0–500 по концентрации: линейно внутри отрезка EPA, как в backend/api/levels.py
const BREAKPOINTS: [number, number, number, number][] = [
  [0.0, 9.0, 0, 50],
  [9.1, 35.4, 51, 100],
  [35.5, 55.4, 101, 150],
  [55.5, 125.4, 151, 200],
  [125.5, 225.4, 201, 300],
  [225.5, 325.4, 301, 500],
]

export function aqiOf(pm: number): number {
  const c = Math.floor(Math.max(pm, 0) * 10) / 10
  const row = BREAKPOINTS.find(([, hi]) => c <= hi)
  if (!row) return 500
  const [cLo, cHi, iLo, iHi] = row
  return Math.round(((iHi - iLo) / (cHi - cLo)) * (c - cLo) + iLo)
}

export function levelOf(pm: number): AqiLevel {
  const c = Math.floor(Math.max(pm, 0) * 10) / 10 // EPA усекает концентрацию до 0,1
  return LEVELS.find((l) => c <= l.upTo)!.key
}

// положение значения на шкале из шести равных отрезков (0…1): внутри отрезка – пропорционально концентрации
export function scalePosition(pm: number): number {
  let low = 0
  for (const [i, l] of LEVELS.entries()) {
    const high = Number.isFinite(l.upTo) ? l.upTo : 500
    if (pm <= high || i === LEVELS.length - 1) {
      const inside = Math.min(1, Math.max(0, (pm - low) / (high - low)))
      return (i + inside) / LEVELS.length
    }
    low = high
  }
  return 1
}

export const LEVEL_COLOR: Record<AqiLevel, string> = {
  good: 'var(--color-aqi-good)',
  moderate: 'var(--color-aqi-moderate)',
  sensitive: 'var(--color-aqi-sensitive)',
  unhealthy: 'var(--color-aqi-unhealthy)',
  very_unhealthy: 'var(--color-aqi-very-unhealthy)',
  hazardous: 'var(--color-aqi-hazardous)',
}

// небо над горами: верх, середина и горизонт; чем грязнее воздух, тем серее и желтее небо
export type Sky = [string, string, string]
const DAY: Record<AqiLevel, Sky> = {
  good: ['#1e6fd9', '#5ea8f0', '#cfe7ff'],
  moderate: ['#3f7bc4', '#8cb4dc', '#ebddb8'],
  sensitive: ['#5f7fa3', '#a9a9a0', '#edc48e'],
  unhealthy: ['#6f7380', '#b09a84', '#e3a56e'],
  very_unhealthy: ['#5e5560', '#9c7a6b', '#cf8a5a'],
  hazardous: ['#3f3438', '#7a5546', '#b26a44'],
}
const NIGHT: Record<AqiLevel, Sky> = {
  good: ['#050b1a', '#0e2547', '#23477a'],
  moderate: ['#070c18', '#1b2740', '#4a4a55'],
  sensitive: ['#0a0c14', '#262a38', '#5c4e48'],
  unhealthy: ['#0c0b10', '#2e2a30', '#6a5040'],
  very_unhealthy: ['#0e0a0d', '#33272a', '#6e4636'],
  hazardous: ['#0f0809', '#36201f', '#6b3a2a'],
}

// рассвет и закат: синевато-лиловый верх, розовая середина и оранжевый горизонт, при смоге – грязнее
const TWILIGHT: Record<AqiLevel, Sky> = {
  good: ['#2b3a67', '#c97b8b', '#f6b26b'],
  moderate: ['#33395a', '#b88482', '#eeb27a'],
  sensitive: ['#3a3a52', '#a88478', '#e2a874'],
  unhealthy: ['#3c3640', '#9a7a6a', '#d59a66'],
  very_unhealthy: ['#352c30', '#86665a', '#c07f55'],
  hazardous: ['#2a2022', '#6b4a3e', '#a0603e'],
}

export function skyColors(level: AqiLevel, phase: SkyPhase): Sky {
  return (phase === 'day' ? DAY : phase === 'night' ? NIGHT : TWILIGHT)[level]
}

// плотность дымки 0…0,6: почти нет при чистом воздухе, горы тонут в ней при сильном смоге
export function hazeOpacity(pm: number): number {
  return Math.min(0.6, Math.max(0, (pm - 5) / 160))
}
