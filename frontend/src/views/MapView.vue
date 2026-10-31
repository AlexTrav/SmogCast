<script setup lang="ts">
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { Pause, Play } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { api } from '../api/client'
import LevelBadge from '../components/LevelBadge.vue'
import { useTheme } from '../composables/useTheme'
import type { AppLocale, AqiLevel, Region } from '../types'
import { LEVELS } from '../utils/aqi'
import { formatDateHour, formatNumber } from '../utils/format'
import { cellsAt, cellsGeoJSON, hourTime, nowHour } from '../utils/region'

// карта долины: сетка CAMS 5x5 поверх 3D-рельефа Заилийского Алатау; ползунок и «Проиграть» – сутки назад
// и трое суток вперёд; подложка CARTO (без ключа), рельеф – открытые плитки высот AWS Terrain Tiles
const { t, locale } = useI18n()
const lang = computed(() => locale.value as AppLocale)
const { theme } = useTheme()

const STYLES = {
  light: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
  dark: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
}
const TERRAIN = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'
const TERRAIN_ATTRIBUTION = '<a href="https://registry.opendata.aws/terrain-tiles/" target="_blank" rel="noopener">AWS Terrain Tiles</a>'
const STEP_MS = 350
const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches

const region = ref<Region | null>(null)
const hour = ref(0)
const playing = ref(false)
const ready = ref(false)
const failed = ref(false)
const el = ref<HTMLElement | null>(null)
const map = shallowRef<maplibregl.Map | null>(null)
let markers: maplibregl.Marker[] = []
let timer: ReturnType<typeof setInterval> | undefined

function css(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}
function colors(): Record<AqiLevel, string> {
  return {
    good: css('--color-aqi-good'),
    moderate: css('--color-aqi-moderate'),
    sensitive: css('--color-aqi-sensitive'),
    unhealthy: css('--color-aqi-unhealthy'),
    very_unhealthy: css('--color-aqi-very-unhealthy'),
    hazardous: css('--color-aqi-hazardous'),
  }
}

const cells = computed(() => (region.value ? cellsAt(region.value, hour.value) : []))
const city = computed(() => cells.value.find((c) => c.city) ?? null)
const worst = computed(() => (cells.value.length ? cells.value.reduce((a, b) => (b.pm > a.pm ? b : a)) : null))
const time = computed(() => (region.value ? hourTime(region.value, hour.value) : null))
const now = computed(() => (region.value ? nowHour(region.value) : 0))
const when = computed(() => (hour.value < now.value ? 'past' : hour.value === now.value ? 'now' : 'future'))

// подписи клеток: значение PM2.5 и стрелка – куда дует ветер (направление в данных – откуда, поэтому +180°)
function chip(pm: number, dir: number | null, color: string): string {
  const arrow = dir == null ? '' : `<span class="map-arrow" style="transform:rotate(${(dir + 180) % 360}deg)">↑</span>`
  return `<span class="map-dot" style="background:${color}"></span><b>${formatNumber(pm, lang.value, 0)}</b>${arrow}`
}

function paint() {
  const m = map.value
  const r = region.value
  if (!m || !r) return
  const palette = colors()
  const source = m.getSource('cells') as maplibregl.GeoJSONSource | undefined
  source?.setData(cellsGeoJSON(r, hour.value, palette))
  if (!markers.length) {
    markers = cells.value.map((c) => {
      const node = document.createElement('div')
      node.className = 'map-chip'
      return new maplibregl.Marker({ element: node }).setLngLat([c.lon, c.lat]).addTo(m)
    })
  }
  cells.value.forEach((c, i) => {
    const node = markers[i]?.getElement()
    if (node) {
      node.innerHTML = chip(c.pm, c.dir, palette[c.level])
      node.classList.toggle('map-city', c.city)
    }
  })
}

// слои после загрузки стиля (и заново после смены темы): рельеф с тенью, клетки CAMS под подписями городов
function addLayers() {
  const m = map.value
  const r = region.value
  if (!m || !r) return
  const dark = theme.value === 'dark'
  const dem = { type: 'raster-dem' as const, tiles: [TERRAIN], tileSize: 256, encoding: 'terrarium' as const, maxzoom: 13 }
  m.addSource('dem', { ...dem, attribution: TERRAIN_ATTRIBUTION })
  m.addSource('shade', dem)
  const firstSymbol = m.getStyle().layers.find((l) => l.type === 'symbol')?.id
  m.addLayer({
    id: 'hillshade', type: 'hillshade', source: 'shade',
    paint: { 'hillshade-exaggeration': dark ? 0.5 : 0.35, 'hillshade-shadow-color': dark ? '#000000' : '#51627a' },
  }, firstSymbol)
  m.addSource('cells', { type: 'geojson', data: cellsGeoJSON(r, hour.value, colors()) })
  m.addLayer({
    id: 'cells-fill', type: 'fill', source: 'cells',
    paint: { 'fill-color': ['get', 'color'], 'fill-opacity': dark ? 0.5 : 0.42 },
  }, firstSymbol)
  m.addLayer({
    id: 'cells-line', type: 'line', source: 'cells',
    paint: {
      'line-color': dark ? '#ffffff' : '#1d2b3d',
      'line-opacity': ['case', ['get', 'city'], 0.9, 0.22],
      'line-width': ['case', ['get', 'city'], 2.5, 0.8],
    },
  }, firstSymbol)
  m.setTerrain({ source: 'dem', exaggeration: 1.5 })
  paint()
}

function createMap() {
  if (!el.value || map.value) return
  try {
    const m = new maplibregl.Map({
      container: el.value,
      style: STYLES[theme.value],
      // взгляд с севера на юг, как на первом экране: город впереди, хребет Заилийского Алатау – на заднем плане
      center: [76.9, 43.15],
      zoom: 8.2,
      pitch: 62,
      bearing: 172,
      maxPitch: 75,
      attributionControl: { compact: true },
      fadeDuration: still ? 0 : 300,
    })
    m.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')
    m.on('style.load', addLayers)
    m.on('load', () => (ready.value = true))
    // клик по клетке – значение словами и ветер
    m.on('click', 'cells-fill', (e) => {
      const c = cells.value.find((x) => {
        const [lon, lat] = [e.lngLat.lng, e.lngLat.lat]
        return Math.abs(x.lon - lon) <= 0.2 && Math.abs(x.lat - lat) <= 0.2
      })
      if (!c) return
      new maplibregl.Popup({ closeButton: false, offset: 8 })
        .setLngLat(e.lngLat)
        .setHTML(
          `<b>${formatNumber(c.pm, lang.value, 0)} ${t('hero.unit')}</b> · ${t(`levels.${c.level}`)}`
          + (c.wind == null ? '' : `<br>${t('map.wind', { value: formatNumber(c.wind, lang.value, 0) })}`),
        )
        .addTo(m)
    })
    m.on('mouseenter', 'cells-fill', () => (m.getCanvas().style.cursor = 'pointer'))
    m.on('mouseleave', 'cells-fill', () => (m.getCanvas().style.cursor = ''))
    map.value = m
  } catch {
    failed.value = true // нет WebGL – значения остаются в таблице
  }
}

onMounted(async () => {
  try {
    region.value = await api.region()
    hour.value = nowHour(region.value)
    createMap()
  } catch {
    // плашка сервера покажет, что API недоступен
  }
})

watch(hour, paint)
watch(lang, paint)
// смена темы – другая подложка; слои добавятся заново на style.load. Рельеф отключается заранее: иначе
// MapLibre рисует кадр с рельефом из источника старого стиля, которого уже нет, и падает
watch(theme, (value) => {
  const m = map.value
  if (!m) return
  m.setTerrain(null)
  m.setStyle(STYLES[value], { diff: false })
})

function play() {
  if (!region.value) return
  if (hour.value >= region.value.hours - 1) hour.value = 0
  playing.value = true
  clearInterval(timer)
  timer = setInterval(() => {
    if (!region.value || hour.value >= region.value.hours - 1) return pause()
    hour.value++
  }, STEP_MS)
}
function pause() {
  playing.value = false
  clearInterval(timer)
}
onBeforeUnmount(() => {
  clearInterval(timer)
  map.value?.remove()
})
</script>

<template>
  <div class="mx-auto max-w-7xl px-4 pt-28 sm:px-6">
    <p class="eyebrow animate-rise">{{ t('map.eyebrow') }}</p>
    <h1 class="animate-rise mt-3 text-4xl font-bold tracking-tight text-ink sm:text-5xl" style="animation-delay: 60ms">{{ t('map.title') }}</h1>
    <p class="animate-rise mt-4 max-w-3xl text-lg leading-relaxed text-muted" style="animation-delay: 120ms">{{ t('map.intro') }}</p>

    <div class="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <section class="card relative min-w-0 overflow-hidden">
        <div ref="el" class="h-[62vh] min-h-[420px] w-full" :aria-label="t('map.title')" role="region" />
        <div v-if="!ready && !failed" class="skeleton absolute inset-x-0 top-0 flex h-[62vh] min-h-[420px] items-center justify-center bg-surface-2 text-sm text-muted">
          {{ t('map.loading') }}
        </div>
        <p v-if="failed" class="absolute inset-x-0 top-0 flex h-[62vh] min-h-[420px] items-center justify-center bg-surface-2 p-8 text-center text-muted">{{ t('map.noWebgl') }}</p>

        <!-- время: ползунок по часам сетки и «Проиграть» – под картой, чтобы не закрывать подписи источников -->
        <div v-if="region" class="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-line px-4 py-3">
          <button v-ripple class="btn-ghost shrink-0 !px-3 !py-1.5" :aria-pressed="playing" @click="playing ? pause() : play()">
            <component :is="playing ? Pause : Play" class="h-4 w-4" aria-hidden="true" />
            {{ playing ? t('map.pause') : t('map.play') }}
          </button>
          <input
            v-model.number="hour"
            type="range"
            min="0"
            :max="region.hours - 1"
            class="min-w-40 flex-1 accent-primary"
            :aria-label="t('map.hour')"
            @input="pause"
          />
          <span class="num text-sm whitespace-nowrap text-ink">
            {{ time ? formatDateHour(time, lang) : '' }}
            <span class="ml-1 rounded-full px-2 py-0.5 text-xs" :class="when === 'future' ? 'bg-primary-soft text-primary-strong' : 'bg-surface-2 text-muted'">
              {{ t(`map.${when}`) }}
            </span>
          </span>
        </div>
      </section>

      <aside class="min-w-0 space-y-6">
        <section class="card p-5">
          <h2 class="text-lg font-bold text-ink">{{ t('map.selected') }}</h2>
          <dl v-if="city && worst" class="mt-4 space-y-4 text-sm">
            <div>
              <dt class="text-muted">{{ t('map.cityCell') }}</dt>
              <dd class="mt-1 flex flex-wrap items-center gap-2">
                <span class="num text-2xl font-semibold text-ink">{{ formatNumber(city.pm, lang, 0) }}</span>
                <span class="text-muted">{{ t('hero.unit') }}</span>
                <LevelBadge :level="city.level" />
              </dd>
              <dd v-if="city.wind != null" class="mt-1 text-muted">{{ t('map.wind', { value: formatNumber(city.wind, lang, 0) }) }}</dd>
            </div>
            <div>
              <dt class="text-muted">{{ t('map.maxCell') }}</dt>
              <dd class="mt-1 flex flex-wrap items-center gap-2">
                <span class="num text-2xl font-semibold text-ink">{{ formatNumber(worst.pm, lang, 0) }}</span>
                <LevelBadge :level="worst.level" />
              </dd>
              <dd class="num mt-1 text-muted">{{ formatNumber(worst.lat, lang, 1) }}° N, {{ formatNumber(worst.lon, lang, 1) }}° E</dd>
            </div>
          </dl>
          <div v-else class="skeleton mt-4 h-40 rounded-2xl bg-surface-2" />
        </section>
        <section class="card p-5">
          <h2 class="text-lg font-bold text-ink">{{ t('map.legend') }}</h2>
          <ul class="mt-3 space-y-1.5 text-sm">
            <li v-for="l in LEVELS" :key="l.key" class="flex items-center justify-between gap-2">
              <span class="flex items-center gap-2 text-ink">
                <span class="h-3 w-5 rounded-sm" :style="{ background: `var(--color-aqi-${l.key.replace('_', '-')})` }" />
                {{ t(`levels.${l.key}`) }}
              </span>
              <span class="num text-faint">{{ Number.isFinite(l.upTo) ? `≤ ${formatNumber(l.upTo, lang)}` : '' }}</span>
            </li>
          </ul>
          <p class="mt-4 text-xs leading-relaxed text-muted">{{ t('map.honest') }}</p>
        </section>
      </aside>
    </div>

    <!-- те же значения таблицей: север сверху, как на карте -->
    <details v-if="region" class="mt-6 text-sm">
      <summary class="cursor-pointer font-medium text-muted hover:text-ink">{{ t('map.table') }}</summary>
      <div class="mt-3 overflow-x-auto rounded-2xl border border-line">
        <table class="w-full">
          <thead class="bg-surface-2 text-xs text-faint">
            <tr>
              <th class="px-3 py-2 text-left font-semibold">{{ t('map.latLon') }}</th>
              <th v-for="lon in region.lons" :key="lon" class="num px-3 py-2 text-right font-semibold">{{ formatNumber(lon, lang, 1) }}° E</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(lat, i) in [...region.lats].reverse()" :key="lat" class="border-t border-line/70">
              <th class="num px-3 py-1.5 text-left font-normal text-muted">{{ formatNumber(lat, lang, 1) }}° N</th>
              <td
                v-for="(lon, j) in region.lons"
                :key="lon"
                class="num px-3 py-1.5 text-right text-ink"
                :class="cells.find((c) => c.lat === lat && c.lon === lon)?.city ? 'font-bold' : ''"
              >
                {{ region.pm2_5[hour][region.lats.length - 1 - i][j] == null ? '–' : formatNumber(region.pm2_5[hour][region.lats.length - 1 - i][j] as number, lang, 0) }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </details>
  </div>
</template>

<style>
/* подписи клеток на карте (маркеры MapLibre вне scoped-стилей) */
.map-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 7px;
  border-radius: 9999px;
  background: rgb(255 255 255 / 0.88);
  color: #0f1b2b;
  font: 600 12px/1.4 'Onest Variable', system-ui, sans-serif;
  box-shadow: 0 1px 4px rgb(0 0 0 / 0.25);
  pointer-events: none;
}
.dark .map-chip {
  background: rgb(10 18 32 / 0.85);
  color: #e8eef7;
}
.map-chip.map-city {
  outline: 2px solid var(--primary);
}
.map-dot {
  width: 8px;
  height: 8px;
  border-radius: 9999px;
}
.map-arrow {
  display: inline-block;
  font-size: 11px;
  opacity: 0.75;
}
</style>
