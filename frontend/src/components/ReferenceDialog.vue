<script setup lang="ts">
import { computed, ref } from 'vue'
import { X, Upload, LoaderCircle, Mic2 } from 'lucide-vue-next'
import VoiceFields from './VoiceFields.vue'
import BatchVoiceImport from './BatchVoiceImport.vue'
import YouTubeAudioClip from './YouTubeAudioClip.vue'
import type { VoiceMetadata } from '../services/studio'
const metadata = ref<VoiceMetadata>({ name: '', role: 'both', gender: 'unknown', kind: 'human' })
const props = defineProps<{ save: (name: string, file: File, metadata: VoiceMetadata) => Promise<void> }>()
const dialog = ref<HTMLDialogElement | null>(null)
const name = ref('')
const file = ref<File | null>(null)
const error = ref('')
const busy = ref(false)
const extracting = ref(false)
const batchMode = ref(false)
const batchBusy = ref(false)
const locked = computed(() => busy.value || extracting.value || batchBusy.value)
const clipSession = ref(0)
defineExpose({ open: () => { error.value = ''; dialog.value?.showModal() } })
function select(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0] || null }
async function submit() {
  if (locked.value) return
  if (!file.value || !name.value.trim()) { error.value = 'Dê um nome e escolha uma gravação.'; return }
  if (file.value.size > 50 * 1024 * 1024) { error.value = 'Escolha um arquivo de até 50 MB.'; return }
  busy.value = true; error.value = ''
  try { await props.save(name.value.trim(), file.value, { ...metadata.value, name: name.value.trim() }); dialog.value?.close(); name.value = ''; file.value = null; clipSession.value += 1 }
  catch (problem) { error.value = problem instanceof Error ? problem.message : 'Não consegui salvar essa voz.' }
  finally { busy.value = false }
}
</script>

<template>
  <dialog ref="dialog" class="reference-dialog voice-import-dialog" aria-labelledby="reference-title" @cancel="locked && $event.preventDefault()">
    <div class="import-heading"><div><h2 id="reference-title"><Mic2 :size="22" /> Adicionar voz</h2><p>Português brasileiro · 3 a 50 segundos · fala limpa, sem música.</p></div><button class="icon-button" aria-label="Fechar" :disabled="locked" @click="dialog?.close()"><X :size="20" /></button></div>
    <div class="import-modes"><button type="button" :class="{ active: !batchMode }" :disabled="locked" @click="batchMode = false">Uma voz</button><button type="button" :class="{ active: batchMode }" :disabled="locked" @click="batchMode = true">Importar em massa</button></div>
    <BatchVoiceImport v-show="batchMode" :save="save" @busy="batchBusy = $event" @done="dialog?.close()" />
    <form v-show="!batchMode" @submit.prevent="submit">
      <div class="import-columns">
        <section class="voice-profile" aria-labelledby="voice-profile-title">
          <h3 id="voice-profile-title">Identificação</h3>
          <label for="reference-name">Nome da voz</label><input id="reference-name" v-model="name" maxlength="60" placeholder="Ex.: Narrador da campanha" required :disabled="locked">
          <fieldset :disabled="locked"><VoiceFields v-model="metadata" :show-help="false" /></fieldset>
        </section>
        <section class="voice-source" aria-labelledby="voice-source-title">
          <h3 id="voice-source-title">Gravação de referência</h3>
          <label class="upload-area import-upload" for="reference-file"><Upload :size="24" /><span class="upload-copy"><strong>Escolher arquivo</strong><span>MP3, M4A, MP4, WAV ou FLAC · até 50 MB</span></span><input id="reference-file" type="file" accept=".mp3,audio/mpeg,.mp4,.m4a,.wav,.flac,video/mp4,audio/mp4,audio/wav,audio/flac" :disabled="locked" @change="select"></label>
          <YouTubeAudioClip :key="clipSession" :disabled="busy" @select="file = $event" @busy="extracting = $event" />
        </section>
      </div>
      <p v-if="error" class="error-message import-error" role="alert">{{ error }}</p>
      <div class="import-footer"><div><strong v-if="file" class="selected-recording" :title="file.name">{{ file.name }}</strong><span v-else class="recording-placeholder">Escolha um arquivo ou extraia do YouTube.</span><p>Use uma gravação sua ou autorizada.</p></div><button type="submit" class="primary-button" :disabled="locked"><LoaderCircle v-if="busy" class="spin" :size="18" />{{ busy ? 'Salvando voz…' : 'Adicionar voz' }}</button></div>
    </form>
  </dialog>
</template>

<style scoped>
.reference-dialog.voice-import-dialog { width: min(1040px, calc(100vw - 48px)); padding: 0; }
.import-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding: 25px 30px 22px; border-bottom: 1px solid var(--color-border); }
.import-heading h2 { display: flex; align-items: center; gap: 11px; font: 25px/1.3 var(--font-display); margin: 0; }
.import-heading h2 svg { color: var(--color-primary-soft); flex-shrink: 0; }
.import-heading p { color: var(--color-muted); font-size: 12px; line-height: 1.6; margin: 8px 0 0; }
.import-heading .icon-button { flex-shrink: 0; }
.import-modes { display: flex; gap: 18px; padding: 0 30px; border-bottom: 1px solid var(--color-border); }
.import-modes button { padding: 14px 2px; border: 0; border-bottom: 2px solid transparent; background: none; color: var(--color-muted); cursor: pointer; }
.import-modes button.active { color: var(--color-primary-soft); border-color: var(--color-primary-soft); }
.import-columns { display: grid; grid-template-columns: minmax(250px, .85fr) minmax(0, 1.4fr); }
.voice-profile, .voice-source { padding: 24px 30px 28px; min-width: 0; }
.voice-source { border-left: 1px solid var(--color-border); }
.import-columns h3 { font-size: 13px; font-weight: 600; color: var(--color-paper); margin: 0 0 22px; }
.voice-profile :deep(.voice-fields) { grid-template-columns: minmax(0, 1fr); gap: 16px; margin-top: 16px; }
.import-upload { flex-direction: row; justify-content: flex-start; text-align: left; gap: 16px; padding: 18px; margin: 0; }
.import-upload > svg { flex-shrink: 0; color: var(--color-primary-soft); }
.upload-copy { display: block; min-width: 0; }
.upload-copy strong { display: block; font-size: 12px; font-weight: 500; color: var(--color-paper); }
.upload-copy > span { display: block; margin-top: 5px; font-size: 10px; line-height: 1.6; }
.import-error { padding: 0 30px 16px; margin: 0; }
.import-footer { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 18px 30px; border-top: 1px solid var(--color-border); position: sticky; bottom: 0; background: var(--color-surface); }
.import-footer > div { min-width: 0; }
.selected-recording { display: block; color: var(--color-paper); font-size: 12px; font-weight: 500; overflow-wrap: anywhere; }
.recording-placeholder, .import-footer p { color: var(--color-muted); font-size: 11px; line-height: 1.5; }
.import-footer p { margin: 4px 0 0; }
.import-footer button { flex-shrink: 0; }
@media (max-width: 767px) {
  .reference-dialog.voice-import-dialog { width: calc(100vw - 24px); }
  .import-heading { padding: 20px; }
  .import-columns { grid-template-columns: minmax(0, 1fr); }
  .voice-profile, .voice-source { padding: 20px; }
  .voice-source { border-left: 0; border-top: 1px solid var(--color-border); }
  .voice-profile :deep(.voice-fields) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .voice-profile :deep(.voice-fields > div:first-child) { grid-column: 1/-1; }
  .import-footer { padding: 15px 20px; flex-wrap: wrap; gap: 12px; }
  .import-footer button { flex: 1; }
  .import-error { padding-inline: 20px; }
}
</style>
