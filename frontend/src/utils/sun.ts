import { localDay } from './format'

// восход и закат в Алматы по упрощённым формулам NOAA (точность – около минуты, для неба на сайте хватает):
// склонение солнца и уравнение времени по дню года, часовой угол – для высоты солнца –0,833°
// (рефракция и радиус диска)
const LAT = 43.25
const LON = 76.92
const RAD = Math.PI / 180
const DAY = 86_400_000
// рассвет и закат на небе – 40 минут до и после восхода (заката)
export const TWILIGHT_MS = 40 * 60_000

export type SkyPhase = 'night' | 'dawn' | 'day' | 'dusk'

export function sunTimes(date: Date): { sunrise: Date; sunset: Date } {
  const [y, m, d] = localDay(date).split('-').map(Number) // календарный день – по Алматы
  const base = Date.UTC(y, m - 1, d)
  const n = Math.round((base - Date.UTC(y, 0, 1)) / DAY) + 1
  const g = ((2 * Math.PI) / 365) * (n - 1)
  const eqtime =
    229.18 *
    (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g))
  const decl =
    0.006918 -
    0.399912 * Math.cos(g) +
    0.070257 * Math.sin(g) -
    0.006758 * Math.cos(2 * g) +
    0.000907 * Math.sin(2 * g) -
    0.002697 * Math.cos(3 * g) +
    0.00148 * Math.sin(3 * g)
  const ha =
    Math.acos(Math.cos(90.833 * RAD) / (Math.cos(LAT * RAD) * Math.cos(decl)) - Math.tan(LAT * RAD) * Math.tan(decl)) /
    RAD
  const minutes = (sign: number) => 720 - 4 * (LON + sign * ha) - eqtime // минуты от полуночи UTC
  return { sunrise: new Date(base + minutes(1) * 60_000), sunset: new Date(base + minutes(-1) * 60_000) }
}

export function skyPhase(now: Date): SkyPhase {
  const { sunrise, sunset } = sunTimes(now)
  const t = now.getTime()
  if (Math.abs(t - sunrise.getTime()) <= TWILIGHT_MS) return 'dawn'
  if (Math.abs(t - sunset.getTime()) <= TWILIGHT_MS) return 'dusk'
  return t > sunrise.getTime() && t < sunset.getTime() ? 'day' : 'night'
}
