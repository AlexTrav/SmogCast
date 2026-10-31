<script setup lang="ts">
import { useIntervalFn } from '@vueuse/core'
import { Pause, Play } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AppLocale } from '../../types'
import { levelOf } from '../../utils/aqi'
import { formatDate, formatHour, formatNumber } from '../../utils/format'
import { skyPhase } from '../../utils/sun'
import LevelBadge from '../LevelBadge.vue'
import SkyScene from '../SkyScene.vue'

// машина времени: ползунок по всем часам ряда, небо и цифра – под выбранный час; кнопка проигрывает
// худший эпизод смога (неделя с наибольшим средним PM2.5) – час за часом
const props = defineProps<{ start: string; values: (number | null)[]; episode: { from: number; to: number } | null }>()
const index = defineModel<number>({ required: true })
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)

const time = computed(() => new Date(new Date(props.start).getTime() + index.value * 3_600_000))
// пропущенный час – ближайшее известное значение раньше
const pm = computed(() => {
  for (let i = index.value; i >= 0; i--) if (props.values[i] != null) return props.values[i] as number
  return 0
})
const level = computed(() => levelOf(pm.value))
const phase = computed(() => skyPhase(time.value))

const STEP_MS = 45 // скорость проигрывания: час ряда за 45 мс, неделя – около 8 секунд
const { pause, resume, isActive } = useIntervalFn(
  () => {
    if (!props.episode || index.value >= props.episode.to) {
      pause()
      return
    }
    index.value += 1
  },
  STEP_MS,
  { immediate: false },
)

function play() {
  if (isActive.value) {
    pause()
    return
  }
  if (props.episode && (index.value < props.episode.from || index.value >= props.episode.to)) index.value = props.episode.from
  resume()
}
</script>

<template>
  <div class="grid overflow-hidden rounded-3xl border border-line lg:grid-cols-[1.4fr_1fr]">
    <div class="relative isolate min-h-72 sm:min-h-80">
      <SkyScene :pm="pm" :level="level" :phase="phase" />
      <div class="relative p-6 text-white">
        <p class="text-sm font-medium text-white/80 tabular-nums">{{ formatDate(time, lang) }}, {{ formatHour(time, lang) }}</p>
        <p class="mt-2 text-6xl font-extralight tracking-tight sm:text-7xl">
          {{ formatNumber(pm, lang) }}<span class="ml-2 text-base text-white/75">{{ t('hero.unit') }}</span>
        </p>
        <LevelBadge class="mt-4" :level="level" glass />
      </div>
    </div>
    <div class="flex flex-col justify-between gap-6 bg-surface p-6">
      <div>
        <h3 class="text-lg font-bold tracking-tight text-ink">{{ t('history.machine') }}</h3>
        <p class="mt-1 text-sm text-muted">{{ t('history.machineText') }}</p>
      </div>
      <div>
        <label class="sr-only" for="time-machine">{{ t('history.machine') }}</label>
        <input
          id="time-machine"
          v-model.number="index"
          type="range"
          min="0"
          :max="values.length - 1"
          step="1"
          class="w-full accent-[var(--primary)]"
          :aria-valuetext="`${formatDate(time, lang)}, ${formatHour(time, lang)}`"
        />
        <div class="mt-1 flex justify-between text-xs text-faint tabular-nums">
          <span>{{ formatDate(start, lang) }}</span>
          <span>{{ formatDate(new Date(new Date(start).getTime() + (values.length - 1) * 3_600_000), lang) }}</span>
        </div>
      </div>
      <button v-if="episode" class="btn-ghost self-start" @click="play">
        <Pause v-if="isActive" class="h-4 w-4" />
        <Play v-else class="h-4 w-4" />
        {{ isActive ? t('history.pause') : t('history.play') }}
      </button>
    </div>
  </div>
</template>
