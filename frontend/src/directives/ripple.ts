import type { Directive } from 'vue'

// директива v-ripple: от точки нажатия по кнопке расходится мягкая волна цвета текста;
// при «уменьшить движение» в системе волны нет
export const vRipple: Directive<HTMLElement> = {
  mounted(el) {
    el.classList.add('ripple-host')
    el.addEventListener('pointerdown', (event) => {
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
      const rect = el.getBoundingClientRect()
      const size = Math.max(rect.width, rect.height) * 2
      const wave = document.createElement('span')
      wave.className = 'ripple'
      wave.style.width = wave.style.height = `${size}px`
      wave.style.left = `${event.clientX - rect.left - size / 2}px`
      wave.style.top = `${event.clientY - rect.top - size / 2}px`
      el.appendChild(wave)
      wave.addEventListener('animationend', () => wave.remove())
    })
  },
}
