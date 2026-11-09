<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { studioApi, type SavedCharacter, type Scene, type Voice, type ReviewedLine } from '../services/studio'
import { characterIdentity, findSavedCharacter, voiceUsedByAnother } from '../utils/characterVoices'
const props = defineProps<{ scene: Scene; voices: Voice[]; narrator: string; disabled: boolean; stale: boolean }>()
const emit = defineEmits<{ change: [lines: ReviewedLine[] | null] }>()
interface Actor { key: string; name: string; gender: string; voice: string; saved: boolean }
const actors = ref<Actor[]>([])
const speakerForLine = ref<Record<number, string>>({})
const savedCharacters = ref<SavedCharacter[]>([])
const allowUsedVoice = ref(false)
const loadingCharacters = ref(true)
const characterError = ref('')
let characterRequest = 0
async function loadCharacters() {
  const requestNumber = ++characterRequest
  loadingCharacters.value = true; characterError.value = ''
  try {
    const characters = await studioApi.characters()
    if (requestNumber === characterRequest) savedCharacters.value = characters
  } catch {
    if (requestNumber === characterRequest) characterError.value = 'Não consegui conferir as vozes do elenco salvo.'
  } finally { if (requestNumber === characterRequest) loadingCharacters.value = false }
}
const dialogue = computed(() => props.scene.segments.filter(segment => segment.kind === 'dialogue'))
const characterVoices = computed(() => props.voices.filter(voice => voice.id !== props.narrator && voice.role !== 'narrator'))
watch(() => props.scene, scene => {
  const found = new Map<string, Actor>()
  const assignments: Record<number, string> = {}
  for (const span of scene.segments.filter(segment => segment.kind === 'dialogue')) {
    const key = span.speaker
    if (!found.has(key)) found.set(key, { key, name: key, gender: span.gender || 'unknown', voice: span.voice_id || '', saved: !!span.character_saved })
    assignments[span.id] = key
  }
  actors.value = [...found.values()]; speakerForLine.value = assignments
}, { immediate: true })
watch(() => props.scene, () => { allowUsedVoice.value = false; void loadCharacters() }, { immediate: true })
function actorIdentity(actor: Actor) {
  return savedActor(actor)?.id || characterIdentity(actor.name)
}
function savedActor(actor: Actor) {
  return findSavedCharacter(savedCharacters.value, actor.name) || findSavedCharacter(savedCharacters.value, actor.key)
}
function compatibleVoices(actor: Actor) {
  const savedCharacter = savedActor(actor)
  return characterVoices.value.filter(voice => {
    if (actor.gender !== 'unknown' && voice.gender !== actor.gender && voice.gender !== 'unknown') return false
    if (allowUsedVoice.value) return true
    return !voiceUsedByAnother(savedCharacters.value, voice.id, savedCharacter?.id)
  })
}
function options(actor: Actor) {
  return compatibleVoices(actor).filter(voice => allowUsedVoice.value
    || !actors.value.some(otherActor => otherActor.key !== actor.key && otherActor.voice === voice.id && actorIdentity(otherActor) !== actorIdentity(actor)))
}
watch([characterVoices, savedCharacters, allowUsedVoice, () => actors.value.map(actor => [actor.name, actor.gender, actor.voice])], () => {
  if (loadingCharacters.value) return
  const assignedVoices = new Map<string, string>()
  for (const actor of actors.value) {
    const owner = assignedVoices.get(actor.voice)
    if (!compatibleVoices(actor).some(voice => voice.id === actor.voice)
      || (!allowUsedVoice.value && owner !== undefined && owner !== actorIdentity(actor))) actor.voice = ''
    if (actor.voice) assignedVoices.set(actor.voice, actorIdentity(actor))
  }
}, { deep: true })
const ready = computed(() => !props.disabled && !props.stale && !loadingCharacters.value && !characterError.value && dialogue.value.every(line => {
  const actor = actors.value.find(candidate => candidate.key === speakerForLine.value[line.id])
  return actor && actor.name.trim() && actor.name.trim().toLocaleLowerCase('pt-BR') !== 'narrador' && options(actor).some(voice => voice.id === actor.voice)
}))
function addActor() { actors.value.push({ key: crypto.randomUUID(), name: 'Novo personagem', gender: 'unknown', voice: '', saved: false }) }
const reviewedLines = computed<ReviewedLine[] | null>(() => {
  if (!ready.value) return null
  return dialogue.value.map(line => {
    const actor = actors.value.find(candidate => candidate.key === speakerForLine.value[line.id])!
    return { id: line.id, speaker: actor.name.trim(), gender: actor.gender, voice_id: actor.voice }
  })
})
watch(reviewedLines, lines => emit('change', lines), { immediate: true })
</script>
<template>
  <section class="cast-review" aria-labelledby="cast-review-title">
    <h2 id="cast-review-title">Confira as vozes da cena</h2>
    <p>Confira ou altere as vozes dos personagens. Quando terminar, clique em Gerar áudio.</p>
    <p v-if="stale" class="error-message">O texto mudou. Clique em Analisar novamente.</p>
    <p v-if="loadingCharacters" class="field-help" role="status">Conferindo as vozes do elenco salvo…</p>
    <p v-if="characterError" class="error-message" role="alert">{{ characterError }} <button class="text-button" @click="loadCharacters">Tentar novamente</button></p>
    <fieldset :disabled="disabled || stale || loadingCharacters || !!characterError">
      <label v-if="dialogue.length" class="reuse-voice-option"><input v-model="allowUsedVoice" type="checkbox"> Usar voz já utilizada</label>
      <p v-if="dialogue.length" class="field-help">Por padrão, vozes escolhidas por outros personagens da cena ou do elenco salvo ficam ocultas. Apelidos do mesmo personagem compartilham a voz.</p>
      <div v-for="(actor, index) in actors" :key="actor.key" class="actor-row" :class="{ 'saved-actor': actor.saved }">
        <div><label :for="`actor-name-${index}`">Personagem <span v-if="actor.saved" class="saved-badge">Salvo</span></label><input :id="`actor-name-${index}`" v-model="actor.name" maxlength="80"></div>
        <div><label :for="`actor-gender-${index}`">Gênero</label><select :id="`actor-gender-${index}`" v-model="actor.gender"><option value="unknown">Não identificado</option><option value="male">Masculino</option><option value="female">Feminino</option><option value="neutral">Neutro</option></select></div>
        <div><label :for="`actor-voice-${index}`">Voz do personagem</label><select :id="`actor-voice-${index}`" v-model="actor.voice"><option value="">Escolha uma voz</option><option v-for="voiceOption in options(actor)" :key="voiceOption.id" :value="voiceOption.id">{{ voiceOption.name }}</option></select><small v-if="!options(actor).length">Importe ou classifique outra voz compatível na biblioteca.</small></div>
      </div>
      <button v-if="dialogue.length" class="text-button" type="button" @click="addActor">Adicionar personagem para separar falas</button>
      <p v-if="!actors.length">Esta cena contém somente narração. Será usada a voz selecionada do narrador.</p>
      <details v-if="dialogue.length" class="review-lines"><summary>Conferir quem diz cada fala · {{ dialogue.length }} falas</summary><div v-for="line in dialogue" :key="line.id" class="review-line"><label :for="`line-speaker-${line.id}`">Quem fala?</label><select :id="`line-speaker-${line.id}`" v-model="speakerForLine[line.id]"><option v-for="actor in actors" :key="actor.key" :value="actor.key">{{ actor.name }}</option></select><p>{{ line.text }}</p></div></details>
    </fieldset>
  </section>
</template>
