<script setup lang="ts">
import { computed } from 'vue'
import type { Job } from '../services/studio'
const props = defineProps<{ job: Job; narrationOnly?: boolean }>()
const analysis = computed(() => Math.max(0, Math.min(100, props.job.analysis_percent ?? (props.job.scene ? 100 : 0))))
const audio = computed(() => props.job.status === 'done' ? 100 : props.job.total ? Math.min(99, Math.round(props.job.completed / props.job.total * 100)) : 0)
const audioLabel = computed(() => props.job.status === 'done' ? 'Áudio pronto' : props.job.status === 'review' ? 'Aguardando revisão do elenco' : props.job.stage === 'assembling' ? 'Unindo os trechos' : props.job.total ? `${props.job.completed} de ${props.job.total} trechos gerados` : props.job.stage === 'loading' ? 'Carregando o modelo de voz' : props.narrationOnly ? 'Preparando a voz do narrador' : 'Aguardando a interpretação')
</script>
<template>
  <section class="process-progress" aria-label="Andamento da narração">
    <p v-if="narrationOnly" class="muted small">Sem interpretação pela IA. Todo o texto será lido com a voz do narrador.</p>
    <div v-if="!narrationOnly" class="progress-phase">
      <details class="analysis-progress">
        <summary><span>Interpretação pela IA <small>Clique para conferir as etapas</small></span><strong>{{ analysis }}%</strong></summary>
        <div class="analysis-log"><p>Etapas do processamento e resultados da interpretação.</p><ol v-if="job.analysis_events?.length"><li v-for="(event, index) in job.analysis_events" :key="index">{{ event }}</li></ol><p v-else>{{ job.status === 'queued' ? 'Aguardando na fila.' : 'Preparando a análise.' }}</p><p v-if="job.scene">{{ job.scene.method === 'conservative' ? 'Leitura com pistas explícitas do texto.' : 'Interpretação concluída.' }} Confira personagens, vozes e intenções em “Como a cena foi interpretada”.</p><p v-if="job.status === 'error' || job.status === 'cancelled'">{{ job.status === 'error' ? 'Processamento interrompido por um erro.' : 'Processamento cancelado.' }}</p></div>
      </details>
      <div class="process-track" role="progressbar" aria-label="Interpretação pela IA" :aria-valuenow="analysis" aria-valuemin="0" aria-valuemax="100"><span :style="{ width: `${analysis}%` }"></span></div>
    </div>
    <div class="progress-phase">
      <div class="audio-progress-label"><span>Geração do áudio <small>{{ audioLabel }}</small></span><strong>{{ audio }}%</strong></div>
      <div class="process-track" role="progressbar" aria-label="Geração do áudio" :aria-valuenow="audio" aria-valuemin="0" aria-valuemax="100"><span :style="{ width: `${audio}%` }"></span></div>
    </div>
  </section>
</template>

<style scoped>
.process-progress { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px 32px; border-top: 1px solid #35412f; padding-top: 22px; margin-top: 24px; }
.process-progress > p { grid-column: 1/-1; margin: 0; }
.progress-phase:only-child, .process-progress > p + .progress-phase { grid-column: 1/-1; }
.analysis-progress summary, .audio-progress-label { min-height: 40px; display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin: 0; color: #dbe1d1; font-size: 12px; }
.analysis-progress summary { cursor: pointer; list-style: none; }
.analysis-progress summary::-webkit-details-marker { display: none; }
.progress-phase small { display: block; color: #95a38c; font-size: 10px; font-weight: 400; line-height: 1.5; margin-top: 5px; }
.progress-phase strong { color: #d0bc91; font-size: 12px; font-variant-numeric: tabular-nums; }
.process-track { height: 5px; border-radius: 4px; margin-top: 12px; background: #2a3527; overflow: hidden; }
.process-track > span { display: block; height: 100%; border-radius: inherit; background: #c9b68c; transition: width .4s; }
.analysis-log { font-size: 11px; line-height: 1.7; color: #a6b29c; padding-top: 12px; }
@media (max-width: 767px) { .process-progress { grid-template-columns: minmax(0, 1fr); gap: 22px; } }
</style>
