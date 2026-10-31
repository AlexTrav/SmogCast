<script setup lang="ts">
import { Navigation2, Pause, Play, Share2, Sunrise, Sunset, X } from 'lucide-vue-next'
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useCountUp } from '../../composables/useCountUp'
import { useLive } from '../../composables/useLive'
import { useSensitive } from '../../composables/useSensitive'
import type { AppLocale, Forecast } from '../../types'
import { aqiOf, levelOf, WHO_24H } from '../../utils/aqi'
import { countdown, formatDateHour, formatHour, formatNumber } from '../../utils/format'
import { drawCard, shareCard } from '../../utils/share'
import { skyPhase, type SkyPhase, sunTimes } from '../../utils/sun'
import LevelBadge from '../LevelBadge.vue'
import TermHint from '../TermHint.vue'
import AqiGauge from './AqiGauge.vue'
import SkyScene from '../SkyScene.vue'

// первый экран: небо над Алматы – цвет и дымка от текущего PM2.5, фаза (день, рассвет, закат, ночь) – по
// настоящему восходу и закату в Алматы, частицы дрейфуют по прогнозу ветра
const props = defineProps<{ wind?: number | null; windDir?: number | null; forecast?: Forecast | null }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { status: live, now, next, updating } = useLive()
const { sensitive } = useSensitive()
const route = useRoute()

// предпросмотр для показа: ?sky=day|dawn|dusk|night и ?pm=… подменяют фазу неба и PM2.5 (данные API не меняются)
const PHASES: SkyPhase[] = ['day', 'dawn', 'dusk', 'night']
const demoPm = computed(() => {
  const v = Number(route.query.pm)
  return route.query.pm !== undefined && Number.isFinite(v) && v >= 0 ? v : null
})

// «Промотать прогноз»: небо, дымка, цифра и уровень проходят по часам прогноза смеси (час за STEP_MS);
// фаза неба – по настоящему восходу и закату того часа; ползунок – перейти к любому часу
const STEP_MS = 220
const hour = ref<number | null>(null)
const playing = ref(false)
let timer: ReturnType<typeof setInterval> | undefined
const last = computed(() => (props.forecast?.pred.length ?? 1) - 1)
const hourTime = computed(() =>
  hour.value == null || !props.forecast ? null : new Date(new Date(props.forecast.start).getTime() + hour.value * 3_600_000),
)

function play() {
  if (!props.forecast) return
  if (hour.value == null || hour.value >= last.value) hour.value = 0
  playing.value = true
  clearInterval(timer)
  timer = setInterval(() => {
    if (hour.value == null || hour.value >= last.value) return pause()
    hour.value++
  }, STEP_MS)
}
function pause() {
  playing.value = false
  clearInterval(timer)
}
function stop() {
  pause()
  hour.value = null
}
onBeforeUnmount(() => clearInterval(timer))

const status = computed(() => {
  const s = live.value
  if (!s) return s
  const v = hourTime.value ? props.forecast!.pred[hour.value!] : demoPm.value
  if (v === null) return s
  return {
    ...s, pm2_5: v, level: levelOf(v), aqi: aqiOf(v), change_24h: null,
    ...(hourTime.value ? { time: hourTime.value.toISOString() } : {}),
  }
})
const phase = computed<SkyPhase>(() =>
  hourTime.value
    ? skyPhase(hourTime.value)
    : PHASES.includes(route.query.sky as SkyPhase) ? (route.query.sky as SkyPhase) : skyPhase(now.value),
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
    <SkyScene parallax :pm="pm" :level="status?.level ?? 'good'" :phase="phase" :wind="wind" :wind-dir="windDir" />

    <div class="relative mx-auto grid w-full max-w-7xl gap-10 px-4 pt-28 pb-56 text-white sm:px-6 sm:pt-32 lg:grid-cols-[1fr_20rem]">
      <div>
        <p class="animate-rise flex flex-wrap items-center gap-x-3 gap-y-1 text-sm font-medium tracking-wide text-white/85">
          <span class="relative flex h-2.5 w-2.5">
            <span class="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-emerald-300" />
            <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-300" />
          </span>
          {{ t('hero.place') }} · {{ t('hero.live') }}
          <span v-if="status" class="text-white/70 tabular-nums">
            · {{ hourTime ? t('hero.forecastFor', { time: formatDateHour(hourTime, lang) }) : t('hero.dataFor', { time: formatHour(status.time, lang) }) }}
          </span>
        </p>

        <template v-if="status">
          <!-- relative z-10: строка крупной цифры выше своего текста и иначе перекрывала бы значок «?» -->
          <p class="animate-rise relative z-10 mt-8 flex items-center gap-2 text-sm font-semibold tracking-[0.14em] text-white/70 uppercase" style="animation-delay: 80ms">
            {{ hour != null ? t('hero.pmAhead', { n: hour + 1 }) : t('hero.pm') }} <TermHint term="pm25" glass />
          </p>
          <div class="animate-rise mt-2 flex items-end gap-4" style="animation-delay: 140ms" data-tour="hero">
            <span class="text-[7rem] leading-[0.85] font-extralight tracking-tight drop-shadow-sm sm:text-[10rem]">
              {{ formatNumber(hour != null ? status.pm2_5 : (shownPm ?? status.pm2_5), lang) }}
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
            {{ t(sensitive ? `adviceSensitive.${status.level}` : `advice.${status.level}`) }}
          </p>
          <p class="animate-rise mt-2 text-sm text-white/70" style="animation-delay: 300ms">
            {{ who > 1 ? t('hero.whoTimes', { value: formatNumber(who, lang) }) : t('hero.whoBelow') }} ·
            {{ t('hero.who') }} <TermHint term="who" glass />
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
              v-ripple
              class="inline-flex items-center gap-2 rounded-full bg-black/20 px-4 py-2 text-sm font-medium ring-1 ring-white/25 backdrop-blur-md transition-colors hover:bg-black/30"
              @click="share"
            >
              <Share2 class="h-4 w-4" aria-hidden="true" />{{ t('hero.share') }}
            </button>
            <button
              v-if="forecast"
              v-ripple
              class="inline-flex items-center gap-2 rounded-full bg-black/20 px-4 py-2 text-sm font-medium ring-1 ring-white/25 backdrop-blur-md transition-colors hover:bg-black/30"
              :aria-pressed="playing"
              @click="playing ? pause() : play()"
            >
              <component :is="playing ? Pause : Play" class="h-4 w-4" aria-hidden="true" />
              {{ playing ? t('hero.pause') : t('hero.play') }}
            </button>
          </div>

          <!-- ползунок по часам прогноза: виден, пока прогноз проигрывается или стоит на паузе -->
          <div
            v-if="hour != null && forecast"
            class="mt-4 flex max-w-xl items-center gap-3 rounded-2xl bg-black/25 px-4 py-3 ring-1 ring-white/15 backdrop-blur-md"
          >
            <input
              v-model.number="hour"
              type="range"
              min="0"
              :max="last"
              class="w-full accent-white"
              :aria-label="t('hero.timeline')"
              @input="pause"
            />
            <span class="w-14 shrink-0 text-right text-sm tabular-nums">{{ t('hero.ahead', { n: hour + 1 }) }}</span>
            <button class="rounded-full p-1 text-white/80 hover:bg-white/15 hover:text-white" :aria-label="t('hero.backNow')" @click="stop">
              <X class="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </template>

        <!-- заготовка, пока API просыпается -->
        <div v-else class="mt-10 space-y-4" aria-hidden="true">
          <div class="h-4 w-32 skeleton rounded-full bg-white/20" />
          <div class="h-36 w-80 max-w-full skeleton rounded-3xl bg-white/15" />
          <div class="h-8 w-64 skeleton rounded-full bg-white/20" />
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
