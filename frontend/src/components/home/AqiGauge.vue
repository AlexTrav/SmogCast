<script setup lang="ts">
import { computed } from 'vue'
import { useCountUp } from '../../composables/useCountUp'
import { LEVEL_COLOR, LEVELS, scalePosition } from '../../utils/aqi'

// полукруглая шкала US AQI: шесть уровней равными дугами, стрелка – на текущем значении
const props = defineProps<{ pm: number }>()

const R = 80
const CX = 100
const CY = 96
const GAP = 2.2 // градусы между дугами

function point(deg: number, r = R) {
  const a = ((180 - deg) * Math.PI) / 180
  return [CX + r * Math.cos(a), CY - r * Math.sin(a)]
}

const arcs = LEVELS.map((l, i) => {
  const from = (i * 180) / LEVELS.length + (i ? GAP / 2 : 0)
  const to = ((i + 1) * 180) / LEVELS.length - (i < LEVELS.length - 1 ? GAP / 2 : 0)
  const [x1, y1] = point(from)
  const [x2, y2] = point(to)
  return { key: l.key, d: `M ${x1} ${y1} A ${R} ${R} 0 0 1 ${x2} ${y2}` }
})

const angle = useCountUp(computed(() => scalePosition(props.pm) * 180), 1200)
const needle = computed(() => {
  const [x, y] = point(angle.value ?? 0, R - 18)
  return { x, y }
})
</script>

<template>
  <svg viewBox="0 0 200 112" class="w-full" aria-hidden="true">
    <path
      v-for="a in arcs"
      :key="a.key"
      :d="a.d"
      fill="none"
      :stroke="LEVEL_COLOR[a.key]"
      stroke-width="12"
      stroke-linecap="round"
    />
    <line :x1="CX" :y1="CY" :x2="needle.x" :y2="needle.y" stroke="white" stroke-width="3.5" stroke-linecap="round" />
    <circle :cx="CX" :cy="CY" r="6" fill="white" />
  </svg>
</template>
