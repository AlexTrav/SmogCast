import { createApp } from 'vue'
// шрифт – локально, без запросов к Google Fonts; в нём есть все казахские буквы (проверено по глифам)
import '@fontsource-variable/onest'
import App from './App.vue'
import { vReveal } from './directives/reveal'
import { vRipple } from './directives/ripple'
import { i18n, initialLocale } from './i18n'
import router from './router'
import './style.css'

document.documentElement.lang = initialLocale

const app = createApp(App)
app.use(router)
app.use(i18n)
app.directive('reveal', vReveal) // плавное появление блоков при прокрутке
app.directive('ripple', vRipple) // волна от нажатия на кнопки
app.mount('#app')

// офлайн: service worker держит оболочку сайта и последние ответы API (только в собранном сайте)
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register(`${import.meta.env.BASE_URL}sw.js`, { scope: import.meta.env.BASE_URL }).catch(() => {})
}
