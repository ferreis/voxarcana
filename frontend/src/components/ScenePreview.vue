<script setup lang="ts">
import { computed } from 'vue'
import type { Scene, Voice } from '../services/studio'

const props = defineProps<{ scene: Scene; narratorName?: string; voices: Voice[] }>()
const characterCount = computed(() => new Set(props.scene.segments.filter(segment => segment.kind === 'dialogue').map(segment => segment.speaker)).size)
const deliveryNames: Record<string, string> = { neutral: 'Natural', warm: 'Afetuoso', playful: 'Bem-humorado', firm: 'Firme', urgent: 'Urgente', soft: 'Baixo e íntimo', sad: 'Vulnerável', tense: 'Tenso', angry: 'Irritado', fear: 'Ansioso' }
function voiceName(voiceId?: string) {
  return props.voices.find(voice => voice.id === voiceId)?.name || 'Voz a definir'
}
</script>

<template>
  <details class="scene-preview">
    <summary><span>Como a cena foi interpretada</span><span class="scene-count">{{ scene.segments.length }} trechos · {{ characterCount }} {{ characterCount === 1 ? 'personagem' : 'personagens' }}</span></summary>
    <ol aria-label="Trechos da cena interpretada">
      <li v-for="(segment, segmentIndex) in scene.segments" :key="segment.id" :class="{ 'dialogue-segment': segment.kind === 'dialogue' }">
        <span class="segment-number" aria-hidden="true">{{ String(segmentIndex + 1).padStart(2, '0') }}</span>
        <div class="segment-content">
          <div class="segment-heading"><strong>{{ segment.speaker }}</strong><span class="segment-voice">{{ segment.kind === 'narration' ? narratorName || 'Narrador' : voiceName(segment.voice_id) }}</span><span class="segment-delivery">{{ deliveryNames[segment.delivery] || 'Natural' }}</span><span v-if="segment.channel && segment.channel !== 'none'" class="segment-delivery">{{ segment.channel === 'radio' ? 'Rádio' : 'Televisão' }}</span></div>
          <p>{{ segment.text }}</p>
        </div>
      </li>
    </ol>
  </details>
</template>

<style scoped>
.scene-preview { margin-top: 24px; }
summary { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px 18px; cursor: pointer; padding-block: 12px; color: var(--color-primary-soft); font-size: 13px; }
summary > span:first-child::before { content: '▸'; display: inline-block; width: 18px; color: var(--color-primary-soft); }
.scene-preview[open] summary > span:first-child::before { content: '▾'; }
.scene-count { color: var(--color-muted); font-size: 11px; padding-left: 18px; }
ol { list-style: none; margin: 10px 0 0; padding: 0 12px 0 0; max-height: 430px; overflow-y: auto; scrollbar-color: var(--color-border-strong) var(--color-surface); scrollbar-width: thin; }
li { display: flex; gap: 18px; padding: 19px 16px; border-bottom: 1px solid var(--color-border); }
li:last-child { border-bottom: 0; }
.dialogue-segment { background: var(--color-primary-tint); }
.segment-number { font-size: 10px; font-variant-numeric: tabular-nums; color: var(--color-muted); padding-top: 3px; flex-shrink: 0; }
.segment-content { min-width: 0; }
.segment-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; }
.segment-heading strong { font-size: 12px; font-weight: 600; color: var(--color-paper); }
.segment-voice { font-size: 11px; color: var(--color-muted); }
.segment-delivery { font-size: 10px; color: var(--color-primary-soft); border: 1px solid var(--color-primary-tint); padding: 2px 7px; border-radius: 4px; }
p { font: 16px/1.8 var(--font-display); color: var(--color-paper); margin: 10px 0 0; max-width: 100ch; overflow-wrap: anywhere; white-space: pre-line; }
@media (max-width: 767px) { li { gap: 10px; padding: 16px 8px; } p { font-size: 15px; } }
</style>
