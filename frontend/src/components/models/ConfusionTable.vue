<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { LEVEL_COLOR, LEVELS } from '../../utils/aqi'

// матрица уровней на сутки вперёд: строки – фактический уровень, столбцы – предсказанный (число часов);
// в отчёте пять уровней – «очень вредно» объединено с «опасно»; насыщенность клетки – доля строки
const props = defineProps<{ matrix: number[][] }>()
const { t } = useI18n()
const levels = LEVELS.slice(0, 5)
const shares = computed(() =>
  props.matrix.map((row) => {
    const total = row.reduce((a, b) => a + b, 0)
    return row.map((v) => (total ? v / total : 0))
  }),
)
</script>

<template>
  <div class="overflow-x-auto">
    <table class="w-full min-w-[640px] table-fixed border-separate border-spacing-1 text-sm">
      <thead>
        <tr>
          <th class="w-52 text-left text-xs font-semibold text-faint">{{ t('modelsPage.fact') }} ↓ · {{ t('modelsPage.predicted') }} →</th>
          <th v-for="l in levels" :key="l.key" class="px-1 text-center text-xs font-medium text-muted">
            <span class="mx-auto mb-1 block h-1.5 w-6 rounded-full" :style="{ background: LEVEL_COLOR[l.key] }" />
            {{ t(`levels.${l.key}`) }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, i) in matrix" :key="i">
          <th class="pr-2 text-left text-xs font-medium text-muted">
            <span class="flex items-center gap-2">
              <span class="h-2.5 w-2.5 shrink-0 rounded-full" :style="{ background: LEVEL_COLOR[levels[i].key] }" />
              {{ t(`levels.${levels[i].key}`) }}
            </span>
          </th>
          <td
            v-for="(v, j) in row"
            :key="j"
            class="num rounded-lg px-2 py-2 text-center"
            :class="[i === j ? 'font-semibold ring-1 ring-primary/40' : '', shares[i][j] > 0.5 ? 'text-on-primary' : 'text-ink']"
            :style="{ background: `color-mix(in srgb, var(--primary) ${Math.round(shares[i][j] * 90)}%, var(--surface-2))` }"
          >
            {{ v }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
