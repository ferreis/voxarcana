<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { AudioLines, BookOpen, CircleHelp, FileText, Mic2, Sparkles, SlidersHorizontal, UsersRound } from 'lucide-vue-next'
import ProjectSelector from './components/ProjectSelector.vue'
import AudioSettings from './components/AudioSettings.vue'
import CharacterLibraryDialog from './components/CharacterLibraryDialog.vue'
import CastReview from './components/CastReview.vue'
import GenerationControls from './components/GenerationControls.vue'
import type { ReviewedLine } from './services/studio'
import { useExclusiveAudio } from './composables/useExclusiveAudio'
import GenerationProgress from './components/GenerationProgress.vue'
import ScenePreview from './components/ScenePreview.vue'
import AudioPlayer from './components/AudioPlayer.vue'
import VoiceLibraryDialog from './components/VoiceLibraryDialog.vue'
import ReferenceDialog from './components/ReferenceDialog.vue'
import { useStudio } from './composables/useStudio'
useExclusiveAudio()
const studio = useStudio()
const { projectId, projects, text, title, voice, style, speed, voices, engine, connected, busy, canPerform, job, narrationOnly, error,
  notice, audioUrl, audioTitle, elapsed, words, selectedVoice, status } = studio
const referenceDialog = ref<InstanceType<typeof ReferenceDialog> | null>(null)
const characterDialog = ref<InstanceType<typeof CharacterLibraryDialog> | null>(null)
const libraryDialog = ref<InstanceType<typeof VoiceLibraryDialog> | null>(null)
const narratorVoices = computed(() => voices.value.filter(item => item.role !== 'character'))
const showHelp = ref(false)
const cast = computed(() => [...new Set(job.value?.scene?.segments.filter(segment => segment.kind === 'dialogue').map(segment => segment.speaker) || [])])
const elapsedLabel = computed(() => `${Math.floor(elapsed.value / 60)}:${String(elapsed.value % 60).padStart(2, '0')}`)
const reviewedLines = ref<ReviewedLine[] | null>(null)
const audioStarted = computed(() => !!job.value && (narrationOnly.value || !!job.value.scene) && job.value.status !== 'review')
const canStart = computed(() => !busy.value && connected.value && engine.value?.id === 'chatterbox-br'
  && engine.value.installed && !!voice.value && !!text.value.trim())
const canGenerate = computed(() => canPerform.value && reviewedLines.value !== null)
watch(() => job.value?.id, () => { reviewedLines.value = null }, { flush: 'sync' })
function generateAudio() {
  if (canGenerate.value && reviewedLines.value !== null) void studio.perform(reviewedLines.value)
}
function example() {
  text.value = 'A chuva desenhava caminhos pelo vidro da velha biblioteca. Do outro lado da sala, uma única vela ainda resistia à escuridão.\n\nVocê encontra um envelope sobre a mesa. Na frente, escrito com uma caligrafia que conhece bem, está o seu nome.\n\nAo longe, o relógio da torre anuncia meia-noite. A carta começa com apenas três palavras: não confie nele.'
  title.value = 'A carta da meia-noite'
}
</script>

<template>
  <div class="app-shell">
    <aside class="rail" aria-label="VoxArcana"><a class="brand-glyph" href="#studio" aria-label="VoxArcana, estúdio">V<span>✦</span></a><a class="rail-button active" href="#studio" aria-label="Estúdio de narração"><AudioLines :size="22" /></a><button class="rail-button" aria-label="Adicionar voz de referência" :disabled="!engine?.reference_audio" @click="referenceDialog?.open()"><Mic2 :size="21" /></button><button class="rail-button rail-help" aria-label="Como funciona" @click="showHelp = !showHelp"><CircleHelp :size="21" /></button></aside>
    <div class="workspace">
      <header class="topbar">
        <AudioPlayer :src="audioUrl" :title="audioTitle">
          <template #actions><button class="icon-button mobile-add-voice" aria-label="Adicionar voz de referência" :disabled="!engine?.reference_audio" @click="referenceDialog?.open()"><Mic2 :size="20" /></button></template>
        </AudioPlayer>
      </header>
      <main id="studio">
        <section v-if="showHelp" class="help-strip"><BookOpen :size="22" /><div><strong>Da sua imaginação para a mesa.</strong><p>Para usar apenas a voz do narrador, clique em Gerar só com narrador. Para separar as falas dos personagens, clique em Analisar texto e escolher vozes. Confira os personagens, corrija nomes e gênero e escolha uma voz para cada um antes de gerar. Depois, ouça ou baixe o WAV. Para outro timbre de narrador, adicione uma gravação brasileira de referência. Você não precisa cadastrar os personagens nem descrever suas emoções. Tudo é gerado neste computador, sem assinatura.</p></div><button class="text-button" @click="showHelp = false">Entendi</button></section>
        <div v-if="error" class="error-message error-banner" role="alert"><span>{{ error }}</span><button v-if="!connected || notice" class="text-button" @click="studio.reconnect">Reconectar</button></div>
        <p v-if="notice" class="muted small" role="status">{{ notice }}</p>
        <ProjectSelector :projects="projects" :project-id="projectId" :disabled="busy" :create="studio.createProject" @select="studio.selectProject" />
        <div class="studio-layout">
          <section class="editor-section" aria-label="Texto da narração">
            <div class="section-heading editor-actions"><button class="text-button" :disabled="busy" @click="example"><Sparkles :size="14" /> Carregar exemplo</button></div>
            <div class="editor-surface">
              <div class="editor-toolbar"><FileText :size="16" aria-hidden="true" /><label class="sr-only" for="narration-title">Título da narração</label><input id="narration-title" v-model="title" class="title-input" maxlength="80" :disabled="busy"><span class="draft-indicator">Rascunho local</span></div>
              <label class="sr-only" for="narration-text">Texto para narrar</label><textarea id="narration-text" v-model="text" maxlength="10000" placeholder="Toda aventura começa com algumas palavras…&#10;&#10;Cole ou escreva a cena que você quer narrar. Um encontro na taverna, uma carta misteriosa, o monólogo de um personagem. A história é sua." spellcheck="true" lang="pt-BR"></textarea>
              <div class="editor-footer"><span>{{ words.toLocaleString('pt-BR') }} palavras</span><span>{{ text.length.toLocaleString('pt-BR') }} <span class="muted">/ 10.000 caracteres</span></span></div>
            </div>
          </section>
          <aside class="voice-panel" aria-label="Configurar narração">
            <div class="voice-identity"><span class="voice-orb" aria-hidden="true"><AudioLines :size="30" /></span><span class="voice-overline">FEITO PARA PT-BR</span></div>
            <div class="narrator-field"><label for="voice">Voz do narrador</label><div class="voice-controls"><select id="voice" v-model="voice" :disabled="busy || !voices.length"><option v-if="!narratorVoices.length" value="">{{ connected ? 'Adicione uma voz de narrador' : 'Carregando vozes…' }}</option><option v-for="item in narratorVoices" :key="item.id" :value="item.id">{{ item.name }}</option></select><button class="secondary-button compact-button" title="Classificar minhas vozes" aria-label="Classificar minhas vozes" :disabled="busy || !engine?.reference_audio" @click="libraryDialog?.open()"><SlidersHorizontal :size="17" /></button><button class="secondary-button compact-button" title="Elenco salvo · personagens e vozes" aria-label="Elenco salvo · personagens e vozes" :disabled="busy || !connected" @click="characterDialog?.open()"><UsersRound :size="17" /></button></div></div>
            <AudioSettings v-if="narrationOnly || !job?.scene" v-model:speed="speed" v-model:style="style" :disabled="busy" />
            <div v-if="cast.length" class="cast-list" aria-label="Personagens identificados"><span v-for="name in cast" :key="name">{{ name }}</span></div>
          </aside>
        </div>
        <GenerationControls :can-start="canStart" :can-generate="canGenerate" :busy="busy" :narration-only="narrationOnly" :audio-started="audioStarted" :has-scene="!!job?.scene" :reviewing="job?.status === 'review'" :done="job?.status === 'done'" :cancelling="job?.status === 'cancelling'" :can-cancel="!!job" :status="status" :elapsed-label="elapsedLabel" @narrate="studio.narrate" @analyze="studio.analyze" @generate="generateAudio" @cancel="studio.cancel" />
        <details v-if="!narrationOnly && job?.scene && job.source_text != null" :key="`${projectId}-${job.id}`" class="analysis-settings" open>
          <summary>Configurar personagens e áudio</summary>
          <CastReview :key="job.id" :project-id="projectId" :scene="job.scene" :voices="voices" :narrator="voice" :disabled="busy" :stale="job.source_text !== text.trim()" @change="reviewedLines = $event" />
          <AudioSettings v-model:speed="speed" v-model:style="style" :disabled="busy" />
        </details>
        <p v-if="job?.scene?.warning" class="analysis-notice" role="status">{{ job.scene.warning }}</p>
        <ScenePreview v-if="job?.scene?.segments.length" :scene="job.scene" :narrator-name="selectedVoice?.name" :voices="voices" />
        <GenerationProgress v-if="job" :job="job" :narration-only="narrationOnly" />
      </main>
      <footer class="page-footer"><span>VoxArcana <span class="footer-star">✦</span> Histórias ganham vida quando encontram uma voz.</span><button class="text-button" @click="showHelp = !showHelp">Como funciona <CircleHelp :size="13" /></button></footer>
    </div>
    <CharacterLibraryDialog :key="projectId" :project-id="projectId" ref="characterDialog" :voices="voices" />
    <VoiceLibraryDialog ref="libraryDialog" :voices="voices" :save="studio.updateVoice" :remove="studio.deleteVoice" />
    <ReferenceDialog ref="referenceDialog" :save="studio.addReference" />
  </div>
</template>

<style scoped>
.analysis-settings { margin: 24px 0; padding: 20px 0; border-block: 1px solid var(--color-border); }
.analysis-settings > summary { cursor: pointer; font-weight: 600; padding: 8px 0; }
.analysis-settings > summary:focus-visible { outline: 2px solid currentColor; outline-offset: 4px; }
.analysis-settings :deep(.cast-review) { border-top: 0; padding-top: 0; }
</style>
