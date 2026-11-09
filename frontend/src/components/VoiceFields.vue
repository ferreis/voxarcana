<script setup lang="ts">
import { useId } from 'vue'
const prefix = useId()
import type { VoiceMetadata } from '../services/studio'
const model = defineModel<VoiceMetadata>({ required: true })
</script>
<template>
  <div class="voice-fields">
    <div><label :for="`${prefix}-role`">Uso</label><select :id="`${prefix}-role`" v-model="model.role"><option value="both">Narrador e personagem</option><option value="narrator">Só narrador</option><option value="character">Só personagem</option></select></div>
    <div><label :for="`${prefix}-gender`">Gênero da voz</label><select :id="`${prefix}-gender`" v-model="model.gender"><option value="unknown">Ainda não classificada</option><option value="male">Masculina</option><option value="female">Feminina</option><option value="neutral">Neutra · sem gênero</option></select></div>
    <div><label :for="`${prefix}-kind`">Tipo de voz</label><select :id="`${prefix}-kind`" v-model="model.kind"><option value="human">Humana</option><option value="robot">Robótica</option><option value="entity">Criatura ou entidade</option></select></div>
  </div>
  <p class="field-help">Neutra significa sem gênero definido. Robótica é um tipo de voz separado. A classificação orienta a escolha; o timbre vem da gravação. A voz selecionada como narrador não participa do elenco de personagens dessa cena, mesmo marcada como Ambos.</p>
</template>
