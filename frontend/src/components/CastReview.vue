<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Scene, Voice, ReviewedLine } from '../services/studio'
const props = defineProps<{ scene: Scene; voices: Voice[]; narrator: string; disabled: boolean; stale: boolean }>()
const emit = defineEmits<{ change: [lines: ReviewedLine[] | null] }>()
interface Actor { key: string; name: string; gender: string; voice: string; saved: boolean }
const actors = ref<Actor[]>([])
const speakerForLine = ref<Record<number, string>>({})
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
function options(actor: Actor) {
  return characterVoices.value.filter(voice => actor.gender === 'unknown' || voice.gender === actor.gender || voice.gender === 'unknown')
}
watch([characterVoices, () => actors.value.map(actor => actor.gender)], () => {
  for (const actor of actors.value) if (!options(actor).some(voice => voice.id === actor.voice)) actor.voice = ''
}, { deep: true })
const ready = computed(() => !props.disabled && !props.stale && dialogue.value.every(line => {
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
    <fieldset :disabled="disabled || stale">
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
