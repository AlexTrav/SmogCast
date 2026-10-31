<script setup lang="ts">
import { computed } from 'vue'
import type { AqiLevel } from '../types'
import { hazeOpacity, skyColors } from '../utils/aqi'
import type { SkyPhase } from '../utils/sun'
import Mountains from './home/Mountains.vue'
import SkyParticles from './home/SkyParticles.vue'

// небо над Алматы: градиент по уровню и фазе суток, звёзды ночью, частицы взвеси и горы в дымке;
// фон для первого экрана главной и для машины времени (родитель задаёт размер и position: relative)
const props = defineProps<{ pm: number; level: AqiLevel; phase: SkyPhase; wind?: number | null; windDir?: number | null }>()

const sky = computed(() => skyColors(props.level, props.phase))
const background = computed(
  () => `linear-gradient(180deg, ${sky.value[0]} 0%, ${sky.value[1]} 55%, ${sky.value[2]} 100%)`,
)
const haze = computed(() => hazeOpacity(props.pm))
</script>

<template>
  <div class="pointer-events-none absolute inset-0 transition-[background] duration-1000" :style="{ background }" aria-hidden="true">
    <!-- ночью – звёзды, сквозь смог их почти не видно -->
    <div
      v-if="phase === 'night'"
      class="absolute inset-0"
      :style="{
        opacity: Math.max(0.1, 0.8 - haze * 1.3),
        backgroundImage:
          'radial-gradient(1px 1px at 12% 18%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 32% 8%, #fff 50%, transparent 51%), radial-gradient(1.4px 1.4px at 58% 22%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 76% 12%, #fff 50%, transparent 51%), radial-gradient(1.2px 1.2px at 88% 28%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 45% 32%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 22% 36%, #fff 50%, transparent 51%)',
      }"
    />
    <SkyParticles :pm="pm" :night="phase !== 'day'" :wind="wind" :wind-dir="windDir" />
    <Mountains :haze="haze" :phase="phase" />
  </div>
</template>
