<script setup lang="ts">
import { ref } from 'vue'
import { X, LoaderCircle } from 'lucide-vue-next'
import { studioApi, type SavedCharacter, type Voice } from '../services/studio'
const props = defineProps<{ voices: Voice[] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const records = ref<SavedCharacter[]>([])
const selected = ref('')
const name = ref('')
const gender = ref('unknown')
const voice = ref('')
const busy = ref(false)
const error = ref('')
const notice = ref('')
function choose(id: string) {
  selected.value = id; error.value = ''; notice.value = ''
  const record = records.value.find(r => r.id === id)
  if (record) { name.value = record.name; gender.value = record.gender; voice.value = record.voice_id }
}
async function open() {
  dialog.value?.showModal(); busy.value = true; error.value = ''; notice.value = ''
  try { records.value = await studioApi.characters(); choose(records.value[0]?.id || '') }
  catch (problem) { error.value = problem instanceof Error ? problem.message : 'Não consegui abrir o elenco.' }
  finally { busy.value = false }
}
defineExpose({ open })
async function save() {
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const updated = await studioApi.updateCharacter(selected.value, { name: name.value.trim(), gender: gender.value, voice_id: voice.value })
    records.value = records.value.map(r => r.id === selected.value ? updated : r)
    choose(updated.id); notice.value = 'Escolha salva para as próximas cenas.'
  } catch (problem) { error.value = problem instanceof Error ? problem.message : 'Não consegui salvar.' }
  finally { busy.value = false }
}
</script>
<template>
  <dialog ref="dialog" class="reference-dialog" aria-labelledby="character-library-title" @cancel="busy && $event.preventDefault()">
    <div class="dialog-heading"><span class="eyebrow">PERSONAGENS E SUAS VOZES</span><button class="icon-button" aria-label="Fechar elenco salvo" :disabled="busy" @click="dialog?.close()"><X :size="20" /></button></div>
    <h2 id="character-library-title">Elenco salvo.</h2>
    <p>As escolhas ficam salvas neste computador, mesmo após reiniciar. Quando estes personagens voltarem, suas vozes e gênero serão reutilizados.</p>
    <p v-if="busy" role="status"><LoaderCircle :size="16" class="spin" /> Carregando…</p>
    <p v-if="error" class="error-message" role="alert">{{ error }}</p>
    <template v-if="records.length">
      <label for="saved-character">Personagem salvo</label><select id="saved-character" :value="selected" :disabled="busy" @change="choose(($event.target as HTMLSelectElement).value)"><option v-for="record in records" :key="record.id" :value="record.id">{{ record.name }} · {{ record.voice_name || 'Voz removida' }}</option></select>
      <form @submit.prevent="save"><fieldset :disabled="busy">
        <label for="saved-character-name">Nome</label><input id="saved-character-name" v-model="name" maxlength="80" required>
        <label for="saved-character-gender">Gênero</label><select id="saved-character-gender" v-model="gender"><option value="male">Masculino</option><option value="female">Feminino</option><option value="neutral">Neutro</option><option value="unknown">Não identificado</option></select>
        <label for="saved-character-voice">Voz</label><select id="saved-character-voice" v-model="voice" required><option v-if="!voices.some(v => v.id === voice && v.role !== 'narrator')" :value="voice" disabled>Voz indisponível · escolha outra</option><option v-for="item in voices.filter(v => v.role !== 'narrator')" :key="item.id" :value="item.id">{{ item.name }}</option></select>
      </fieldset><p v-if="notice" role="status">{{ notice }}</p><button class="primary-button full" :disabled="busy || !name.trim() || !voices.some(v => v.id === voice && v.role !== 'narrator')">Salvar personagem</button></form>
    </template>
    <p v-else-if="!busy && !error">Nenhum personagem salvo. Ao confirmar as vozes após analisar uma cena, elas aparecerão aqui.</p>
  </dialog>
</template>
