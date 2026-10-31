<script setup lang="ts">
import { useWindowScroll } from '@vueuse/core'
import { computed } from 'vue'
import type { AqiLevel } from '../types'
import { hazeOpacity, skyColors } from '../utils/aqi'
import type { SkyPhase } from '../utils/sun'
import Mountains from './home/Mountains.vue'
import SkyParticles from './home/SkyParticles.vue'

// небо над Алматы: градиент по уровню и фазе суток, звёзды ночью, частицы взвеси и горы в дымке;
// фон для первого экрана главной и для машины времени (родитель задаёт размер и position: relative)
const props = defineProps<{
  pm: number
  level: AqiLevel
  phase: SkyPhase
  wind?: number | null
  windDir?: number | null
  parallax?: boolean
}>()

const sky = computed(() => skyColors(props.level, props.phase))
const background = computed(
  () => `linear-gradient(180deg, ${sky.value[0]} 0%, ${sky.value[1]} 55%, ${sky.value[2]} 100%)`,
)
const haze = computed(() => hazeOpacity(props.pm))

// лёгкий параллакс на главной: при прокрутке звёзды и частицы отстают сильнее гор – у неба появляется глубина;
// считается только в пределах первого экрана и выключается при «уменьшить движение»
const { y } = useWindowScroll()
const still = typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
const shift = (k: number) =>
  props.parallax && !still ? { transform: `translate3d(0, ${Math.min(y.value, 900) * k}px, 0)` } : undefined
</script>

<template>
  <div class="pointer-events-none absolute inset-0 transition-[background] duration-1000" :style="{ background }" aria-hidden="true">
    <!-- ночью – звёзды, сквозь смог их почти не видно -->
    <!-- «вдох» чистого воздуха: у горизонта медленно нарастает и гаснет мягкое свечение -->
    <div
      v-if="level === 'good'"
      class="sky-breathe absolute inset-0"
      style="background: radial-gradient(ellipse 70% 45% at 50% 85%, rgb(255 255 255 / 0.22), transparent 70%)"
    />
    <div
      v-if="phase === 'night'"
      class="absolute inset-0"
      :style="{
        ...shift(0.35),
        opacity: Math.max(0.1, 0.8 - haze * 1.3),
        backgroundImage:
          'radial-gradient(1px 1px at 12% 18%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 32% 8%, #fff 50%, transparent 51%), radial-gradient(1.4px 1.4px at 58% 22%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 76% 12%, #fff 50%, transparent 51%), radial-gradient(1.2px 1.2px at 88% 28%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 45% 32%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 22% 36%, #fff 50%, transparent 51%)',
      }"
    />
    <div class="absolute inset-0" :style="shift(0.25)">
      <SkyParticles :pm="pm" :night="phase !== 'day'" :wind="wind" :wind-dir="windDir" />
    </div>
    <div class="absolute inset-0" :style="shift(0.12)">
      <Mountains :haze="haze" :phase="phase" />
    </div>
  </div>
</template>
