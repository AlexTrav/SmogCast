<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

// взвесь в воздухе: число частиц растёт с PM2.5; при prefers-reduced-motion частицы стоят на месте
const props = defineProps<{ pm: number; night: boolean }>()
const canvas = ref<HTMLCanvasElement | null>(null)

interface Particle {
  x: number
  y: number
  r: number
  vx: number
  vy: number
  a: number
}

let particles: Particle[] = []
let frame = 0
let observer: ResizeObserver | null = null
const reduce = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches

function count(pm: number): number {
  return Math.round(Math.min(420, Math.max(12, pm * 4)))
}

function spawn(w: number, h: number): Particle {
  return {
    x: Math.random() * w,
    y: Math.random() * h,
    r: 0.6 + Math.random() * 1.8,
    vx: 0.08 + Math.random() * 0.25,
    vy: (Math.random() - 0.5) * 0.08,
    a: 0.15 + Math.random() * 0.45,
  }
}

function reset() {
  const el = canvas.value
  if (!el) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  el.width = el.clientWidth * dpr
  el.height = el.clientHeight * dpr
  el.getContext('2d')?.setTransform(dpr, 0, 0, dpr, 0, 0)
  particles = Array.from({ length: count(props.pm) }, () => spawn(el.clientWidth, el.clientHeight))
}

function draw() {
  const el = canvas.value
  const ctx = el?.getContext('2d')
  if (!el || !ctx) return
  const w = el.clientWidth
  const h = el.clientHeight
  ctx.clearRect(0, 0, w, h)
  // днём – тёплая пыль, ночью – частицы подсвечены огнями города
  const tone = props.night ? '255, 214, 170' : '255, 244, 228'
  for (const p of particles) {
    if (!reduce) {
      p.x += p.vx
      p.y += p.vy
      if (p.x > w + 4) p.x = -4
      if (p.y < -4 || p.y > h + 4) p.y = Math.random() * h
    }
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${tone}, ${p.a})`
    ctx.fill()
  }
  if (!reduce) frame = requestAnimationFrame(draw)
}

onMounted(() => {
  reset()
  draw()
  observer = new ResizeObserver(() => {
    reset()
    if (reduce) draw()
  })
  if (canvas.value) observer.observe(canvas.value)
})

watch(
  () => props.pm,
  () => {
    reset()
    if (reduce) draw()
  },
)

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  observer?.disconnect()
})
</script>

<template>
  <canvas ref="canvas" class="pointer-events-none absolute inset-0 h-full w-full" aria-hidden="true" />
</template>
