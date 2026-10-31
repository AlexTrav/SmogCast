<script setup lang="ts">
import { Navigation2, Share2, Sunrise, Sunset } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useCountUp } from '../../composables/useCountUp'
import { useLive } from '../../composables/useLive'
import type { AppLocale } from '../../types'
import { aqiOf, levelOf, WHO_24H } from '../../utils/aqi'
import { countdown, formatDateHour, formatHour, formatNumber } from '../../utils/format'
import { drawCard, shareCard } from '../../utils/share'
import { skyPhase, type SkyPhase, sunTimes } from '../../utils/sun'
import LevelBadge from '../LevelBadge.vue'
import AqiGauge from './AqiGauge.vue'
import SkyScene from '../SkyScene.vue'

// первый экран: небо над Алматы – цвет и дымка от текущего PM2.5, фаза (день, рассвет, закат, ночь) – по
// настоящему восходу и закату в Алматы, частицы дрейфуют по прогнозу ветра
const props = defineProps<{ wind?: number | null; windDir?: number | null }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { status: live, now, next, updating } = useLive()
const route = useRoute()

// предпросмотр для показа: ?sky=day|dawn|dusk|night и ?pm=… подменяют фазу неба и PM2.5 (данные API не меняются)
const PHASES: SkyPhase[] = ['day', 'dawn', 'dusk', 'night']
const demoPm = computed(() => {
  const v = Number(route.query.pm)
  return route.query.pm !== undefined && Number.isFinite(v) && v >= 0 ? v : null
})
const status = computed(() => {
  const s = live.value
  if (!s || demoPm.value === null) return s
  return { ...s, pm2_5: demoPm.value, level: levelOf(demoPm.value), aqi: aqiOf(demoPm.value), change_24h: null }
})
const phase = computed<SkyPhase>(() =>
  PHASES.includes(route.query.sky as SkyPhase) ? (route.query.sky as SkyPhase) : skyPhase(now.value),
)
const sun = computed(() => sunTimes(now.value))

const pm = computed(() => status.value?.pm2_5 ?? 0)
const shownPm = useCountUp(computed(() => status.value?.pm2_5), 1100)
const who = computed(() => pm.value / WHO_24H)
const change = computed(() => {
  const c = status.value?.change_24h
  if (c == null) return null
  return `${c > 0 ? '+' : c < 0 ? '−' : '±'}${formatNumber(Math.abs(c), lang.value)}`
})
// «Поделиться»: карточка PNG с небом и текущим PM2.5
async function share() {
  const s = status.value
  if (!s) return
  const blob = await drawCard({
    pm: formatNumber(s.pm2_5, lang.value),
    unit: t('hero.unit'),
    level: s.level,
    levelText: t(`levels.${s.level}`),
    aqi: s.aqi,
    when: formatDateHour(s.time, lang.value),
    place: t('hero.place'),
    phase: phase.value,
    url: 'alextrav.github.io/SmogCast',
  })
  await shareCard(blob, `smogcast-${s.time.slice(0, 13)}.png`, `SmogCast · ${t('hero.place')}`)
}

// стрелка показывает, куда дует ветер: направление в данных – откуда, поэтому +180°
const windArrow = computed(() => (props.windDir == null ? 0 : (props.windDir + 180) % 360))
</script>

<template>
  <section class="relative isolate flex min-h-[860px] items-start overflow-hidden sm:min-h-[720px]">
    <SkyScene :pm="pm" :level="status?.level ?? 'good'" :phase="phase" :wind="wind" :wind-dir="windDir" />

    <div class="relative mx-auto grid w-full max-w-7xl gap-10 px-4 pt-28 pb-56 text-white sm:px-6 sm:pt-32 lg:grid-cols-[1fr_20rem]">
      <div>
        <p class="animate-rise flex flex-wrap items-center gap-x-3 gap-y-1 text-sm font-medium tracking-wide text-white/85">
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
              {{ formatNumber(shownPm ?? status.pm2_5, lang) }}
            </span>
            <span class="mb-3 text-xl text-white/80 sm:mb-5">{{ t('hero.unit') }}</span>
          </div>

          <div class="animate-rise mt-6 flex flex-wrap items-center gap-3" style="animation-delay: 200ms">
            <LevelBadge :level="status.level" glass />
            <span class="rounded-full bg-white/15 px-3.5 py-1.5 text-sm font-semibold ring-1 ring-white/25 backdrop-blur-md lg:hidden">
              US AQI <span class="tabular-nums">{{ status.aqi }}</span>
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

          <div class="animate-rise mt-8 flex flex-wrap items-center gap-3" style="animation-delay: 340ms">
            <p
              class="inline-flex items-center gap-2 rounded-full bg-black/15 px-4 py-2 text-sm text-white/85 tabular-nums ring-1 ring-white/15 backdrop-blur-md"
              aria-live="polite"
            >
              <template v-if="updating">{{ t('hero.updating') }}</template>
              <template v-else>{{ t('hero.nextUpdate', { time: countdown(next.getTime() - now.getTime()) }) }}</template>
            </p>
            <button
              class="inline-flex items-center gap-2 rounded-full bg-white/15 px-4 py-2 text-sm font-medium ring-1 ring-white/25 backdrop-blur-md transition-colors hover:bg-white/25"
              @click="share"
            >
              <Share2 class="h-4 w-4" aria-hidden="true" />{{ t('hero.share') }}
            </button>
          </div>
        </template>

        <!-- заготовка, пока API просыпается -->
        <div v-else class="mt-10 space-y-4" aria-hidden="true">
          <div class="h-4 w-32 animate-pulse rounded-full bg-white/20" />
          <div class="h-36 w-80 max-w-full animate-pulse rounded-3xl bg-white/15" />
          <div class="h-8 w-64 animate-pulse rounded-full bg-white/20" />
        </div>
      </div>

      <!-- над городом: шкала AQI, ветер, восход и закат -->
      <aside
        v-if="status"
        class="animate-rise hidden self-start rounded-3xl bg-white/10 p-6 ring-1 ring-white/20 backdrop-blur-md lg:block"
        style="animation-delay: 220ms"
      >
        <p class="text-xs font-semibold tracking-[0.14em] text-white/70 uppercase">{{ t('hero.aboveCity') }}</p>
        <AqiGauge class="mt-3" :pm="status.pm2_5" />
        <p class="-mt-2 text-center">
          <span class="text-4xl font-light tabular-nums">{{ status.aqi }}</span>
          <span class="ml-1.5 text-sm text-white/70">US AQI</span>
        </p>
        <dl class="mt-5 grid grid-cols-3 gap-2 border-t border-white/15 pt-4 text-center text-sm">
          <div>
            <dt class="flex justify-center text-white/60"><Sunrise class="h-4 w-4" :aria-label="t('hero.sunrise')" /></dt>
            <dd class="mt-1 tabular-nums">{{ formatHour(sun.sunrise, lang) }}</dd>
          </div>
          <div>
            <dt class="flex justify-center text-white/60"><Sunset class="h-4 w-4" :aria-label="t('hero.sunset')" /></dt>
            <dd class="mt-1 tabular-nums">{{ formatHour(sun.sunset, lang) }}</dd>
          </div>
          <div v-if="wind != null">
            <dt class="flex justify-center text-white/60">
              <Navigation2 class="h-4 w-4 transition-transform" :style="{ transform: `rotate(${windArrow}deg)` }" :aria-label="t('hero.wind')" />
            </dt>
            <dd class="mt-1 tabular-nums">{{ t('hero.windValue', { value: formatNumber(wind, lang) }) }}</dd>
          </div>
        </dl>
      </aside>
    </div>
  </section>
</template>
