<script setup lang="ts">
import { CloudOff, Flame, Snowflake, Wind } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'
import type { Factor } from '../../types'

// факторы смога на ближайшие сутки: активный – цветной значок и пояснение, неактивный – приглушён
defineProps<{ factors: Factor[] }>()
const { t } = useI18n()
const ICONS = { cold: Snowflake, calm: Wind, dry: CloudOff, heating: Flame }
</script>

<template>
  <ul class="space-y-3">
    <li
      v-for="f in factors"
      :key="f.key"
      class="flex items-start gap-3 rounded-2xl border p-3.5 transition-colors"
      :class="f.active ? 'border-accent/40 bg-accent-soft/60' : 'border-line opacity-60'"
    >
      <span
        class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
        :class="f.active ? 'bg-accent text-white' : 'bg-surface-2 text-faint'"
      >
        <component :is="ICONS[f.key]" class="h-4.5 w-4.5" aria-hidden="true" />
      </span>
      <span>
        <span class="block font-semibold text-ink">
          {{ t(`factors.${f.key}`) }}
          <span v-if="!f.active" class="font-normal text-faint">· {{ t('factors.off') }}</span>
        </span>
        <span class="block text-sm text-muted">{{ t(`factors.${f.key}Text`) }}</span>
      </span>
    </li>
  </ul>
</template>
