<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { AppLocale, Bucket, ModelsReport } from '../../types'
import { formatNumber } from '../../utils/format'
import { modelColor } from '../../utils/models'

// рейтинг на тестовом году: MAE по горизонтам, выигрыш над «как вчера», доля угаданных уровней AQI
// и попадание в интервал 80 % (на первых сутках); † – значимо хуже модели по умолчанию
const props = defineProps<{ report: ModelsReport['test'] }>()
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const BUCKETS: Bucket[] = ['1–24', '25–48', '49–72']

const rows = computed(() =>
  Object.entries(props.report.models)
    .map(([key, m]) => {
      const dm = props.report.dm_vs_default[key]?.['1–24']
      return {
        key,
        mae: BUCKETS.map((b) => m.buckets[b].mae),
        mean: m.mae_1_72,
        skill: m.buckets['1–24'].skill,
        level: props.report.aqi[key]?.['1–24']?.level_exact,
        cover: m.buckets['1–24'].cover80,
        worse: dm != null && dm.p_value < 0.05 && dm.mae_diff < 0,
      }
    })
    .sort((a, b) => a.mean - b.mean),
)
const percent = (v: number | undefined) => (v == null || Number.isNaN(v) ? '–' : `${formatNumber(v * 100, lang.value, 0)} %`)
</script>

<template>
  <div class="overflow-x-auto">
    <table class="w-full min-w-[760px] text-sm">
      <thead>
        <tr class="border-b border-line text-left text-xs tracking-wide text-faint uppercase">
          <th class="py-2.5 pr-3 font-semibold">{{ t('modelsPage.model') }}</th>
          <th v-for="b in BUCKETS" :key="b" class="px-3 py-2.5 text-right font-semibold">{{ b }}</th>
          <th class="px-3 py-2.5 text-right font-semibold">{{ t('modelsPage.mean') }}</th>
          <th class="px-3 py-2.5 text-right font-semibold">{{ t('modelsPage.skill') }}</th>
          <th class="px-3 py-2.5 text-right font-semibold">{{ t('modelsPage.levels') }}</th>
          <th class="py-2.5 pl-3 text-right font-semibold">{{ t('modelsPage.cover') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="r in rows"
          :key="r.key"
          class="border-b border-line/70 last:border-0"
          :class="r.key === report.meta.default ? 'bg-primary-soft/50 font-semibold' : ''"
        >
          <td class="py-2.5 pr-3">
            <span class="flex items-center gap-2 text-ink">
              <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ background: modelColor(r.key) }" />
              {{ t(`modelNames.${r.key}`) }}
              <span v-if="r.key === report.meta.default" class="rounded-full bg-primary px-2 py-0.5 text-[11px] font-semibold text-on-primary">
                {{ t('modelsPage.defaultModel') }}
              </span>
              <span v-if="r.worse" class="text-faint" :title="t('modelsPage.worse')">†</span>
            </span>
          </td>
          <td v-for="(v, i) in r.mae" :key="i" class="num px-3 py-2.5 text-right text-ink">{{ formatNumber(v, lang, 2) }}</td>
          <td class="num px-3 py-2.5 text-right text-ink">{{ formatNumber(r.mean, lang, 2) }}</td>
          <td class="num px-3 py-2.5 text-right text-muted">{{ percent(r.skill) }}</td>
          <td class="num px-3 py-2.5 text-right text-muted">{{ percent(r.level) }}</td>
          <td class="num py-2.5 pl-3 text-right text-muted">{{ percent(r.cover) }}</td>
        </tr>
      </tbody>
    </table>
    <p class="mt-3 text-xs text-faint">† {{ t('modelsPage.worse') }}</p>
  </div>
</template>
