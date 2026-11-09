<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { Download, LoaderCircle } from 'lucide-vue-next'
import { studioApi } from '../services/studio'

defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ select: [recording: File]; busy: [extracting: boolean] }>()
const videoUrl = ref('')
const clipStart = ref('00:00')
const extracting = ref(false)
const error = ref('')
const clipUrl = ref('')
const clipName = ref('')
const clipDescription = ref('')
const controller = new AbortController()
const startSeconds = computed(() => {
  const timestamp = clipStart.value.trim()
  if (!/^\d+(?::[0-5]\d){0,2}$/.test(timestamp)) return NaN
  return timestamp.split(':').reduce((totalSeconds, part) => totalSeconds * 60 + Number(part), 0)
})

async function extract() {
  if (extracting.value) return
  error.value = ''
  if (!videoUrl.value.trim()) { error.value = 'Cole o link do vídeo do YouTube.'; return }
  if (!Number.isFinite(startSeconds.value) || startSeconds.value > 86400) {
    error.value = 'Informe o início em segundos, mm:ss ou hh:mm:ss, até 24 horas.'
    return
  }
  const selectedStart = startSeconds.value
  extracting.value = true
  emit('busy', true)
  try {
    const audio = await studioApi.youtubeClip(videoUrl.value.trim(), selectedStart,
      AbortSignal.any([controller.signal, AbortSignal.timeout(135000)]))
    if (clipUrl.value) URL.revokeObjectURL(clipUrl.value)
    clipName.value = `youtube-${selectedStart}s-30s.wav`
    clipDescription.value = `30 segundos a partir de ${clipStart.value.trim()}`
    clipUrl.value = URL.createObjectURL(audio)
    emit('select', new File([audio], clipName.value, { type: 'audio/wav' }))
  } catch (problem) {
    if (!controller.signal.aborted) {
      error.value = problem instanceof Error ? problem.message : 'Não consegui extrair esse trecho.'
    }
  } finally {
    extracting.value = false
    emit('busy', false)
  }
}

onUnmounted(() => {
  controller.abort()
  if (clipUrl.value) URL.revokeObjectURL(clipUrl.value)
})
</script>

<template>
  <section class="youtube-audio-clip" aria-labelledby="youtube-clip-title" :aria-busy="extracting">
    <h3 id="youtube-clip-title">Recortar áudio do YouTube</h3>
    <p class="muted small">Cole o link e escolha onde começam os 30 segundos. O resultado contém somente áudio.</p>
    <label for="youtube-video-url">Link do vídeo</label>
    <input id="youtube-video-url" v-model="videoUrl" type="url" maxlength="2048" placeholder="https://www.youtube.com/watch?v=…" :disabled="disabled || extracting">
    <label for="youtube-clip-start">Início do trecho</label>
    <input id="youtube-clip-start" v-model="clipStart" maxlength="12" placeholder="01:20" aria-describedby="youtube-start-help" :disabled="disabled || extracting">
    <p id="youtube-start-help" class="muted small">Ex.: 01:20 recorta de 1min20s até 1min50s. Também aceita segundos ou hh:mm:ss.</p>
    <button type="button" class="secondary-button full" :disabled="disabled || extracting" @click="extract">
      <LoaderCircle v-if="extracting" class="spin" :size="18" />
      {{ extracting ? 'Extraindo áudio…' : 'Extrair 30 segundos' }}
    </button>
    <p v-if="extracting" class="muted small" role="status">Buscando e convertendo o trecho. Pode levar até 2 minutos.</p>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <div v-if="clipUrl" class="youtube-clip-result">
      <p class="muted small" role="status">{{ clipDescription }}. Trecho selecionado como gravação da voz.</p>
      <audio :src="clipUrl" controls preload="metadata" aria-label="Ouvir trecho extraído do YouTube"></audio>
      <a class="secondary-button full" :href="clipUrl" :download="clipName"><Download :size="16" /> Baixar áudio de 30 segundos</a>
    </div>
  </section>
</template>
