<script setup lang="ts">
import { Footprints, Wind } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSensitive } from '../../composables/useSensitive'
import type { AppLocale } from '../../types'
import { LEVEL_COLOR } from '../../utils/aqi'
import { formatHour, formatNumber } from '../../utils/format'
import { type DayOutlook, type Window, windows } from '../../utils/outlook'

// «Когда лучше выйти»: самые чистые часы сегодня и завтра для прогулки и для проветривания
const props = defineProps<{ days: DayOutlook[] }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const DAY_NAMES = ['outlook.today', 'outlook.tomorrow', 'outlook.after']

const rows = computed(() => props.days.slice(0, 2).map((d) => ({ offset: d.offset, ...windows(d) })))
const kinds = computed(() => [
  { key: 'walk' as const, icon: Footprints, title: t('outlook.walk'), note: t('outlook.walkNote') },
  { key: 'air' as const, icon: Wind, title: t('outlook.air'), note: t('outlook.airNote') },
])

// вредный воздух даже в лучшие часы – честно говорим, что лучше переждать; чувствительным – уже с уровня
// «вредно для чувствительных»
const { sensitive } = useSensitive()
const harmful = (w: Window) =>
  [...(sensitive.value ? ['sensitive'] : []), 'unhealthy', 'very_unhealthy', 'hazardous'].includes(w.level)
const span = (w: Window, kind: 'walk' | 'air') =>
  kind === 'air' ? formatHour(w.start, lang.value) : `${formatHour(w.start, lang.value)}–${formatHour(w.end, lang.value)}`
</script>

<template>
  <div class="space-y-5">
    <section v-for="k in kinds" :key="k.key">
      <h3 class="flex items-center gap-2 font-semibold text-ink">
        <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-soft text-primary-strong">
          <component :is="k.icon" class="h-4 w-4" aria-hidden="true" />
        </span>
        {{ k.title }}
        <span class="text-xs font-normal text-faint">· {{ k.note }}</span>
      </h3>
      <ul class="mt-2 space-y-1.5">
        <li v-for="r in rows" :key="r.offset" class="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span class="w-20 shrink-0 text-muted">{{ t(DAY_NAMES[r.offset]) }}</span>
          <template v-if="r[k.key]">
            <span class="num font-semibold text-ink">{{ span(r[k.key]!, k.key) }}</span>
            <span class="inline-flex items-center gap-1.5 text-muted">
              <span class="h-2 w-2 rounded-full" :style="{ background: LEVEL_COLOR[r[k.key]!.level] }" />
              {{ t(`levels.${r[k.key]!.level}`) }}, {{ t('outlook.about', { value: formatNumber(r[k.key]!.mean, lang, 0) }) }}
            </span>
            <span v-if="harmful(r[k.key]!)" class="basis-full pl-22 text-xs text-accent">{{ t('outlook.stayHome') }}</span>
          </template>
          <span v-else class="text-faint">{{ t('outlook.none') }}</span>
        </li>
      </ul>
    </section>
  </div>
</template>
