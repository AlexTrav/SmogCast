import type { AppLocale } from '../types'

const TAGS: Record<AppLocale, string> = { ru: 'ru-RU', kk: 'kk-KZ', en: 'en-GB' }
export const TZ = 'Asia/Almaty'

export function formatNumber(value: number, locale: AppLocale, digits = 1): string {
  return new Intl.NumberFormat(TAGS[locale], { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(
    value,
  )
}

// время по Алматы: «20:00»
export function formatHour(iso: string | Date, locale: AppLocale): string {
  return new Intl.DateTimeFormat(TAGS[locale], { hour: '2-digit', minute: '2-digit', timeZone: TZ }).format(
    new Date(iso),
  )
}

// «31 окт., 20:00»
export function formatDateHour(iso: string | Date, locale: AppLocale): string {
  return new Intl.DateTimeFormat(TAGS[locale], {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: TZ,
  }).format(new Date(iso))
}

// «1 нояб.»
export function formatDay(iso: string | Date, locale: AppLocale): string {
  return new Intl.DateTimeFormat(TAGS[locale], { day: 'numeric', month: 'short', timeZone: TZ }).format(new Date(iso))
}

// день по Алматы в виде YYYY-MM-DD (для запросов истории), со сдвигом в днях
export function localDay(date: Date, shiftDays = 0): string {
  const shifted = new Date(date.getTime() + shiftDays * 86_400_000)
  return new Intl.DateTimeFormat('en-CA', { timeZone: TZ }).format(shifted)
}

// следующий запуск ежечасной задачи: ближайшее xx:minute UTC после now
export function nextRun(now: Date, minute: number): Date {
  const next = new Date(now)
  next.setUTCMinutes(minute, 0, 0)
  if (next <= now) next.setUTCHours(next.getUTCHours() + 1)
  return next
}

// час суток по Алматы (0–23) – для дня и ночи на небе
export function localHour(date: Date): number {
  return Number(new Intl.DateTimeFormat('en-GB', { hour: 'numeric', hourCycle: 'h23', timeZone: TZ }).format(date))
}

// мм:сс до момента
export function countdown(ms: number): string {
  const total = Math.max(0, Math.round(ms / 1000))
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}
