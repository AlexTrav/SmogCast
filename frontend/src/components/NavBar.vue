<script setup lang="ts">
import { useWindowScroll } from '@vueuse/core'
import { Activity, BrainCircuit, CalendarRange, Info, Moon, Radio, Sun } from 'lucide-vue-next'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { useLocale } from '../composables/useLocale'
import { useTheme } from '../composables/useTheme'
import LogoMark from './icons/LogoMark.vue'

// шапка: на главной прозрачная поверх неба, после прокрутки и на остальных страницах – плотная;
// на телефоне разделы – в нижней панели
const { t } = useI18n()
const route = useRoute()
const { y } = useWindowScroll()
const { theme, toggleTheme } = useTheme()
const { locale, locales } = useLocale()

const overSky = computed(() => route.name === 'home' && y.value < 40)
const items = computed(() => [
  { to: '/', label: t('nav.now'), icon: Radio },
  { to: '/history', label: t('nav.history'), icon: CalendarRange },
  { to: '/models', label: t('nav.models'), icon: BrainCircuit },
  { to: '/performance', label: t('nav.performance'), icon: Activity },
  { to: '/about', label: t('nav.about'), icon: Info },
])
</script>

<template>
  <header
    class="fixed inset-x-0 top-0 z-50 transition-colors duration-300"
    :class="overSky ? 'bg-transparent text-white' : 'border-b border-line bg-bg/85 text-ink backdrop-blur-xl'"
  >
    <div class="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
      <RouterLink to="/" class="flex items-center gap-2.5">
        <LogoMark class="h-8 w-8" />
        <span class="text-lg font-bold tracking-tight">Smog<span :class="overSky ? 'text-white/70' : 'text-primary'">Cast</span></span>
      </RouterLink>
      <nav class="ml-4 hidden items-center gap-1 md:flex">
        <RouterLink
          v-for="item in items"
          :key="item.to"
          :to="item.to"
          class="rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors"
          :class="[
            overSky ? 'text-white/80 hover:bg-white/15 hover:text-white' : 'text-muted hover:bg-surface-2 hover:text-ink',
            route.path === item.to && (overSky ? '!bg-white/20 !text-white' : '!bg-primary-soft !text-primary-strong'),
          ]"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
      <div class="ml-auto flex items-center gap-2">
        <div class="flex rounded-full p-0.5" :class="overSky ? 'bg-white/15' : 'bg-surface-2'" role="group" :aria-label="t('nav.language')">
          <button
            v-for="l in locales"
            :key="l.code"
            class="rounded-full px-2.5 py-1 text-xs font-semibold transition-colors"
            :class="locale === l.code ? (overSky ? 'bg-white text-[#0c1a2e]' : 'bg-surface text-ink shadow-sm') : 'opacity-70 hover:opacity-100'"
            :aria-pressed="locale === l.code"
            @click="locale = l.code"
          >
            {{ l.label }}
          </button>
        </div>
        <button
          class="flex h-9 w-9 items-center justify-center rounded-full transition-colors"
          :class="overSky ? 'bg-white/15 hover:bg-white/25' : 'bg-surface-2 hover:bg-line'"
          :aria-label="t('nav.theme')"
          @click="toggleTheme"
        >
          <Sun v-if="theme === 'dark'" class="h-4.5 w-4.5" />
          <Moon v-else class="h-4.5 w-4.5" />
        </button>
      </div>
    </div>
  </header>

  <!-- нижняя навигация на телефоне -->
  <nav class="fixed inset-x-0 bottom-0 z-50 border-t border-line bg-bg/90 backdrop-blur-xl md:hidden">
    <div class="grid grid-cols-5">
      <RouterLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        class="flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium text-faint"
        exact-active-class="!text-primary-strong"
      >
        <component :is="item.icon" class="h-5 w-5" aria-hidden="true" />
        <span class="max-w-full truncate px-1">{{ item.label }}</span>
      </RouterLink>
    </div>
  </nav>
</template>
