<script setup lang="ts">
import { onClickOutside, onKeyStroke, useEventListener } from '@vueuse/core'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

// значок «?» у термина: по нажатию – короткое объяснение простыми словами; закрывается кликом мимо, Esc
// или прокруткой. Подсказка выводится поверх страницы (Teleport в body, position: fixed), поэтому её не
// обрезают таблицы с прокруткой и блоки с overflow: hidden
// term – ключ в разделе terms локалей: terms.<term>Name – название, terms.<term> – объяснение
defineProps<{ term: string; glass?: boolean }>()
const { t } = useI18n()
const WIDTH = 256
const GAP = 8

const open = ref(false)
const button = ref<HTMLElement | null>(null)
const popup = ref<HTMLElement | null>(null)
const place = ref<Record<string, string>>({})

onClickOutside(popup, () => (open.value = false), { ignore: [button] })
onKeyStroke('Escape', () => (open.value = false))
useEventListener(window, 'scroll', () => (open.value = false), { passive: true, capture: true })
useEventListener(window, 'resize', () => (open.value = false))

// под значком; у правого края – влево, у нижнего края экрана – над значком
function toggle() {
  if (!open.value && button.value) {
    const r = button.value.getBoundingClientRect()
    const left = Math.max(GAP, Math.min(r.left, window.innerWidth - WIDTH - GAP))
    const below = r.bottom + 220 < window.innerHeight
    place.value = below
      ? { left: `${left}px`, top: `${r.bottom + GAP}px` }
      : { left: `${left}px`, bottom: `${window.innerHeight - r.top + GAP}px` }
  }
  open.value = !open.value
}
</script>

<template>
  <span class="inline-flex align-middle tracking-normal normal-case">
    <button
      ref="button"
      type="button"
      class="inline-flex h-[18px] w-[18px] items-center justify-center rounded-full text-[11px] leading-none font-bold transition-colors"
      :class="glass ? 'bg-white/20 text-white ring-1 ring-white/30 hover:bg-white/30' : 'bg-surface-2 text-muted ring-1 ring-line hover:text-ink'"
      :aria-expanded="open"
      :aria-label="t('terms.help', { term: t(`terms.${term}Name`) })"
      @click.stop="toggle"
    >
      ?
    </button>
    <Teleport to="body">
      <span
        v-if="open"
        ref="popup"
        role="tooltip"
        class="fixed z-[70] block rounded-xl border border-line bg-surface p-3 text-left text-sm leading-relaxed font-normal text-ink shadow-xl"
        :style="{ ...place, width: `${WIDTH}px` }"
      >
        <span class="block font-semibold">{{ t(`terms.${term}Name`) }}</span>
        {{ t(`terms.${term}`) }}
      </span>
    </Teleport>
  </span>
</template>
