<script setup lang="ts">
import { onClickOutside, onKeyStroke } from '@vueuse/core'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

// значок «?» у термина: по нажатию – короткое объяснение простыми словами; закрывается кликом мимо или Esc
defineProps<{ term: 'pm25' | 'aqi' | 'band' | 'cams' | 'who' | 'blend'; glass?: boolean }>()
const { t } = useI18n()
const open = ref(false)
const right = ref(false) // у правого края экрана подсказка раскрывается влево
const root = ref<HTMLElement | null>(null)

onClickOutside(root, () => (open.value = false))
onKeyStroke('Escape', () => (open.value = false))

function toggle() {
  if (!open.value && root.value) right.value = root.value.getBoundingClientRect().left > window.innerWidth / 2
  open.value = !open.value
}
</script>

<template>
  <span ref="root" class="relative inline-flex align-middle tracking-normal normal-case">
    <button
      type="button"
      class="inline-flex h-[18px] w-[18px] items-center justify-center rounded-full text-[11px] leading-none font-bold transition-colors"
      :class="glass ? 'bg-white/20 text-white ring-1 ring-white/30 hover:bg-white/30' : 'bg-surface-2 text-muted ring-1 ring-line hover:text-ink'"
      :aria-expanded="open"
      :aria-label="t('terms.help', { term: t(`terms.${term}Name`) })"
      @click.stop="toggle"
    >
      ?
    </button>
    <span
      v-if="open"
      role="tooltip"
      class="absolute top-full z-30 mt-2 w-64 rounded-xl border border-line bg-surface p-3 text-left text-sm leading-relaxed font-normal text-ink shadow-xl"
      :class="right ? 'right-0' : 'left-0'"
    >
      <span class="block font-semibold">{{ t(`terms.${term}Name`) }}</span>
      {{ t(`terms.${term}`) }}
    </span>
  </span>
</template>
