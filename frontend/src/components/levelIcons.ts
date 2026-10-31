import { CloudFog, CloudSun, Leaf, ShieldAlert, Siren, TriangleAlert } from 'lucide-vue-next'
import type { AqiLevel } from '../types'

// значок каждого уровня AQI: уровень никогда не передаётся одним цветом
export const LEVEL_ICON: Record<AqiLevel, typeof Leaf> = {
  good: Leaf,
  moderate: CloudSun,
  sensitive: CloudFog,
  unhealthy: TriangleAlert,
  very_unhealthy: ShieldAlert,
  hazardous: Siren,
}
