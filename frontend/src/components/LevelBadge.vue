<script setup lang="ts">
import { CloudFog, CloudSun, Leaf, ShieldAlert, Siren, TriangleAlert } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import type { AqiLevel } from '../types'
import { LEVEL_COLOR } from '../utils/aqi'

// уровень AQI никогда не передаётся одним цветом: цветная точка, иконка и подпись вместе
defineProps<{ level: AqiLevel; glass?: boolean }>()
const { t } = useI18n()

const ICONS = {
  good: Leaf,
  moderate: CloudSun,
  sensitive: CloudFog,
  unhealthy: TriangleAlert,
  very_unhealthy: ShieldAlert,
  hazardous: Siren,
}
</script>

<template>
  <span
    class="inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-semibold"
    :class="glass ? 'bg-white/15 text-white ring-1 ring-white/25 backdrop-blur-md' : 'bg-surface-2 text-ink'"
  >
    <span class="h-2.5 w-2.5 rounded-full ring-2 ring-white/60" :style="{ background: LEVEL_COLOR[level] }" />
    <component :is="ICONS[level]" class="h-4 w-4" aria-hidden="true" />
    {{ t(`levels.${level}`) }}
  </span>
</template>
