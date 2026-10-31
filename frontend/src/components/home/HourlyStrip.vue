<script setup lang="ts">
import { ChevronLeft, ChevronRight, CloudRain, Navigation2, Snowflake, Wind } from 'lucide-vue-next'
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AppLocale, Status, Weather } from '../../types'
import TermHint from '../TermHint.vue'
import { LEVEL_COLOR, levelOf } from '../../utils/aqi'
import { formatDay, formatHour, formatNumber, localDay, localHour } from '../../utils/format'
import type { HourPoint } from '../../utils/outlook'

// почасовая лента, как в приложениях погоды: первым – «сейчас» (факт), дальше 72 ч прогноза;
// высота столбика – PM2.5, цвет – уровень (уровень есть и в подписи для экранного диктора); под ним – погода
// того же часа: температура, ветер со стрелкой «куда дует», осадки. Мороз и штиль – подсвечены: они копят смог
const props = defineProps<{
  points: HourPoint[]
  now: { pm: number; time: string } | null
  day: number
  weather?: Weather | null
  nowWeather?: Status['weather'] | null
}>()
const COLD = 0 // °C – ниже топят сильнее, холодный воздух запирает дым у земли
const CALM = 3 // км/ч – слабее почти не уносит дым (как пороги факторов в API)
const WET = 0.1 // мм за час – осадки вымывают частицы

interface HourWeather {
  temp: number | null
  wind: number | null
  dir: number | null
  precip: number | null
}

// погода по часу: прогноз ECMWF из /api/weather, для «сейчас» – погода последнего часа ряда
const weatherAt = computed(() => {
  const w = props.weather
  const map = new Map<number, HourWeather>()
  if (!w) return map
  const t0 = new Date(w.start).getTime()
  const v = w.values
  ;(v.temp ?? []).forEach((_, i) =>
    map.set(t0 + i * 3_600_000, { temp: v.temp?.[i] ?? null, wind: v.wind?.[i] ?? null, dir: v.wind_dir?.[i] ?? null, precip: v.precip?.[i] ?? null }),
  )
  return map
})
function hourWeather(time: Date, current: boolean): HourWeather | null {
  if (current) {
    const n = props.nowWeather
    return n ? { temp: n.temp, wind: n.wind, dir: n.wind_dir, precip: null } : null
  }
  return weatherAt.value.get(time.getTime()) ?? null
}
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)

const items = computed(() => {
  const head = props.now ? [{ time: new Date(props.now.time), pm: props.now.pm, level: levelOf(props.now.pm), current: true }] : []
  return [...head, ...props.points.map((p) => ({ ...p, current: false }))]
})
const top = computed(() => Math.max(...items.value.map((i) => i.pm), 1))
const today = computed(() => localDay(new Date()))

// подпись суток над первым часом каждых суток
function dayLabel(time: Date, index: number): string | null {
  if (index > 0 && localHour(time) !== 0) return null
  const key = localDay(time)
  if (key === today.value) return t('outlook.today')
  if (key === localDay(new Date(), 1)) return t('outlook.tomorrow')
  return formatDay(time, lang.value)
}

// выбранные в карточках сутки – прокрутить ленту к их первому часу
const list = ref<HTMLElement | null>(null)
watch(
  () => props.day,
  async (offset) => {
    await nextTick()
    const target = list.value?.querySelector<HTMLElement>(`[data-day="${localDay(new Date(), offset)}"]`)
    if (target && list.value) list.value.scrollTo({ left: target.offsetLeft - list.value.offsetLeft, behavior: 'smooth' })
  },
)

function scrollBy(direction: number) {
  list.value?.scrollBy({ left: direction * list.value.clientWidth * 0.8, behavior: 'smooth' })
}
</script>

<template>
  <div>
    <!-- что в ленте: подписи рядов и объяснения -->
    <p v-if="weather" class="mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
      <span class="flex items-center gap-1">{{ t('strip.pm') }} <TermHint term="pm25" /></span>
      <span class="flex items-center gap-1"><Snowflake class="h-3 w-3 text-sky-600 dark:text-sky-300" aria-hidden="true" />{{ t('strip.temp') }} <TermHint term="cold" /></span>
      <span class="flex items-center gap-1"><Wind class="h-3 w-3 text-accent" aria-hidden="true" />{{ t('strip.wind') }} <TermHint term="calm" /></span>
      <span class="flex items-center gap-1"><CloudRain class="h-3 w-3 text-sky-600 dark:text-sky-300" aria-hidden="true" />{{ t('strip.precip') }} <TermHint term="precip" /></span>
    </p>
    <div class="relative">
      <ol
        ref="list"
        class="strip flex snap-x gap-1 overflow-x-auto scroll-smooth pb-2"
        :aria-label="t('outlook.hourly')"
        tabindex="0"
      >
        <li
          v-for="(h, i) in items"
          :key="h.time.getTime() + (h.current ? 'now' : '')"
          :data-day="h.current ? null : localDay(h.time)"
          class="flex w-14 shrink-0 snap-start flex-col items-center"
          :aria-label="t('outlook.hourLabel', { time: formatHour(h.time, lang), value: formatNumber(h.pm, lang, 0), level: t(`levels.${h.level}`) })"
        >
          <span class="h-4 text-[11px] font-semibold whitespace-nowrap text-primary-strong">{{ h.current ? '' : dayLabel(h.time, i - (now ? 1 : 0)) }}</span>
          <span
            class="mt-1 flex w-full flex-col items-center rounded-xl py-2"
            :class="h.current ? 'bg-primary-soft' : ''"
          >
            <span class="text-xs" :class="h.current ? 'font-semibold text-primary-strong' : 'text-faint'">
              {{ h.current ? t('outlook.now') : formatHour(h.time, lang).slice(0, 2) }}
            </span>
            <span class="mt-1.5 flex h-16 items-end">
              <span
                class="bar block w-2.5 rounded-full"
                :style="{ height: `${Math.max(8, (h.pm / top) * 100)}%`, background: LEVEL_COLOR[h.level] }"
              />
            </span>
            <span class="num mt-1.5 text-sm font-semibold text-ink">{{ formatNumber(h.pm, lang, 0) }}</span>
            <template v-for="w in [hourWeather(h.time, h.current)]" :key="'w'">
              <span v-if="w" class="mt-2 flex w-full flex-col items-center gap-1 border-t border-line/70 pt-2 text-[11px] tabular-nums">
                <span class="flex items-center gap-0.5" :class="w.temp != null && w.temp < COLD ? 'font-semibold text-sky-600 dark:text-sky-300' : 'text-muted'">
                  <Snowflake v-if="w.temp != null && w.temp < COLD" class="h-3 w-3" aria-hidden="true" />
                  {{ w.temp == null ? '–' : `${formatNumber(w.temp, lang, 0)}°` }}
                </span>
                <span class="flex items-center gap-0.5" :class="w.wind != null && w.wind < CALM ? 'font-semibold text-accent' : 'text-muted'">
                  <Navigation2 v-if="w.dir != null" class="h-3 w-3" :style="{ transform: `rotate(${(w.dir + 180) % 360}deg)` }" aria-hidden="true" />
                  {{ w.wind == null ? '–' : formatNumber(w.wind, lang, 0) }}
                </span>
                <span class="flex h-4 items-center gap-0.5 text-sky-600 dark:text-sky-300">
                  <template v-if="w.precip != null && w.precip >= WET">
                    <CloudRain class="h-3 w-3" aria-hidden="true" />{{ formatNumber(w.precip, lang, 1) }}
                  </template>
                </span>
              </span>
            </template>
          </span>
        </li>
      </ol>
      <button
        class="absolute top-1/2 -left-3 hidden h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-line bg-surface text-muted shadow-sm hover:text-ink sm:flex"
        :aria-label="t('outlook.back')"
        @click="scrollBy(-1)"
      >
        <ChevronLeft class="h-4 w-4" aria-hidden="true" />
      </button>
      <button
        class="absolute top-1/2 -right-3 hidden h-8 w-8 -translate-y-1/2 items-center justify-center rounded-full border border-line bg-surface text-muted shadow-sm hover:text-ink sm:flex"
        :aria-label="t('outlook.forward')"
        @click="scrollBy(1)"
      >
        <ChevronRight class="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.strip {
  scrollbar-width: thin;
  /* края ленты плавно уходят в фон – видно, что её можно листать */
  mask-image: linear-gradient(to right, transparent, #000 12px, #000 calc(100% - 24px), transparent);
}
</style>
