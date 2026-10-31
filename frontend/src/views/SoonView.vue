<script setup lang="ts">
import { Mountain } from 'lucide-vue-next'
import { useI18n } from 'vue-i18n'

// заглушка разделов, которые появятся на следующих подпунктах
const { t } = useI18n()
</script>

<template>
  <div class="mx-auto flex min-h-[70vh] max-w-7xl flex-col items-center justify-center px-4 pt-24 text-center">
    <Mountain class="h-12 w-12 text-primary" aria-hidden="true" />
    <h1 class="mt-6 text-3xl font-bold tracking-tight text-ink">{{ t('soon.title') }}</h1>
    <p class="mt-3 text-muted">{{ t('soon.text') }}</p>
  </div>
</template>
