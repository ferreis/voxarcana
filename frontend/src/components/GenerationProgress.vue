<script setup lang="ts">
import { computed } from 'vue'
import type { Job } from '../services/studio'
const props = defineProps<{ job: Job }>()
const analysis = computed(() => Math.max(0, Math.min(100, props.job.analysis_percent ?? (props.job.scene ? 100 : 0))))
const audio = computed(() => props.job.status === 'done' ? 100 : props.job.total ? Math.min(99, Math.round(props.job.completed / props.job.total * 100)) : 0)
const audioLabel = computed(() => props.job.status === 'done' ? 'Áudio pronto' : props.job.status === 'review' ? 'Aguardando revisão do elenco' : props.job.stage === 'assembling' ? 'Unindo os trechos' : props.job.total ? `${props.job.completed} de ${props.job.total} trechos gerados` : props.job.stage === 'loading' ? 'Carregando o modelo de voz' : 'Aguardando a interpretação')
</script>
<template>
  <section class="process-progress" aria-label="Andamento da narração">
    <details class="analysis-progress">
      <summary><span>01 · Interpretação pela IA <small>estimativa por etapas · clique para conferir</small></span><strong>{{ analysis }}%</strong></summary>
      <div class="analysis-log"><p>Etapas do processamento e resultados da interpretação.</p><ol v-if="job.analysis_events?.length"><li v-for="(event, index) in job.analysis_events" :key="index">{{ event }}</li></ol><p v-else>{{ job.status === 'queued' ? 'Aguardando na fila.' : 'Preparando a análise.' }}</p><p v-if="job.scene">{{ job.scene.method === 'conservative' ? 'Leitura com pistas explícitas do texto.' : 'Interpretação concluída.' }} Confira personagens, vozes e intenções em “Como a cena foi interpretada”.</p><p v-if="job.status === 'error' || job.status === 'cancelled'">{{ job.status === 'error' ? 'Processamento interrompido por um erro.' : 'Processamento cancelado.' }}</p></div>
    </details>
    <div class="process-track" role="progressbar" aria-label="Interpretação pela IA" :aria-valuenow="analysis" aria-valuemin="0" aria-valuemax="100"><span :style="{ width: `${analysis}%` }"></span></div>
    <div class="audio-progress-label"><span>02 · Geração do áudio <small>{{ audioLabel }}</small></span><strong>{{ audio }}%</strong></div>
    <div class="process-track" role="progressbar" aria-label="Geração do áudio" :aria-valuenow="audio" aria-valuemin="0" aria-valuemax="100"><span :style="{ width: `${audio}%` }"></span></div>
  </section>
</template>
