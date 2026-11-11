<script setup lang="ts">
import { computed } from 'vue'
import { AudioLines, FileText, LoaderCircle, Square, WandSparkles } from 'lucide-vue-next'

const props = defineProps<{
  canStart: boolean
  canGenerate: boolean
  busy: boolean
  narrationOnly: boolean
  audioStarted: boolean
  hasScene: boolean
  reviewing: boolean
  done: boolean
  cancelling: boolean
  canCancel: boolean
  status: string
  elapsedLabel: string
}>()
defineEmits<{ narrate: []; analyze: []; generate: []; cancel: [] }>()
const generating = computed(() => props.busy && props.audioStarted)
const analyzing = computed(() => props.busy && !props.audioStarted && !props.narrationOnly)
const analysisLabel = computed(() => analyzing.value ? 'Analisando texto…' : props.hasScene ? 'Analisar novamente' : 'Analisar texto e escolher vozes')
const narratorLabel = computed(() => props.busy && props.narrationOnly ? 'Gerando áudio…' : 'Gerar só com narrador')
const statusLabel = computed(() => props.busy ? 'Em andamento' : props.done ? 'Áudio pronto' : props.reviewing ? 'Revisar vozes' : 'Estúdio')
const guidance = computed(() => props.busy ? `${props.elapsedLabel} decorridos`
  : props.reviewing ? 'Confira o elenco abaixo e clique em Gerar áudio.'
    : props.done ? 'Ouça no player do topo. Você pode trocar o narrador ou corrigir as vozes e gerar novamente.'
      : 'Use só o narrador ou analise o texto para definir as vozes dos personagens.')
</script>

<template>
  <section class="generation-controls" aria-label="Controles da narração">
    <div class="generation-overview">
      <div class="generation-feedback" role="status" aria-live="polite">
        <span class="generation-label"><span :class="{ working: busy, complete: done }"></span>{{ statusLabel }}</span>
        <strong>{{ status }}</strong>
        <p>{{ guidance }}</p>
      </div>
      <button v-if="busy" class="secondary-button cancel-generation" :disabled="cancelling || !canCancel" @click="$emit('cancel')"><Square :size="14" /> Cancelar</button>
    </div>
    <div class="generation-options">
      <button class="secondary-button" :disabled="!canStart" :aria-label="narratorLabel" title="Ler todo o texto com a voz do narrador, sem interpretação pela IA" @click="$emit('narrate')">
        <LoaderCircle v-if="busy && narrationOnly" :size="18" class="spin" /><AudioLines v-else :size="18" />
        <span>{{ busy && narrationOnly ? 'Gerando áudio…' : 'Só narrador' }}</span>
      </button>
      <button class="secondary-button" :disabled="!canStart" :aria-label="analysisLabel" title="Interpretar o texto e revisar as vozes dos personagens" @click="$emit('analyze')">
        <LoaderCircle v-if="analyzing" :size="18" class="spin" /><FileText v-else :size="18" />
        <span>{{ analyzing ? 'Analisando…' : hasScene ? 'Analisar novamente' : 'Analisar texto' }}</span>
      </button>
      <button class="primary-button" :disabled="!canGenerate || busy" :aria-label="generating && !narrationOnly ? 'Gerando áudio…' : 'Gerar áudio'" title="Gerar a narração com as vozes revisadas" @click="$emit('generate')">
        <LoaderCircle v-if="generating && !narrationOnly" :size="18" class="spin" /><WandSparkles v-else :size="18" />
        <span>{{ generating && !narrationOnly ? 'Gerando áudio…' : 'Gerar áudio' }}</span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.generation-controls { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 24px; align-items: center; border-block: 1px solid #3c4938; padding: 22px 0; margin-top: 28px; }
.generation-overview { display: flex; align-items: center; gap: 16px; min-width: 0; }
.generation-feedback { min-width: 0; }
.generation-label { display: flex; align-items: center; gap: 7px; color: #b4bdab; font-size: 10px; margin-bottom: 8px; }
.generation-label > span { width: 6px; height: 6px; border-radius: 50%; background: #7c8c74; }
.generation-label .working { background: #d4bd91; box-shadow: 0 0 0 3px #d4bd9115; }
.generation-label .complete { background: #b0c59a; }
.generation-feedback strong { display: block; color: #e1e6d9; font-size: 14px; font-weight: 500; line-height: 1.5; }
.generation-feedback p { font-size: 11px; line-height: 1.6; color: #a2af98; margin: 5px 0 0; }
.generation-options { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.generation-options button { min-height: 46px; justify-content: center; padding: 12px 16px; font-size: 12px; }
.generation-options button > span { margin: 0; }
.generation-options svg { flex-shrink: 0; }
.cancel-generation { margin-left: auto; flex-shrink: 0; }
@media (max-width: 1100px) {
  .generation-controls { grid-template-columns: minmax(0, 1fr); gap: 18px; }
}
@media (max-width: 767px) {
  .generation-controls { margin-top: 22px; padding-block: 18px; }
  .generation-options { gap: 7px; }
  .generation-options button { flex-direction: column; gap: 7px; padding: 10px 5px; font-size: 11px; white-space: normal; line-height: 1.4; }
}
</style>
