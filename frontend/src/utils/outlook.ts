import type { AqiLevel, Forecast } from '../types'
import { levelOf } from './aqi'
import { localDay, localHour } from './format'

// прогноз простыми словами: часы прогноза по суткам Алматы и самые чистые окна для прогулки и проветривания

const HOUR = 3_600_000

export interface HourPoint {
  time: Date
  pm: number
  level: AqiLevel
}

export interface DayOutlook {
  offset: number // 0 – сегодня, 1 – завтра, 2 – послезавтра
  date: Date
  hours: HourPoint[]
  min: number
  max: number
  level: AqiLevel // по среднему за сутки – «какой будет день»
  worst: AqiLevel // по самому грязному часу – для совета
  peak: HourPoint
  best: HourPoint
}

export interface Window {
  start: Date
  end: Date
  mean: number
  level: AqiLevel
}

export function hoursOf(f: Forecast): HourPoint[] {
  const t0 = new Date(f.start).getTime()
  return f.pred.map((pm, i) => ({ time: new Date(t0 + i * HOUR), pm, level: levelOf(pm) }))
}

// сутки сегодня, завтра и послезавтра по местному времени; сегодня – оставшиеся часы
export function dayOutlook(points: HourPoint[], now: Date): DayOutlook[] {
  const days = [0, 1, 2].map((offset) => ({ offset, key: localDay(now, offset) }))
  return days.flatMap(({ offset, key }) => {
    const hours = points.filter((p) => localDay(p.time) === key)
    if (!hours.length) return []
    const values = hours.map((h) => h.pm)
    const mean = values.reduce((a, b) => a + b, 0) / values.length
    const peak = hours.reduce((a, b) => (b.pm > a.pm ? b : a))
    const best = hours.reduce((a, b) => (b.pm < a.pm ? b : a))
    return [{
      offset, date: hours[0].time, hours, min: best.pm, max: peak.pm,
      level: levelOf(mean), worst: peak.level, peak, best,
    }]
  })
}

// самое чистое окно из length часов подряд, целиком внутри [from, to) по местному времени тех же суток
export function bestWindow(hours: HourPoint[], length: number, from: number, to: number): Window | null {
  let best: Window | null = null
  for (let i = 0; i + length <= hours.length; i++) {
    const part = hours.slice(i, i + length)
    const inside = part.every((h, k) => {
      const hour = localHour(h.time)
      return hour >= from && hour + 1 <= to && (k === 0 || h.time.getTime() - part[k - 1].time.getTime() === HOUR)
    })
    if (!inside) continue
    const mean = part.reduce((a, h) => a + h.pm, 0) / length
    if (!best || mean < best.mean) {
      best = { start: part[0].time, end: new Date(part[length - 1].time.getTime() + HOUR), mean, level: levelOf(mean) }
    }
  }
  return best
}

// прогулка – 2 часа подряд с 7:00 до 22:00, проветривание – самый чистый час с 6:00 до полуночи
export const WALK = { length: 2, from: 7, to: 22 }
export const AIR = { length: 1, from: 6, to: 24 }

export function windows(day: DayOutlook): { walk: Window | null; air: Window | null } {
  return {
    walk: bestWindow(day.hours, WALK.length, WALK.from, WALK.to),
    air: bestWindow(day.hours, AIR.length, AIR.from, AIR.to),
  }
}
