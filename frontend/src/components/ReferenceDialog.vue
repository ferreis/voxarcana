<script setup lang="ts">
import { ref } from 'vue'
import { X, Upload, LoaderCircle, Mic2 } from 'lucide-vue-next'
const props = defineProps<{ save: (name: string, file: File) => Promise<void> }>()
const dialog = ref<HTMLDialogElement | null>(null)
const name = ref('')
const file = ref<File | null>(null)
const error = ref('')
const busy = ref(false)
defineExpose({ open: () => { error.value = ''; dialog.value?.showModal() } })
function select(event: Event) { file.value = (event.target as HTMLInputElement).files?.[0] || null }
async function submit() {
  if (!file.value || !name.value.trim()) { error.value = 'Dê um nome e escolha uma gravação.'; return }
  if (file.value.size > 10 * 1024 * 1024) { error.value = 'Escolha um arquivo de até 10 MB.'; return }
  busy.value = true; error.value = ''
  try { await props.save(name.value.trim(), file.value); dialog.value?.close(); name.value = ''; file.value = null }
  catch (problem) { error.value = problem instanceof Error ? problem.message : 'Não consegui salvar essa voz.' }
  finally { busy.value = false }
}
</script>

<template>
  <dialog ref="dialog" class="reference-dialog" aria-labelledby="reference-title" @cancel="busy && $event.preventDefault()">
    <div class="dialog-heading"><span class="eyebrow"><Mic2 :size="15" /> SUA VOZ, SUA HISTÓRIA</span><button class="icon-button" aria-label="Fechar" :disabled="busy" @click="dialog?.close()"><X :size="20" /></button></div>
    <h2 id="reference-title">Uma voz para o seu narrador.</h2>
    <p>Use uma gravação em <strong>português brasileiro</strong>, de 3 a 30 segundos, com uma pessoa falando com clareza, sem música ou ruídos.</p>
    <form @submit.prevent="submit">
      <label for="reference-name">Nome da voz</label><input id="reference-name" v-model="name" maxlength="60" placeholder="Ex.: Narrador da campanha" required :disabled="busy">
      <label class="upload-area" for="reference-file"><Upload :size="24" /><strong>{{ file?.name || 'Escolher gravação' }}</strong><span>WAV ou FLAC · até 10 MB</span><input id="reference-file" type="file" accept=".wav,.flac,audio/wav,audio/flac" :disabled="busy" @change="select"></label>
      <p class="muted small">Use sua voz ou uma gravação que você tenha autorização para utilizar. O timbre vem desse áudio; o texto narrado será o que você escrever.</p>
      <p v-if="error" class="error-message" role="alert">{{ error }}</p>
      <button type="submit" class="primary-button full" :disabled="busy"><LoaderCircle v-if="busy" class="spin" :size="18" />{{ busy ? 'Salvando voz…' : 'Adicionar à minha mesa' }}</button>
    </form>
  </dialog>
</template>
