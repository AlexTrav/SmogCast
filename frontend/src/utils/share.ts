import type { AqiLevel } from '../types'
import { skyColors } from './aqi'
import type { SkyPhase } from './sun'

// карточка «Поделиться» 1200×630 (размер превью в соцсетях): небо по уровню и фазе суток, силуэт гор,
// PM2.5, уровень и время – рисуется на canvas в браузере, без сервера
export interface ShareCard {
  pm: string
  unit: string
  level: AqiLevel
  levelText: string
  aqi: number
  when: string
  place: string
  phase: SkyPhase
  url: string
}

const W = 1200
const H = 630
// хребет из Mountains.vue (viewBox 1440×320), сжатый под ширину карточки
const RIDGE = [
  [0, 210], [60, 190], [110, 200], [170, 150], [210, 165], [260, 120], [300, 140], [350, 95], [390, 118], [430, 80],
  [470, 105], [520, 70], [560, 98], [600, 60], [640, 88], [690, 55], [735, 85], [780, 62], [830, 92], [870, 70],
  [915, 100], [960, 75], [1010, 110], [1060, 85], [1110, 120], [1160, 95], [1210, 130], [1260, 110], [1310, 140],
  [1370, 125], [1440, 150],
]

export async function drawCard(card: ShareCard): Promise<Blob> {
  await document.fonts?.ready
  const canvas = document.createElement('canvas')
  canvas.width = W
  canvas.height = H
  const ctx = canvas.getContext('2d')!
  const [top, mid, horizon] = skyColors(card.level, card.phase)
  const sky = ctx.createLinearGradient(0, 0, 0, H)
  sky.addColorStop(0, top)
  sky.addColorStop(0.55, mid)
  sky.addColorStop(1, horizon)
  ctx.fillStyle = sky
  ctx.fillRect(0, 0, W, H)

  // горы: дальний хребет со снегом и ближний план
  const base = H - 230
  const scale = W / 1440
  ctx.beginPath()
  ctx.moveTo(0, H)
  for (const [x, y] of RIDGE) ctx.lineTo(x * scale, base + y * 0.7)
  ctx.lineTo(W, H)
  ctx.closePath()
  const ridge = ctx.createLinearGradient(0, base + 30, 0, base + 160)
  ridge.addColorStop(0, card.phase === 'day' ? '#ffffff' : '#9fb0c8')
  ridge.addColorStop(0.35, card.phase === 'day' ? '#7f9bbd' : '#2a3a56')
  ctx.fillStyle = ridge
  ctx.fill()
  ctx.fillStyle = card.phase === 'day' ? '#2f4560' : '#0a1120'
  ctx.beginPath()
  ctx.moveTo(0, H)
  ctx.lineTo(0, H - 60)
  ctx.bezierCurveTo(300, H - 95, 700, H - 50, W, H - 80)
  ctx.lineTo(W, H)
  ctx.closePath()
  ctx.fill()

  // текст
  const font = (weight: number, size: number) => `${weight} ${size}px 'Onest Variable', system-ui, sans-serif`
  ctx.fillStyle = 'rgba(255,255,255,0.85)'
  ctx.font = font(600, 30)
  ctx.fillText(`SmogCast · ${card.place}`, 64, 84)
  ctx.font = font(400, 26)
  ctx.fillStyle = 'rgba(255,255,255,0.75)'
  ctx.fillText(card.when, 64, 124)
  ctx.fillStyle = '#ffffff'
  ctx.font = font(200, 190)
  ctx.fillText(card.pm, 56, 320)
  const width = ctx.measureText(card.pm).width
  ctx.font = font(400, 34)
  ctx.fillStyle = 'rgba(255,255,255,0.85)'
  ctx.fillText(card.unit, 72 + width, 312)
  ctx.font = font(600, 36)
  ctx.fillStyle = '#ffffff'
  ctx.fillText(`${card.levelText} · US AQI ${card.aqi}`, 64, 384)
  ctx.font = font(500, 24)
  ctx.fillStyle = 'rgba(255,255,255,0.8)'
  ctx.fillText(card.url, 64, H - 28)

  return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob!), 'image/png'))
}

// на телефоне – системное меню «Поделиться» с файлом, на компьютере – скачивание PNG
export async function shareCard(blob: Blob, name: string, title: string): Promise<void> {
  const file = new File([blob], name, { type: 'image/png' })
  const touch = window.matchMedia('(pointer: coarse)').matches
  if (touch && navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title })
      return
    } catch {
      // пользователь закрыл меню – ничего не делаем
      return
    }
  }
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
