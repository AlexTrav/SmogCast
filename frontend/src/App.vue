<script setup lang="ts">
import { onMounted } from 'vue'
import FooterSection from './components/FooterSection.vue'
import NavBar from './components/NavBar.vue'
import ServerBanner from './components/ServerBanner.vue'
import { useServerStatus } from './composables/useServerStatus'

const { wake } = useServerStatus()
onMounted(wake) // будим API сразу при открытии сайта
</script>

<template>
  <NavBar />
  <ServerBanner />
  <main>
    <RouterView />
  </main>
  <FooterSection />
</template>
