<script setup lang="ts">
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AppLocale } from '../../types'
import { LEVEL_COLOR, levelOf } from '../../utils/aqi'
import { formatDay, formatHour, formatNumber, localDay, localHour } from '../../utils/format'
import type { HourPoint } from '../../utils/outlook'

// почасовая лента, как в приложениях погоды: первым – «сейчас» (факт), дальше 72 ч прогноза;
// высота столбика – PM2.5, цвет – уровень (уровень есть и в подписи для экранного диктора)
const props = defineProps<{ points: HourPoint[]; now: { pm: number; time: string } | null; day: number }>()
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
</template>

<style scoped>
.strip {
  scrollbar-width: thin;
  /* края ленты плавно уходят в фон – видно, что её можно листать */
  mask-image: linear-gradient(to right, transparent, #000 12px, #000 calc(100% - 24px), transparent);
}
</style>
