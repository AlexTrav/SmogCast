<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useLive } from '../../composables/useLive'
import type { AppLocale } from '../../types'
import { aqiOf, hazeOpacity, levelOf, skyColors, WHO_24H } from '../../utils/aqi'
import { countdown, formatHour, formatNumber, localHour } from '../../utils/format'
import LevelBadge from '../LevelBadge.vue'
import Mountains from './Mountains.vue'
import SkyParticles from './SkyParticles.vue'

// первый экран: небо над Алматы, его цвет и дымка – от текущего PM2.5, день и ночь – по местному времени
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { status: live, now, next, updating } = useLive()
const route = useRoute()

// предпросмотр неба для показа: ?sky=day|night и ?pm=… подменяют время суток и PM2.5 (данные API не меняются)
const demoPm = computed(() => {
  const v = Number(route.query.pm)
  return Number.isFinite(v) && v >= 0 && route.query.pm !== undefined ? v : null
})
const status = computed(() => {
  const s = live.value
  if (!s || demoPm.value === null) return s
  return { ...s, pm2_5: demoPm.value, level: levelOf(demoPm.value), aqi: aqiOf(demoPm.value), change_24h: null }
})
const night = computed(() => {
  if (route.query.sky === 'day' || route.query.sky === 'night') return route.query.sky === 'night'
  const h = localHour(now.value)
  return h < 7 || h >= 19
})
const pm = computed(() => status.value?.pm2_5 ?? 0)
const sky = computed(() => skyColors(status.value?.level ?? 'good', night.value))
const background = computed(
  () => `linear-gradient(180deg, ${sky.value[0]} 0%, ${sky.value[1]} 55%, ${sky.value[2]} 100%)`,
)
const haze = computed(() => hazeOpacity(pm.value))
const who = computed(() => pm.value / WHO_24H)
const change = computed(() => {
  const c = status.value?.change_24h
  if (c == null) return null
  return `${c > 0 ? '+' : c < 0 ? '−' : '±'}${formatNumber(Math.abs(c), lang.value)}`
})
</script>

<template>
  <section
    class="relative isolate flex min-h-[820px] items-start overflow-hidden transition-[background] duration-1000 sm:min-h-[720px]"
    :style="{ background }"
  >
    <!-- ночью – звёзды, их почти не видно сквозь смог -->
    <div
      v-if="night"
      class="pointer-events-none absolute inset-0 opacity-70"
      :style="{
        opacity: Math.max(0.1, 0.8 - haze * 1.3),
        backgroundImage:
          'radial-gradient(1px 1px at 12% 18%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 32% 8%, #fff 50%, transparent 51%), radial-gradient(1.4px 1.4px at 58% 22%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 76% 12%, #fff 50%, transparent 51%), radial-gradient(1.2px 1.2px at 88% 28%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 45% 32%, #fff 50%, transparent 51%), radial-gradient(1px 1px at 22% 36%, #fff 50%, transparent 51%)',
      }"
    />
    <SkyParticles :pm="pm" :night="night" />
    <Mountains :haze="haze" :night="night" />

    <div class="relative mx-auto w-full max-w-7xl px-4 pt-28 pb-56 text-white sm:px-6 sm:pt-32">
      <p class="animate-rise flex items-center gap-3 text-sm font-medium tracking-wide text-white/85">
        <span class="relative flex h-2.5 w-2.5">
          <span class="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-emerald-300" />
          <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-300" />
        </span>
        {{ t('hero.place') }} · {{ t('hero.live') }}
        <span v-if="status" class="text-white/70 tabular-nums">· {{ t('hero.dataFor', { time: formatHour(status.time, lang) }) }}</span>
      </p>

      <template v-if="status">
        <p class="animate-rise mt-8 text-sm font-semibold tracking-[0.14em] text-white/70 uppercase" style="animation-delay: 80ms">
          {{ t('hero.pm') }}
        </p>
        <div class="animate-rise mt-2 flex items-end gap-4" style="animation-delay: 140ms">
          <span class="text-[7rem] leading-[0.85] font-extralight tracking-tight drop-shadow-sm sm:text-[10rem]">
            {{ formatNumber(status.pm2_5, lang) }}
          </span>
          <span class="mb-3 text-xl text-white/80 sm:mb-5">{{ t('hero.unit') }}</span>
        </div>

        <div class="animate-rise mt-6 flex flex-wrap items-center gap-3" style="animation-delay: 200ms">
          <LevelBadge :level="status.level" glass />
          <span class="rounded-full bg-white/15 px-3.5 py-1.5 text-sm font-semibold ring-1 ring-white/25 backdrop-blur-md">
            US AQI <span class="num">{{ status.aqi }}</span>
          </span>
          <span v-if="change" class="text-sm text-white/80">{{ t('hero.change', { value: change }) }}</span>
        </div>

        <p class="animate-rise mt-6 max-w-xl text-lg leading-relaxed text-white/90" style="animation-delay: 260ms">
          {{ t(`advice.${status.level}`) }}
        </p>
        <p class="animate-rise mt-2 text-sm text-white/70" style="animation-delay: 300ms">
          {{ who > 1 ? t('hero.whoTimes', { value: formatNumber(who, lang) }) : t('hero.whoBelow') }} ·
          {{ t('hero.who') }}
        </p>

        <p class="animate-rise mt-8 inline-flex tabular-nums items-center gap-2 rounded-full bg-black/15 px-4 py-2 text-sm text-white/85 ring-1 ring-white/15 backdrop-blur-md" style="animation-delay: 340ms">
          <template v-if="updating">{{ t('hero.updating') }}</template>
          <template v-else>{{ t('hero.nextUpdate', { time: countdown(next.getTime() - now.getTime()) }) }}</template>
        </p>
      </template>

      <!-- заготовка, пока API просыпается -->
      <div v-else class="mt-10 space-y-4" aria-hidden="true">
        <div class="h-4 w-32 animate-pulse rounded-full bg-white/20" />
        <div class="h-36 w-80 animate-pulse rounded-3xl bg-white/15" />
        <div class="h-8 w-64 animate-pulse rounded-full bg-white/20" />
      </div>
    </div>
  </section>
</template>
