<script setup lang="ts">
import { AppWindow, Bike, CircleAlert, CircleCheck, CircleX, Fan, Shield } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSensitive } from '../../composables/useSensitive'
import type { AqiLevel } from '../../types'
import { type Tip, type Verdict, tips } from '../../utils/advice'
import TermHint from '../TermHint.vue'

// «Что делать сейчас»: четыре совета значками по текущему уровню; переключатель чувствительности здесь же –
// при нём советы сразу становятся строже, это видно
const props = defineProps<{ level: AqiLevel }>()
const { t } = useI18n()
const { sensitive } = useSensitive()
const ICONS: Record<Tip, unknown> = { sport: Bike, windows: AppWindow, mask: Shield, purifier: Fan }
const MARK: Record<Verdict, unknown> = { ok: CircleCheck, caution: CircleAlert, no: CircleX }
// цвет состояния всегда вместе со значком и словами
const TONE: Record<Verdict, string> = {
  ok: 'bg-aqi-good/15 text-ink',
  caution: 'bg-aqi-sensitive/20 text-ink',
  no: 'bg-aqi-unhealthy/15 text-ink',
}
const MARK_COLOR: Record<Verdict, string> = { ok: 'text-aqi-good', caution: 'text-aqi-sensitive', no: 'text-aqi-unhealthy' }
const list = computed(() => tips(props.level, sensitive.value))
</script>

<template>
  <div>
    <ul class="grid grid-cols-2 gap-2.5">
      <li v-for="tip in list" :key="tip.key" class="rounded-2xl p-3 transition-colors" :class="TONE[tip.verdict]">
        <span class="flex items-center justify-between gap-2">
          <component :is="ICONS[tip.key]" class="h-5 w-5 text-ink" aria-hidden="true" />
          <span class="flex items-center gap-1">
            <component :is="MARK[tip.verdict]" class="h-4 w-4" :class="MARK_COLOR[tip.verdict]" aria-hidden="true" />
            <TermHint :term="`tip_${tip.key}`" />
          </span>
        </span>
        <span class="mt-2 block text-xs text-muted">{{ t(`tips.${tip.key}`) }}</span>
        <span class="block text-sm font-semibold">{{ t(`tips.${tip.key}_${tip.verdict}`) }}</span>
      </li>
    </ul>
    <!-- переключатель-тумблер: настоящий чекбокс (role="switch") спрятан, рисуется его «дорожка» -->
    <div class="mt-3 flex items-center justify-between gap-3 rounded-xl bg-surface-2 px-3.5 py-2.5">
      <label for="sensitive" class="min-w-0 cursor-pointer">
        <span class="flex items-center gap-1.5 text-sm font-medium text-ink">{{ t('sensitive.label') }}</span>
        <span class="block text-xs text-muted">{{ t('sensitive.hint') }}</span>
      </label>
      <span class="flex shrink-0 items-center gap-2">
        <TermHint term="sensitive" />
        <label class="relative inline-flex cursor-pointer">
          <input id="sensitive" v-model="sensitive" type="checkbox" role="switch" class="peer sr-only" />
          <span
            class="relative h-6 w-11 rounded-full bg-line transition-colors peer-checked:bg-primary peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-primary after:absolute after:top-0.5 after:left-0.5 after:h-5 after:w-5 after:rounded-full after:bg-white after:shadow after:transition-transform peer-checked:after:translate-x-5"
            aria-hidden="true"
          />
        </label>
      </span>
    </div>
  </div>
</template>
