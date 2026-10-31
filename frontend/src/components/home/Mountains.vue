<script setup lang="ts">
import { computed } from 'vue'
import type { SkyPhase } from '../../utils/sun'

// силуэт Заилийского Алатау в три плана: дальний хребет со снегом, средний и предгорья с огнями города ночью;
// дымка ложится между планами – при сильном смоге дальние горы почти исчезают
const props = defineProps<{ haze: number; phase: SkyPhase }>()

const PALETTE = {
  day: { far: '#7f9bbd', snow: '#ffffff', mid: '#55708f', near: '#2f4560', haze: '226, 190, 140' },
  // на рассвете и закате снег розовеет, горы – лиловые
  twilight: { far: '#5b6684', snow: '#f6d3c6', mid: '#3a4660', near: '#1c2538', haze: '222, 168, 128' },
  night: { far: '#22324d', snow: '#8ea3c2', mid: '#141f33', near: '#0a1120', haze: '196, 150, 110' },
}
const colors = computed(() => PALETTE[props.phase === 'day' || props.phase === 'night' ? props.phase : 'twilight'])

// огни города в предгорьях: фиксированные точки, чтобы картинка не менялась при каждой отрисовке
const lights = Array.from({ length: 70 }, (_, i) => ({
  x: (i * 131.7) % 1440,
  y: 292 + ((i * 37) % 26),
  r: 0.8 + ((i * 7) % 10) / 9,
  o: 0.35 + ((i * 13) % 10) / 16,
}))
</script>

<template>
  <svg
    class="pointer-events-none absolute inset-x-0 bottom-0 h-[26%] w-full sm:h-[46%]"
    viewBox="0 0 1440 320"
    preserveAspectRatio="none"
    aria-hidden="true"
  >
    <defs>
      <linearGradient id="snow" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" :stop-color="colors.snow" />
        <stop offset="0.17" :stop-color="colors.snow" stop-opacity="0.85" />
        <stop offset="0.28" :stop-color="colors.far" />
      </linearGradient>
      <linearGradient id="haze" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" :stop-color="`rgb(${colors.haze})`" stop-opacity="0" />
        <stop offset="0.2" :stop-color="`rgb(${colors.haze})`" :stop-opacity="haze * 0.7" />
        <stop offset="0.45" :stop-color="`rgb(${colors.haze})`" :stop-opacity="haze" />
        <stop offset="1" :stop-color="`rgb(${colors.haze})`" :stop-opacity="haze * 0.8" />
      </linearGradient>
    </defs>
    <path
      fill="url(#snow)"
      d="M0,210 L60,190 L110,200 L170,150 L210,165 L260,120 L300,140 L350,95 L390,118 L430,80 L470,105 L520,70
         L560,98 L600,60 L640,88 L690,55 L735,85 L780,62 L830,92 L870,70 L915,100 L960,75 L1010,110 L1060,85
         L1110,120 L1160,95 L1210,130 L1260,110 L1310,140 L1370,125 L1440,150 L1440,320 L0,320 Z"
    />
    <rect x="0" y="0" width="1440" height="320" fill="url(#haze)" />
    <path
      :fill="colors.mid"
      d="M0,250 L80,225 L150,240 L230,205 L300,228 L380,195 L450,220 L540,190 L620,215 L700,185 L790,212
         L880,190 L960,220 L1050,198 L1140,225 L1230,205 L1320,232 L1440,215 L1440,320 L0,320 Z"
    />
    <rect x="0" y="180" width="1440" height="140" fill="url(#haze)" opacity="0.6" />
    <path
      :fill="colors.near"
      d="M0,285 C120,265 240,272 360,262 C480,252 600,270 720,266 C840,262 960,250 1080,258 C1200,266 1320,256
         1440,262 L1440,320 L0,320 Z"
    />
    <g v-if="phase !== 'day'">
      <circle v-for="(l, i) in lights" :key="i" :cx="l.x" :cy="l.y" :r="l.r" fill="#ffd28a" :opacity="l.o" />
    </g>
  </svg>
</template>
