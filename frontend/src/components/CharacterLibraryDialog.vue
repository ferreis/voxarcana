<script setup lang="ts">
import { computed, ref } from 'vue'
import { X, LoaderCircle } from 'lucide-vue-next'
import { studioApi, type SavedCharacter, type Voice } from '../services/studio'
import { voiceUsedByAnother } from '../utils/characterVoices'
const props = defineProps<{ voices: Voice[] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const records = ref<SavedCharacter[]>([])
const selected = ref('')
const name = ref('')
const gender = ref('unknown')
const voice = ref('')
const aliases = ref('')
const allowUsedVoice = ref(false)
const availableVoices = computed(() => props.voices.filter(candidate => candidate.role !== 'narrator'
  && (allowUsedVoice.value || !voiceUsedByAnother(records.value, candidate.id, selected.value))))
const busy = ref(false)
const error = ref('')
const notice = ref('')
function choose(id: string) {
  selected.value = id; error.value = ''; notice.value = ''; allowUsedVoice.value = false
  const record = records.value.find(r => r.id === id)
  if (record) { name.value = record.name; gender.value = record.gender; voice.value = record.voice_id; aliases.value = record.aliases.join(', ') }
}
async function open() {
  dialog.value?.showModal(); busy.value = true; error.value = ''; notice.value = ''
  try { records.value = await studioApi.characters(); choose(records.value[0]?.id || '') }
  catch (problem) { error.value = problem instanceof Error ? problem.message : 'Não consegui abrir o elenco.' }
  finally { busy.value = false }
}
defineExpose({ open })
async function save() {
  if (!availableVoices.value.some(candidate => candidate.id === voice.value)) return
  busy.value = true; error.value = ''; notice.value = ''
  try {
    const updated = await studioApi.updateCharacter(selected.value, { name: name.value.trim(), gender: gender.value, voice_id: voice.value,
      aliases: aliases.value.split(/[,\n]/).map(alias => alias.trim()).filter(Boolean) })
    records.value = records.value.map(r => r.id === selected.value ? updated : r)
    choose(updated.id); notice.value = 'Personagem salvo. Analise novamente o texto para aplicar os vínculos à cena.'
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
        <label for="saved-character-aliases">Apelidos e sobrenomes</label><input id="saved-character-aliases" v-model="aliases" maxlength="1600" placeholder="Ex.: Almeida, Corvo" aria-describedby="saved-aliases-help">
        <p id="saved-aliases-help" class="field-help">Separe por vírgulas. Esses nomes identificam o mesmo personagem e usam a mesma voz nas próximas análises.</p>
        <label for="saved-character-gender">Gênero</label><select id="saved-character-gender" v-model="gender"><option value="male">Masculino</option><option value="female">Feminino</option><option value="neutral">Neutro</option><option value="unknown">Não identificado</option></select>
        <label class="reuse-voice-option"><input v-model="allowUsedVoice" type="checkbox"> Usar voz já utilizada</label>
        <label for="saved-character-voice">Voz</label><select id="saved-character-voice" v-model="voice" required><option v-if="!availableVoices.some(candidate => candidate.id === voice)" :value="voice" disabled>Voz indisponível ou já utilizada · escolha outra ou permita reutilizar</option><option v-for="availableVoice in availableVoices" :key="availableVoice.id" :value="availableVoice.id">{{ availableVoice.name }}</option></select>
      </fieldset><p v-if="notice" role="status">{{ notice }}</p><button class="primary-button full" :disabled="busy || !name.trim() || !availableVoices.some(candidate => candidate.id === voice)">Salvar personagem</button></form>
    </template>
    <p v-else-if="!busy && !error">Nenhum personagem salvo. Ao confirmar as vozes após analisar uma cena, elas aparecerão aqui.</p>
  </dialog>
</template>
