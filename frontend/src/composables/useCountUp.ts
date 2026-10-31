import { onUnmounted, ref, watch, type Ref } from 'vue'

const reducedMotion = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// плавный «докрут» числа к новому значению: PM2.5 на главной, метрики.
// при «уменьшить движение» в системе число меняется сразу
export function useCountUp(target: Ref<number | null | undefined>, duration = 700) {
  const display = ref<number | null>(target.value ?? null)
  let frame = 0

  watch(target, (to, fromValue) => {
    cancelAnimationFrame(frame)
    if (to == null) {
      display.value = null
      return
    }
    const from = display.value ?? fromValue ?? 0
    if (reducedMotion() || from === to) {
      display.value = to
      return
    }
    const start = performance.now()
    const step = (now: number) => {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - (1 - t) ** 4 // easeOutQuart: быстро в начале, мягко в конце
      display.value = from + (to - from) * eased
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
  })

  onUnmounted(() => cancelAnimationFrame(frame))
  return display
}
