<script setup lang="ts">
import { ref } from 'vue'
import { X, Trash2 } from 'lucide-vue-next'
import VoiceFields from './VoiceFields.vue'
import type { Voice, VoiceMetadata } from '../services/studio'
const props = defineProps<{ voices: Voice[]; save: (id: string, metadata: VoiceMetadata) => Promise<void>; remove: (id: string) => Promise<void> }>()
const dialog = ref<HTMLDialogElement | null>(null)
const selected = ref('')
const metadata = ref<VoiceMetadata>({ name: '', role: 'both', gender: 'unknown', kind: 'human' })
const busy = ref(false)
const message = ref('')
const confirmDelete = ref(false)
function choose(id: string) {
  selected.value = id; message.value = ''; confirmDelete.value = false
  const voice = props.voices.find(item => item.id === id)
  if (voice) metadata.value = { name: voice.name, role: voice.role || 'both', gender: voice.gender || 'unknown', kind: voice.kind || 'human' }
}
defineExpose({ open: () => { choose(props.voices.find(v => v.editable)?.id || ''); dialog.value?.showModal() } })
async function submit() {
  busy.value = true; message.value = ''
  try { await props.save(selected.value, { ...metadata.value }); message.value = 'Classificação salva. Será usada nas próximas narrações.' }
  catch (error) { message.value = error instanceof Error ? error.message : 'Não consegui salvar.' }
  finally { busy.value = false }
}
async function remove() {
  busy.value = true; message.value = ''
  try {
    await props.remove(selected.value)
    choose(props.voices.find(v => v.editable && v.id !== selected.value)?.id || '')
    message.value = 'Voz excluída.'
  } catch (error) { message.value = error instanceof Error ? error.message : 'Não consegui excluir.' }
  finally { busy.value = false }
}
</script>
<template>
  <dialog ref="dialog" class="reference-dialog" aria-labelledby="library-title" @cancel="busy && $event.preventDefault()">
    <div class="dialog-heading"><span class="eyebrow">BIBLIOTECA DE VOZES</span><button class="icon-button" aria-label="Fechar biblioteca" :disabled="busy" @click="dialog?.close()"><X :size="20" /></button></div>
    <h2 id="library-title">Seu elenco de vozes.</h2>
    <p>Classifique uma vez. A cada cena, os personagens recebem referências compatíveis com o contexto. Somente suas gravações importadas são usadas.</p>
    <template v-if="selected">
      <label for="library-voice">Gravação importada</label><select id="library-voice" :value="selected" :disabled="busy" @change="choose(($event.target as HTMLSelectElement).value)"><option v-for="item in voices.filter(v => v.editable)" :key="item.id" :value="item.id">{{ item.name }}</option></select>
      <audio class="library-audio" :key="selected" controls preload="none" :src="`/v1/voices/${encodeURIComponent(selected)}/reference`"></audio>
      <form @submit.prevent="submit"><fieldset :disabled="busy"><label for="library-name">Nome</label><input id="library-name" v-model="metadata.name" maxlength="60" required><VoiceFields v-model="metadata" /></fieldset><p v-if="message" role="status">{{ message }}</p><button class="primary-button full" :disabled="busy">{{ busy ? 'Salvando…' : 'Salvar classificação' }}</button></form>
      <div class="voice-delete">
        <template v-if="confirmDelete"><p>Excluir “{{ metadata.name }}” e sua gravação? Essa ação não pode ser desfeita.</p><button class="danger-button" :disabled="busy" @click="remove">Excluir definitivamente</button><button class="text-button" :disabled="busy" @click="confirmDelete = false">Manter voz</button></template>
        <button v-else class="text-button danger-text" :disabled="busy" @click="confirmDelete = true"><Trash2 :size="15" /> Excluir voz</button>
      </div>
    </template>
    <p v-else>Sua biblioteca está vazia. Adicione uma gravação para montar seu elenco.</p>
  </dialog>
</template>
