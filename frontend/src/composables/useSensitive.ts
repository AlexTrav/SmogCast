import { ref, watch } from 'vue'

// «У меня чувствительность к смогу» (дети, пожилые, астма, болезни сердца): советы строже; выбор общий для
// всех блоков страницы и запоминается в браузере
const KEY = 'smogcast-sensitive'

function read(): boolean {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

const sensitive = ref(read())
watch(sensitive, (value) => {
  try {
    localStorage.setItem(KEY, value ? '1' : '0')
  } catch {
    // не критично – выбор просто не запомнится между визитами
  }
})

export function useSensitive() {
  return { sensitive }
}
