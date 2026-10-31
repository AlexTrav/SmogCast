<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { LINKS } from '../links'
import LogoMark from './icons/LogoMark.vue'

const { t } = useI18n()
const sections = computed(() => [
  { to: '/', label: t('nav.now') },
  { to: '/history', label: t('nav.history') },
  { to: '/models', label: t('nav.models') },
  { to: '/performance', label: t('nav.performance') },
  { to: '/about', label: t('nav.about') },
])
const links = [
  { href: LINKS.github, label: 'GitHub' },
  { href: LINKS.api, label: 'API' },
  { href: LINKS.openMeteo, label: 'Open-Meteo' },
  { href: LINKS.cams, label: 'Copernicus CAMS' },
]
</script>

<template>
  <footer class="mt-24 border-t border-line bg-surface-2/50 pb-20 md:pb-0">
    <div class="mx-auto grid max-w-7xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.6fr_1fr_1fr]">
      <div>
        <div class="flex items-center gap-2.5">
          <LogoMark class="h-9 w-9" />
          <span class="text-lg font-bold text-ink">Smog<span class="text-primary">Cast</span></span>
        </div>
        <p class="mt-4 max-w-md text-sm leading-relaxed text-muted">{{ t('footer.tagline') }}</p>
        <p class="mt-3 max-w-md text-xs leading-relaxed text-faint">{{ t('footer.project') }}</p>
      </div>
      <div>
        <h3 class="eyebrow">{{ t('footer.sections') }}</h3>
        <ul class="mt-4 space-y-2 text-sm">
          <li v-for="s in sections" :key="s.to">
            <RouterLink :to="s.to" class="text-muted transition-colors hover:text-primary-strong">{{ s.label }}</RouterLink>
          </li>
        </ul>
      </div>
      <div>
        <h3 class="eyebrow">{{ t('footer.links') }}</h3>
        <ul class="mt-4 space-y-2 text-sm">
          <li v-for="l in links" :key="l.href">
            <a :href="l.href" target="_blank" rel="noopener" class="text-muted transition-colors hover:text-primary-strong">{{ l.label }} ↗</a>
          </li>
        </ul>
      </div>
    </div>
    <div class="border-t border-line">
      <div class="mx-auto max-w-7xl space-y-1 px-4 py-5 text-xs leading-relaxed text-faint sm:px-6">
        <p>{{ t('footer.disclaimer') }}</p>
        <p>{{ t('footer.data') }}</p>
      </div>
    </div>
  </footer>
</template>
