<script setup lang="ts">
import { computed, ref } from 'vue'
import { AudioLines, BookOpen, ChevronRight, CircleHelp, FileText, Headphones, LoaderCircle, Mic2, Plus, RefreshCw, ShieldCheck, Sparkles, Square, WandSparkles, Volume2 } from 'lucide-vue-next'
import AudioPlayer from './components/AudioPlayer.vue'
import ReferenceDialog from './components/ReferenceDialog.vue'
import { useStudio } from './composables/useStudio'
const studio = useStudio()
const { text, title, voice, style, voices, styles, engine, connected, checking, busy, job, error,
  notice, audioUrl, audioTitle, elapsed, words, selectedVoice, status } = studio
const referenceDialog = ref<InstanceType<typeof ReferenceDialog> | null>(null)
const showHelp = ref(false)
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
      <header class="topbar"><a href="#studio" class="wordmark">Vox<span>Arcana</span><span class="studio-tag">ESTÚDIO</span></a><div class="connection"><span class="connection-dot" :class="{ online: connected }"></span><span>{{ connected ? 'No seu computador' : 'Desconectado' }}</span><button class="icon-button" aria-label="Reconectar ao servidor" :disabled="checking" @click="studio.reconnect"><RefreshCw :size="15" :class="{ spin: checking }" /></button></div></header>
      <main id="studio">
        <div class="page-heading"><div><p class="eyebrow"><span class="gold-line"></span> VOZES PARA MUNDOS QUE AINDA NÃO EXISTEM</p><h1>Estúdio de narração<span>.</span></h1><p class="subtitle">Dê voz à cena. Deixe a sua mesa ouvir a história.</p></div><span class="locale-badge"><span aria-hidden="true">🇧🇷</span> Português do Brasil</span></div>
        <section v-if="showHelp" class="help-strip"><BookOpen :size="22" /><div><strong>Da sua imaginação para a mesa.</strong><p>Cole a cena, escolha uma voz brasileira e clique em Gerar narração. Depois, ouça ou baixe o WAV. Para outro timbre, adicione uma gravação brasileira de referência. Tudo é gerado neste computador, sem assinatura.</p></div><button class="text-button" @click="showHelp = false">Entendi</button></section>
        <div v-if="error" class="error-message error-banner" role="alert"><span>{{ error }}</span><button v-if="!connected || notice" class="text-button" @click="studio.reconnect">Reconectar</button></div>
        <p v-if="notice" class="muted small" role="status">{{ notice }}</p>
        <div class="studio-layout">
          <section class="editor-section" aria-label="Texto da narração">
            <div class="section-heading"><div class="section-title"><span class="section-number">01</span><h2>A história</h2></div><button class="text-button" :disabled="busy" @click="example"><Sparkles :size="14" /> Carregar exemplo</button></div>
            <div class="editor-surface">
              <div class="editor-toolbar"><FileText :size="16" aria-hidden="true" /><label class="sr-only" for="narration-title">Título da narração</label><input id="narration-title" v-model="title" class="title-input" maxlength="80" :disabled="busy"><span class="draft-indicator">Rascunho local</span></div>
              <label class="sr-only" for="narration-text">Texto para narrar</label><textarea id="narration-text" v-model="text" maxlength="10000" placeholder="Toda aventura começa com algumas palavras…&#10;&#10;Cole ou escreva a cena que você quer narrar. Um encontro na taverna, uma carta misteriosa, o monólogo de um personagem. A história é sua." spellcheck="true" lang="pt-BR"></textarea>
              <div class="editor-footer"><span>{{ words.toLocaleString('pt-BR') }} palavras</span><span>{{ text.length.toLocaleString('pt-BR') }} <span class="muted">/ 10.000 caracteres</span></span></div>
            </div>
            <div class="editor-note"><ShieldCheck :size="14" /><p>Seu texto fica neste computador. Sem créditos, sem mensalidade.</p></div>
          </section>
          <aside class="voice-panel" aria-label="Configurar narração">
            <div class="section-heading"><div class="section-title"><span class="section-number">02</span><h2>A voz</h2></div><Volume2 :size="18" class="muted" /></div>
            <div class="voice-identity"><span class="voice-orb" aria-hidden="true"><AudioLines :size="30" /></span><span class="voice-overline">FEITO PARA PT-BR</span><h3>Uma voz brasileira.</h3><p>O sotaque da sua história.</p><div class="wave-decoration" aria-hidden="true"><i v-for="(height, index) in [9,16,12,24,35,19,44,30,48,22,36,52,30,42,17,32,24,13,20,9]" :key="index" :style="{ height: `${height}px` }"></i></div></div>
            <label for="voice">Voz de referência</label><select id="voice" v-model="voice" :disabled="busy || !voices.length"><option v-if="!voices.length" value="">Carregando vozes…</option><option v-for="item in voices" :key="item.id" :value="item.id">{{ item.name }}</option></select><p class="field-help">{{ selectedVoice?.description || 'Escolha uma voz para a sua cena.' }}</p>
            <button class="add-voice" :disabled="busy || !engine?.reference_audio" @click="referenceDialog?.open()"><Plus :size="15" /> Adicionar minha voz <ChevronRight :size="15" /></button>
            <div class="style-field"><label for="style">Interpretação</label><select id="style" v-model="style" :disabled="busy || !styles.length"><option v-for="item in styles" :key="item.id" :value="item.id">{{ item.name }}</option></select><p class="field-help">Ajusta a expressividade. O timbre vem da voz de referência.</p></div>
            <div class="model-note"><span class="model-dot"></span><span>{{ engine?.id === 'chatterbox-br' ? 'Chatterbox · modelo brasileiro' : 'Aguardando motor brasileiro' }}<small>Geração local · sem serviço pago</small></span></div>
          </aside>
        </div>
        <div class="generation-bar"><div class="generation-status" role="status" aria-live="polite"><span class="status-icon"><LoaderCircle v-if="busy" :size="20" class="spin" /><Headphones v-else :size="20" /></span><div><strong>{{ status }}</strong><span v-if="busy">{{ elapsedLabel }} decorridos <template v-if="job?.total">· {{ progress }}% dos trechos concluídos</template></span><span v-else>A narração pode levar alguns minutos. Você pode continuar com esta aba aberta.</span></div></div><div class="generation-actions"><button v-if="busy" class="secondary-button" :disabled="job?.status === 'cancelling' || !job" @click="studio.cancel"><Square :size="14" /> Cancelar</button><button class="primary-button" :disabled="busy || !connected || engine?.id !== 'chatterbox-br' || !engine?.installed || !text.trim()" @click="studio.generate"><LoaderCircle v-if="busy" :size="18" class="spin" /><WandSparkles v-else :size="18" />{{ busy ? 'Criando sua narração' : 'Gerar narração' }}<span v-if="!busy" aria-hidden="true">↗</span></button></div></div>
        <div v-if="busy" class="generation-progress" role="progressbar" aria-label="Trechos concluídos" :aria-valuenow="job?.total ? progress : undefined" aria-valuemin="0" aria-valuemax="100"><span :class="{ indeterminate: !job?.total }" :style="{ width: job?.total ? `${progress}%` : '25%' }"></span></div>
      </main>
      <AudioPlayer :src="audioUrl" :title="audioTitle" />
      <footer class="page-footer"><span>VoxArcana <span class="footer-star">✦</span> Histórias ganham vida quando encontram uma voz.</span><button class="text-button" @click="showHelp = !showHelp">Como funciona <CircleHelp :size="13" /></button></footer>
    </div>
    <ReferenceDialog ref="referenceDialog" :save="studio.addReference" />
  </div>
</template>
