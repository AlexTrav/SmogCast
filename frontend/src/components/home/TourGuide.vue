<script setup lang="ts">
import { useEventListener } from '@vueuse/core'
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

// экскурсия при первом визите: четыре шага, каждый подсвечивает блок с [data-tour] и объясняет его словами;
// после «Понятно» или «Пропустить» больше не показывается (повтор – кнопкой «Как читать прогноз»)
const props = defineProps<{ ready: boolean }>()
const { t } = useI18n()
const KEY = 'smogcast-tour'
const STEPS = ['hero', 'days', 'best', 'more']
const PAD = 8

const index = ref(-1)
const rect = ref<DOMRect | null>(null)
const next = ref<HTMLButtonElement | null>(null)
const reduce = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

function seen(): boolean {
  try {
    return localStorage.getItem(KEY) === 'done'
  } catch {
    return true
  }
}

function target(): HTMLElement | null {
  return index.value < 0 ? null : document.querySelector<HTMLElement>(`[data-tour="${STEPS[index.value]}"]`)
}

function measure() {
  rect.value = target()?.getBoundingClientRect() ?? null
}

async function show() {
  const el = target()
  if (!el) return finish()
  el.scrollIntoView({ block: 'center', behavior: reduce() ? 'auto' : 'smooth' })
  setTimeout(measure, reduce() ? 0 : 450)
  measure()
  await nextTick()
  next.value?.focus({ preventScroll: true })
}

function start() {
  index.value = 0
  show()
}

function step() {
  if (index.value < STEPS.length - 1) {
    index.value++
    show()
  } else finish()
}

function finish() {
  index.value = -1
  try {
    localStorage.setItem(KEY, 'done')
  } catch {
    // не критично – экскурсия покажется ещё раз
  }
}

watch(
  () => props.ready,
  (ready) => {
    if (ready && !seen()) setTimeout(start, 1200)
  },
  { immediate: true },
)
useEventListener(window, 'scroll', () => index.value >= 0 && measure(), { passive: true })
useEventListener(window, 'resize', () => index.value >= 0 && measure())
useEventListener(window, 'keydown', (e: KeyboardEvent) => e.key === 'Escape' && index.value >= 0 && finish())

// карточка – под подсвеченным блоком, если снизу хватает места, иначе над ним; по ширине не выходит за экран
const card = computed(() => {
  const r = rect.value
  if (!r) return {}
  const width = Math.min(352, window.innerWidth - 32)
  const left = Math.max(16, Math.min(r.left, window.innerWidth - width - 16))
  const below = r.bottom + PAD + 230 < window.innerHeight
  return below
    ? { left: `${left}px`, top: `${r.bottom + PAD + 12}px`, width: `${width}px` }
    : { left: `${left}px`, bottom: `${Math.max(16, window.innerHeight - r.top + PAD + 12)}px`, width: `${width}px` }
})

defineExpose({ start })
</script>

<template>
  <Teleport to="body">
    <div v-if="index >= 0 && rect" class="fixed inset-0 z-[60]">
      <!-- затемнение всего, кроме подсвеченного блока: огромная тень вокруг «окна» -->
      <div
        class="tour-hole pointer-events-none fixed rounded-2xl ring-2 ring-white/70"
        :style="{
          left: `${rect.left - PAD}px`,
          top: `${rect.top - PAD}px`,
          width: `${rect.width + PAD * 2}px`,
          height: `${rect.height + PAD * 2}px`,
        }"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        class="fixed rounded-2xl border border-line bg-surface p-5 shadow-2xl"
        :style="card"
      >
        <h2 id="tour-title" class="text-lg font-bold text-ink">{{ t(`tour.${STEPS[index]}Title`) }}</h2>
        <p class="mt-1.5 text-[15px] leading-relaxed text-muted">{{ t(`tour.${STEPS[index]}Text`) }}</p>
        <div class="mt-4 flex items-center justify-between gap-3">
          <!-- ход экскурсии – точками, без номеров -->
          <span class="flex gap-1.5" aria-hidden="true">
            <span
              v-for="(s, i) in STEPS"
              :key="s"
              class="h-1.5 rounded-full transition-all"
              :class="i === index ? 'w-5 bg-primary' : 'w-1.5 bg-line'"
            />
          </span>
          <span class="flex gap-2">
            <button class="rounded-full px-3 py-1.5 text-sm text-muted hover:text-ink" @click="finish">{{ t('tour.skip') }}</button>
            <button
              ref="next"
              v-ripple
              class="rounded-full bg-primary px-4 py-1.5 text-sm font-semibold text-on-primary hover:bg-primary-strong"
              @click="step"
            >
              {{ index === STEPS.length - 1 ? t('tour.done') : t('tour.next') }}
            </button>
          </span>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.tour-hole {
  box-shadow: 0 0 0 9999px rgb(7 14 26 / 0.62);
  transition: left 0.3s ease, top 0.3s ease, width 0.3s ease, height 0.3s ease;
}
@media (prefers-reduced-motion: reduce) {
  .tour-hole {
    transition: none;
  }
}
</style>
