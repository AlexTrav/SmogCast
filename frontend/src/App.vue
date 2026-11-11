<script setup lang="ts">
import { onMounted, watch } from 'vue'
import FooterSection from './components/FooterSection.vue'
import FreshToast from './components/FreshToast.vue'
import NavBar from './components/NavBar.vue'
import ServerBanner from './components/ServerBanner.vue'
import { useLive } from './composables/useLive'
import { useServerStatus } from './composables/useServerStatus'

const { epoch, wake } = useServerStatus()
const { refresh } = useLive()
onMounted(wake) // будим API сразу при открытии сайта
// сервер проснулся после сна или сбоя: свежее состояние сразу, а страница (ключ ниже) создаётся заново
// и загружает свои данные – запросы, сделанные до пробуждения, уже завершились ошибкой
watch(epoch, () => refresh())
</script>

<template>
  <NavBar />
  <ServerBanner />
  <main>
    <!-- переход между страницами: старая гаснет, новая проявляется снизу -->
    <RouterView v-slot="{ Component, route }">
      <Transition name="page" mode="out-in">
        <component :is="Component" :key="`${route.path}:${epoch}`" />
      </Transition>
    </RouterView>
  </main>
  <FooterSection />
  <FreshToast />
</template>
