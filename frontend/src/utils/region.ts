import type { AqiLevel, Region } from '../types'
import { levelOf } from './aqi'

// сетка CAMS для карты: узел – центр клетки 0,4° × 0,4°; клетка Алматы – та, в которую попадает центр города

export const CITY: [number, number] = [76.889, 43.238] // долгота, широта
const HOUR = 3_600_000

export interface Cell {
  lat: number
  lon: number
  pm: number
  level: AqiLevel
  wind: number | null
  dir: number | null
  city: boolean
}

export function half(values: number[]): number {
  return values.length > 1 ? (values[1] - values[0]) / 2 : 0.2
}

// клетки за час hour (пустые значения пропускаются)
export function cellsAt(r: Region, hour: number): Cell[] {
  const dLat = half(r.lats)
  const dLon = half(r.lons)
  return r.lats.flatMap((lat, i) =>
    r.lons.flatMap((lon, j) => {
      const pm = r.pm2_5[hour]?.[i]?.[j]
      if (pm == null) return []
      const city = Math.abs(CITY[1] - lat) <= dLat && Math.abs(CITY[0] - lon) <= dLon
      return [{ lat, lon, pm, level: levelOf(pm), wind: r.wind[hour]?.[i]?.[j] ?? null, dir: r.wind_dir[hour]?.[i]?.[j] ?? null, city }]
    }),
  )
}

// клетки – многоугольниками GeoJSON для заливки на карте; цвет уровня – в свойствах
export function cellsGeoJSON(r: Region, hour: number, colors: Record<AqiLevel, string>) {
  const dLat = half(r.lats)
  const dLon = half(r.lons)
  return {
    type: 'FeatureCollection' as const,
    features: cellsAt(r, hour).map((c) => ({
      type: 'Feature' as const,
      properties: { pm: c.pm, level: c.level, color: colors[c.level], city: c.city },
      geometry: {
        type: 'Polygon' as const,
        coordinates: [[
          [c.lon - dLon, c.lat - dLat], [c.lon + dLon, c.lat - dLat], [c.lon + dLon, c.lat + dLat],
          [c.lon - dLon, c.lat + dLat], [c.lon - dLon, c.lat - dLat],
        ]],
      },
    })),
  }
}

export function hourTime(r: Region, hour: number): Date {
  return new Date(new Date(r.start).getTime() + hour * HOUR)
}

// номер часа «сейчас» – последний час, по которому уже есть данные ряда (issued_at)
export function nowHour(r: Region): number {
  const i = Math.round((new Date(r.issued_at).getTime() - new Date(r.start).getTime()) / HOUR)
  return Math.min(Math.max(i, 0), r.hours - 1)
}
