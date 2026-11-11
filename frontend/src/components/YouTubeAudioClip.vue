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
    <h3 id="youtube-clip-title">Ou recortar do YouTube</h3>
    <label for="youtube-video-url">Link do vídeo</label>
    <input id="youtube-video-url" v-model="videoUrl" type="url" maxlength="2048" placeholder="https://www.youtube.com/watch?v=…" :disabled="disabled || extracting">
    <div class="clip-extraction-row"><div>
    <label for="youtube-clip-start">Início do trecho</label>
    <input id="youtube-clip-start" v-model="clipStart" maxlength="12" placeholder="01:20" aria-describedby="youtube-start-help" :disabled="disabled || extracting">
    </div><button type="button" class="secondary-button clip-extract-button" :disabled="disabled || extracting" @click="extract">
      <LoaderCircle v-if="extracting" class="spin" :size="18" />
      {{ extracting ? 'Extraindo áudio…' : 'Extrair 30 segundos' }}
    </button></div>
    <p id="youtube-start-help" class="clip-help">Segundos, mm:ss ou hh:mm:ss · recorte de 30 s.</p>
    <p v-if="extracting" class="muted small" role="status">Buscando e convertendo o trecho. Pode levar até 2 minutos.</p>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <div v-if="clipUrl" class="youtube-clip-result">
      <p class="clip-help" role="status">{{ clipDescription }} · pronto para usar.</p>
      <div class="clip-playback">
      <audio :src="clipUrl" controls preload="metadata" aria-label="Ouvir trecho extraído do YouTube"></audio>
      <a class="secondary-button" :href="clipUrl" :download="clipName" aria-label="Baixar áudio de 30 segundos" title="Baixar áudio de 30 segundos"><Download :size="16" /> Baixar WAV</a>
      </div>
    </div>
  </section>
</template>

<style scoped>
.youtube-audio-clip { border-top: 1px solid var(--color-border); margin-top: 22px; padding-top: 20px; }
.youtube-audio-clip h3 { font-size: 12px; font-weight: 500; color: var(--color-primary-soft); margin: 0 0 16px; }
.youtube-audio-clip > label { display: block; margin: 0 0 9px; }
.clip-extraction-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: end; gap: 12px; margin-top: 16px; }
.clip-extraction-row > div { min-width: 0; }
.clip-extract-button { min-height: 42px; justify-content: center; }
.clip-help { font-size: 10px; line-height: 1.6; color: var(--color-muted); margin: 9px 0 0; }
.youtube-clip-result { border-top: 1px solid var(--color-border); margin-top: 18px; padding-top: 4px; }
.clip-playback { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 12px; }
.clip-playback audio { flex: 1; min-width: 190px; width: 0; height: 40px; }
.clip-playback a { flex-shrink: 0; min-height: 40px; text-decoration: none; justify-content: center; }
@media (max-width: 400px) {
  .clip-extraction-row { gap: 8px; }
  .clip-extract-button { padding-inline: 9px; font-size: 10px; }
}
</style>
