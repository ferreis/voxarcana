<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { Play, Pause, Square, Download, AudioLines } from 'lucide-vue-next'
const props = defineProps<{ src: string; title: string }>()
const audio = ref<HTMLAudioElement | null>(null)
const playing = ref(false)
const current = ref(0)
const duration = ref(0)
const rate = ref(1)
const error = ref('')
const filename = computed(() => `${props.title.replace(/[^\p{L}\p{N}\s_-]/gu, '').trim() || 'voxarcana'}.wav`)
const time = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
watch(() => props.src, () => { playing.value = false; current.value = 0; duration.value = 0; error.value = '' })
watch(rate, value => { if (audio.value) audio.value.playbackRate = value })
async function toggle() {
  if (!audio.value || !props.src) return
  try {
    if (playing.value) audio.value.pause()
    else { audio.value.playbackRate = rate.value; await audio.value.play() }
  } catch { error.value = 'Não consegui reproduzir. Baixe o WAV para ouvir no seu player.' }
}
function stop() { if (audio.value) { audio.value.pause(); audio.value.currentTime = 0 } }
function seek(event: Event) { if (audio.value) audio.value.currentTime = Number((event.target as HTMLInputElement).value) }
</script>

<template>
  <section class="player" aria-label="Reprodução da narração">
    <audio v-if="src" ref="audio" :src="src" preload="metadata" @play="playing = true" @pause="playing = false" @ended="playing = false"
      @timeupdate="current = audio?.currentTime || 0" @loadedmetadata="duration = audio?.duration || 0" @error="error = 'O áudio não pôde ser aberto. Tente gerar novamente.'" />
    <div class="player-track"><span class="track-icon"><AudioLines :size="22" aria-hidden="true" /></span><div><strong>{{ src ? title : 'Sua próxima narração' }}</strong><span>{{ src ? 'Áudio pronto para ouvir e baixar' : 'O áudio aparecerá aqui quando estiver pronto' }}</span></div></div>
    <div class="player-center">
      <div class="playback-actions"><button class="icon-button" :disabled="!src" aria-label="Parar reprodução" @click="stop"><Square :size="15" /></button><button class="play-button" :disabled="!src" :aria-label="playing ? 'Pausar narração' : 'Reproduzir narração'" @click="toggle"><Pause v-if="playing" :size="20" fill="currentColor" /><Play v-else :size="20" fill="currentColor" /></button><label class="speed-label"><span class="sr-only">Velocidade do player</span><select v-model="rate" aria-label="Velocidade do player" title="Só altera a reprodução"><option :value="0.5">0,5×</option><option :value="0.75">0,75×</option><option :value="1">1×</option><option :value="1.25">1,25×</option><option :value="1.5">1,5×</option><option :value="1.75">1,75×</option><option :value="2">2×</option></select></label></div>
      <div class="timeline"><span>{{ time(current) }}</span><input type="range" aria-label="Posição da reprodução" :max="duration || 1" step="0.1" :value="current" :disabled="!src" @input="seek"><span>{{ time(duration) }}</span></div>
    </div>
    <a class="download-button" :class="{ disabled: !src }" :href="src || undefined" :download="filename" :aria-disabled="!src" :tabindex="src ? 0 : -1"><Download :size="17" /> <span>Baixar WAV</span></a>
    <p v-if="error" class="player-error" role="alert">{{ error }}</p>
  </section>
</template>
