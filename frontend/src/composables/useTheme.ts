import { ref, watchEffect } from 'vue'

type Theme = 'light' | 'dark'

const STORAGE_KEY = 'smogcast-theme'

// та же логика, что инлайн-скрипт в index.html: состояние Vue совпадает с уже применённым классом на <html>
function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    // localStorage недоступен (приватный режим) – берём системную тему
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const theme = ref<Theme>(initialTheme())

watchEffect(() => {
  document.documentElement.classList.toggle('dark', theme.value === 'dark')
  document.documentElement.style.colorScheme = theme.value
  try {
    localStorage.setItem(STORAGE_KEY, theme.value)
  } catch {
    // не критично – тема просто не запомнится
  }
})

export function useTheme() {
  // смена темы «расходящимся кругом» от кнопки (View Transitions API); где его нет или анимации
  // отключены – мгновенно
  function toggleTheme(event?: MouseEvent) {
    const next: Theme = theme.value === 'dark' ? 'light' : 'dark'
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (!document.startViewTransition || reduce || !event) {
      theme.value = next
      return
    }
    const { clientX: x, clientY: y } = event
    const radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y))
    document.startViewTransition(() => {
      theme.value = next
      document.documentElement.classList.toggle('dark', next === 'dark')
    }).ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 550, easing: 'cubic-bezier(0.4, 0, 0.2, 1)', pseudoElement: '::view-transition-new(root)' },
      )
    })
  }
  return { theme, toggleTheme }
}
