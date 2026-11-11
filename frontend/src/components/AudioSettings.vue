<script setup lang="ts">
defineProps<{ disabled: boolean }>()
const speed = defineModel<number>('speed', { required: true })
const style = defineModel<string>('style', { required: true })
const speedOptions = [0.5, 0.75, 1, 1.1, 1.25, 1.5, 1.75, 2]
</script>

<template>
  <div class="audio-settings">
    <div class="voice-setting"><label for="generation-speed">Velocidade do áudio gerado</label><select id="generation-speed" v-model.number="speed" :disabled="disabled"><option v-for="speedOption in speedOptions" :key="speedOption" :value="speedOption">{{ speedOption.toLocaleString('pt-BR') }}×</option></select></div>
    <div class="voice-setting"><label for="acting">Atuação pelo contexto</label><select id="acting" v-model="style" :disabled="disabled"><option value="neutral">Automática · equilibrada</option><option value="storyteller">Automática · mais expressiva</option><option value="calm">Automática · contida</option></select></div>
  </div>
</template>

<style scoped>
.audio-settings { display: grid; gap: 20px; }
@media (min-width: 768px) { .analysis-settings .audio-settings { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
