<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import TermHint from '../TermHint.vue'
import type { AppLocale, Verify } from '../../types'
import { formatNumber } from '../../utils/format'
import { modelColor, modelTerm, REFERENCE } from '../../utils/models'

// гонка моделей: средняя ошибка живых прогнозов за последние сутки; при новом часе строки плавно
// переставляются; прогноз CAMS – отдельно, нейтральным цветом (на коротком горизонте он почти совпадает с рядом)
const props = defineProps<{ verify: Verify }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)

const rows = computed(() =>
  Object.entries(props.verify.models)
    .filter(([key, m]) => key !== REFERENCE && m.mae != null)
    .map(([key, m]) => ({ key, mae: m.mae as number, hours: m.hours }))
    .sort((a, b) => a.mae - b.mae),
)
const max = computed(() => Math.max(...rows.value.map((r) => r.mae), 1))
const cams = computed(() => props.verify.models[REFERENCE])
</script>

<template>
  <div>
    <TransitionGroup tag="ol" move-class="transition-transform duration-700" class="space-y-3">
      <li v-for="r in rows" :key="r.key" class="grid grid-cols-[9rem_1fr_4rem] items-center gap-3 text-sm">
        <span class="flex items-center gap-2 truncate text-ink" :class="r.key === verify.default_model ? 'font-semibold' : ''">
          <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ background: modelColor(r.key) }" />
          <span class="truncate">{{ t(`modelNames.${r.key}`) }}</span>
          <TermHint :term="modelTerm(r.key)" />
        </span>
        <span class="h-2.5 overflow-hidden rounded-full bg-surface-2">
          <span class="block h-full rounded-full transition-[width] duration-700" :style="{ width: `${(r.mae / max) * 100}%`, background: modelColor(r.key) }" />
        </span>
        <span class="num text-right text-ink">{{ formatNumber(r.mae, lang) }}</span>
      </li>
    </TransitionGroup>
    <p v-if="cams && cams.mae != null" class="mt-4 border-t border-line pt-3 text-xs text-faint">
      {{ t('modelNames.cams') }}: <span class="num">{{ formatNumber(cams.mae, lang) }}</span> · {{ t('modelsPage.camsNote') }}
    </p>
  </div>
</template>
