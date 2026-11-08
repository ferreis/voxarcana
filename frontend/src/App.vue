<script setup lang="ts">
import { computed, ref } from 'vue'
import { AudioLines, BookOpen, CircleHelp, FileText, Headphones, LoaderCircle, Mic2, ShieldCheck, Sparkles, Square, WandSparkles, SlidersHorizontal, UsersRound } from 'lucide-vue-next'
import CharacterLibraryDialog from './components/CharacterLibraryDialog.vue'
import CastReview from './components/CastReview.vue'
import { useExclusiveAudio } from './composables/useExclusiveAudio'
import GenerationProgress from './components/GenerationProgress.vue'
import AudioPlayer from './components/AudioPlayer.vue'
import VoiceLibraryDialog from './components/VoiceLibraryDialog.vue'
import ReferenceDialog from './components/ReferenceDialog.vue'
import { useStudio } from './composables/useStudio'
useExclusiveAudio()
const studio = useStudio()
const { text, title, voice, style, speed, voices, engine, connected, busy, job, error,
  notice, audioUrl, audioTitle, elapsed, words, selectedVoice, status } = studio
const referenceDialog = ref<InstanceType<typeof ReferenceDialog> | null>(null)
const characterDialog = ref<InstanceType<typeof CharacterLibraryDialog> | null>(null)
const libraryDialog = ref<InstanceType<typeof VoiceLibraryDialog> | null>(null)
const narratorVoices = computed(() => voices.value.filter(item => item.role !== 'character'))
const voiceName = (id?: string) => voices.value.find(v => v.id === id)?.name || 'Voz a definir'
const showHelp = ref(false)
const cast = computed(() => [...new Set(job.value?.scene?.segments.filter(segment => segment.kind === 'dialogue').map(segment => segment.speaker) || [])])
const deliveryNames: Record<string, string> = { neutral: 'Natural', warm: 'Afetuoso', playful: 'Bem-humorado', firm: 'Firme', urgent: 'Urgente', soft: 'Baixo e íntimo', sad: 'Vulnerável', tense: 'Tenso', angry: 'Irritado', fear: 'Ansioso' }
const elapsedLabel = computed(() => `${Math.floor(elapsed.value / 60)}:${String(elapsed.value % 60).padStart(2, '0')}`)
const progress = computed(() => job.value?.total ? Math.round(job.value.completed / job.value.total * 100) : 0)
function example() {
  text.value = 'A chuva desenhava caminhos pelo vidro da velha biblioteca. Do outro lado da sala, uma única vela ainda resistia à escuridão.\n\nVocê encontra um envelope sobre a mesa. Na frente, escrito com uma caligrafia que conhece bem, está o seu nome.\n\nAo longe, o relógio da torre anuncia meia-noite. A carta começa com apenas três palavras: não confie nele.'
  title.value = 'A carta da meia-noite'
}
</script>

<template>
  <div class="app-shell">
    <aside class="rail" aria-label="VoxArcana"><a class="brand-glyph" href="#studio" aria-label="VoxArcana, estúdio">V<span>✦</span></a><a class="rail-button active" href="#studio" aria-label="Estúdio de narração"><AudioLines :size="22" /></a><button class="rail-button" aria-label="Adicionar voz de referência" :disabled="!engine?.reference_audio" @click="referenceDialog?.open()"><Mic2 :size="21" /></button><button class="rail-button rail-help" aria-label="Como funciona" @click="showHelp = !showHelp"><CircleHelp :size="21" /></button></aside>
    <div class="workspace">
      <header class="topbar"><a href="#studio" class="wordmark">Vox<span>Arcana</span><span class="studio-tag">ESTÚDIO</span></a><div class="header-actions"><button class="icon-button mobile-add-voice" aria-label="Adicionar voz de referência" :disabled="!engine?.reference_audio" @click="referenceDialog?.open()"><Mic2 :size="20" /></button><span class="locale-badge"><span aria-hidden="true">🇧🇷</span> Português do Brasil</span></div></header>
      <main id="studio">
        <section v-if="showHelp" class="help-strip"><BookOpen :size="22" /><div><strong>Da sua imaginação para a mesa.</strong><p>Cole a cena e clique em Analisar texto e escolher vozes. Confira os personagens, corrija nomes e gênero e escolha uma voz para cada um antes de gerar. Depois, ouça ou baixe o WAV. Para outro timbre de narrador, adicione uma gravação brasileira de referência. Você não precisa cadastrar os personagens nem descrever suas emoções. Tudo é gerado neste computador, sem assinatura.</p></div><button class="text-button" @click="showHelp = false">Entendi</button></section>
        <div v-if="error" class="error-message error-banner" role="alert"><span>{{ error }}</span><button v-if="!connected || notice" class="text-button" @click="studio.reconnect">Reconectar</button></div>
        <p v-if="notice" class="muted small" role="status">{{ notice }}</p>
        <div class="studio-layout">
          <section class="editor-section" aria-label="Texto da narração">
            <div class="section-heading editor-actions"><button class="text-button" :disabled="busy" @click="example"><Sparkles :size="14" /> Carregar exemplo</button></div>
            <div class="editor-surface">
              <div class="editor-toolbar"><FileText :size="16" aria-hidden="true" /><label class="sr-only" for="narration-title">Título da narração</label><input id="narration-title" v-model="title" class="title-input" maxlength="80" :disabled="busy"><span class="draft-indicator">Rascunho local</span></div>
              <label class="sr-only" for="narration-text">Texto para narrar</label><textarea id="narration-text" v-model="text" maxlength="10000" placeholder="Toda aventura começa com algumas palavras…&#10;&#10;Cole ou escreva a cena que você quer narrar. Um encontro na taverna, uma carta misteriosa, o monólogo de um personagem. A história é sua." spellcheck="true" lang="pt-BR"></textarea>
              <div class="editor-footer"><span>{{ words.toLocaleString('pt-BR') }} palavras</span><span>{{ text.length.toLocaleString('pt-BR') }} <span class="muted">/ 10.000 caracteres</span></span></div>
            </div>
            <div class="editor-note"><ShieldCheck :size="14" /><p>Seu texto fica neste computador. Sem créditos, sem mensalidade.</p></div>
          </section>
          <aside class="voice-panel" aria-label="Configurar narração">
            <div class="voice-identity"><span class="voice-orb" aria-hidden="true"><AudioLines :size="30" /></span><span class="voice-overline">FEITO PARA PT-BR</span></div>
            <div class="narrator-field"><label for="voice">Voz do narrador</label><div class="voice-controls"><select id="voice" v-model="voice" :disabled="busy || !voices.length"><option v-if="!narratorVoices.length" value="">{{ connected ? 'Adicione uma voz de narrador' : 'Carregando vozes…' }}</option><option v-for="item in narratorVoices" :key="item.id" :value="item.id">{{ item.name }}</option></select><button class="secondary-button compact-button" title="Classificar minhas vozes" aria-label="Classificar minhas vozes" :disabled="busy || !engine?.reference_audio" @click="libraryDialog?.open()"><SlidersHorizontal :size="17" /></button><button class="secondary-button compact-button" title="Elenco salvo · personagens e vozes" aria-label="Elenco salvo · personagens e vozes" :disabled="busy || !connected" @click="characterDialog?.open()"><UsersRound :size="17" /></button></div></div>
            <div class="voice-setting"><label for="generation-speed">Velocidade do áudio gerado</label><select id="generation-speed" title="Aplicada ao WAV baixado" v-model.number="speed" :disabled="busy"><option :value="0.5">0,5×</option><option :value="0.75">0,75×</option><option :value="1">1×</option><option :value="1.1">1,1×</option><option :value="1.25">1,25×</option><option :value="1.5">1,5×</option><option :value="1.75">1,75×</option><option :value="2">2×</option></select></div>
            <div class="voice-setting"><label for="acting">Atuação pelo contexto</label><select id="acting" v-model="style" :disabled="busy"><option value="neutral">Automática · equilibrada</option><option value="storyteller">Automática · mais expressiva</option><option value="calm">Automática · contida</option></select></div>
            <div v-if="cast.length" class="cast-list" aria-label="Personagens identificados"><span v-for="name in cast" :key="name">{{ name }}</span></div>
          </aside>
        </div>
        <div class="generation-bar"><div class="generation-status" role="status" aria-live="polite"><span class="status-icon"><LoaderCircle v-if="busy" :size="20" class="spin" /><Headphones v-else :size="20" /></span><div><strong>{{ status }}</strong><span v-if="busy">{{ elapsedLabel }} decorridos <template v-if="job?.total">· {{ progress }}% dos trechos concluídos</template></span><span v-else>A narração pode levar alguns minutos. Você pode continuar com esta aba aberta.</span></div></div><div class="generation-actions"><button v-if="busy" class="secondary-button" :disabled="job?.status === 'cancelling' || !job" @click="studio.cancel"><Square :size="14" /> Cancelar</button><button class="primary-button" :disabled="busy || !connected || engine?.id !== 'chatterbox-br' || !engine?.installed || !voice || !text.trim()" @click="studio.generate"><LoaderCircle v-if="busy" :size="18" class="spin" /><WandSparkles v-else :size="18" />{{ busy ? 'Processando a cena' : job?.status === 'review' ? 'Analisar novamente' : 'Analisar texto e escolher vozes' }}<span v-if="!busy" aria-hidden="true">↗</span></button></div></div>
        <CastReview v-if="job?.status === 'review' && job.scene" :key="job.id" :scene="job.scene" :voices="voices" :narrator="voice" :disabled="busy" :stale="job.source_text !== text.trim()" @generate="studio.perform" />
        <p v-if="job?.scene?.warning" class="analysis-notice" role="status">{{ job.scene.warning }}</p>
        <details v-if="job?.scene?.segments.length" class="scene-preview"><summary>Como a cena foi interpretada <span>{{ cast.length }} personagens</span></summary><ol><li v-for="segment in job.scene.segments" :key="segment.id"><div><strong>{{ segment.speaker }}</strong><span>{{ deliveryNames[segment.delivery] || 'Natural' }} · {{ segment.kind === 'narration' ? selectedVoice?.name : voiceName(segment.voice_id) }}</span></div><p>{{ segment.text }}</p></li></ol></details>
        <GenerationProgress v-if="job" :job="job" />
      </main>
      <AudioPlayer :src="audioUrl" :title="audioTitle" />
      <footer class="page-footer"><span>VoxArcana <span class="footer-star">✦</span> Histórias ganham vida quando encontram uma voz.</span><button class="text-button" @click="showHelp = !showHelp">Como funciona <CircleHelp :size="13" /></button></footer>
    </div>
    <CharacterLibraryDialog ref="characterDialog" :voices="voices" />
    <VoiceLibraryDialog ref="libraryDialog" :voices="voices" :save="studio.updateVoice" :remove="studio.deleteVoice" />
    <ReferenceDialog ref="referenceDialog" :save="studio.addReference" />
  </div>
</template>
