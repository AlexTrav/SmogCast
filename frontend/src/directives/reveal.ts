import type { Directive } from 'vue'

// один общий наблюдатель на все элементы с v-reveal – экономнее, чем создавать по одному на элемент
const observer = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.setAttribute('data-reveal', 'visible') // включает CSS-переход в style.css
        observer.unobserve(entry.target) // анимация проигрывается один раз
      }
    }
  },
  { threshold: 0.12 },
)

// директива v-reveal: элемент плавно появляется, когда попадает в область видимости при скролле.
// v-reveal="i" – порядковый номер в группе: элементы появляются «лесенкой» с задержкой 70 мс
export const vReveal: Directive<HTMLElement, number | undefined> = {
  mounted(el, binding) {
    if (binding.value) el.style.setProperty('--reveal-i', String(binding.value))
    el.setAttribute('data-reveal', '')
    observer.observe(el)
  },
  unmounted(el) {
    observer.unobserve(el)
  },
}
