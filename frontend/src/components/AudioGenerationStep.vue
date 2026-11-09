<script setup lang="ts">
import { Headphones, LoaderCircle, Square, WandSparkles } from 'lucide-vue-next'

defineProps<{
  ready: boolean
  active: boolean
  busy: boolean
  cancelling: boolean
  canCancel: boolean
  status: string
  elapsedLabel: string
}>()
defineEmits<{ generate: []; cancel: [] }>()
</script>

<template>
  <section class="audio-generation-step" aria-labelledby="audio-step-title">
    <h2 id="audio-step-title">2 · Gerar áudio</h2>
    <p>O áudio só começa a ser gerado quando você confirmar as vozes no botão abaixo.</p>
    <div class="generation-bar">
      <div class="generation-status" role="status" aria-live="polite">
        <span class="status-icon"><LoaderCircle v-if="active && busy" :size="20" class="spin" /><Headphones v-else :size="20" /></span>
        <div>
          <strong>{{ active ? status : ready ? 'Vozes definidas. Pronto para gerar.' : 'Conclua a análise e confira as vozes na etapa 1.' }}</strong>
          <span v-if="active && busy">{{ elapsedLabel }} decorridos</span>
        </div>
      </div>
      <div class="generation-actions">
        <button v-if="active && busy" class="secondary-button" :disabled="cancelling || !canCancel" @click="$emit('cancel')"><Square :size="14" /> Cancelar</button>
        <button class="primary-button" :disabled="!ready || busy" @click="$emit('generate')">
          <LoaderCircle v-if="active && busy" :size="18" class="spin" /><WandSparkles v-else :size="18" />
          {{ active && busy ? 'Gerando áudio…' : 'Gerar áudio' }}
        </button>
      </div>
    </div>
  </section>
</template>
