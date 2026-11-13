<script setup lang="ts">
import { ref, watch, computed } from "vue";
import {
  Play,
  Pause,
  Square,
  Download,
  AudioLines,
  Volume2,
  VolumeX,
} from "lucide-vue-next";
const props = defineProps<{ src: string; title: string }>();
const audio = ref<HTMLAudioElement | null>(null);
const playing = ref(false);
const current = ref(0);
const duration = ref(0);
const rate = ref(1);
const volume = ref(1);
const previousVolume = ref(1);
const volumePercent = computed(() => Math.round(volume.value * 100));
const error = ref("");
const filename = computed(
  () =>
    `${props.title.replace(/[^\p{L}\p{N}\s_-]/gu, "").trim() || "voxarcana"}.wav`,
);
const time = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
watch(
  () => props.src,
  () => {
    playing.value = false;
    current.value = 0;
    duration.value = 0;
    error.value = "";
  },
);
watch(rate, (value) => {
  if (audio.value) audio.value.playbackRate = value;
});
watch(volume, (nextVolume) => {
  if (audio.value) audio.value.volume = nextVolume;
});
function applyAudioSettings() {
  if (!audio.value) return;
  duration.value = Number.isFinite(audio.value.duration)
    ? audio.value.duration
    : 0;
  audio.value.volume = volume.value;
  audio.value.playbackRate = rate.value;
}
function toggleMute() {
  if (volume.value > 0) {
    previousVolume.value = volume.value;
    volume.value = 0;
  } else volume.value = previousVolume.value;
}
async function toggle() {
  if (!audio.value || !props.src) return;
  try {
    if (playing.value) audio.value.pause();
    else {
      audio.value.playbackRate = rate.value;
      audio.value.volume = volume.value;
      await audio.value.play();
    }
  } catch {
    error.value =
      "Não consegui reproduzir. Baixe o WAV para ouvir no seu player.";
  }
}
function stop() {
  if (audio.value) {
    audio.value.pause();
    audio.value.currentTime = 0;
  }
}
function seek(event: Event) {
  if (audio.value)
    audio.value.currentTime = Number((event.target as HTMLInputElement).value);
}
</script>

<template>
  <section class="player" aria-label="Reprodução da narração">
    <audio
      v-if="src"
      ref="audio"
      :src="src"
      preload="metadata"
      @play="playing = true"
      @pause="playing = false"
      @ended="playing = false"
      @timeupdate="current = audio?.currentTime || 0"
      @loadedmetadata="applyAudioSettings"
      @error="error = 'O áudio não pôde ser aberto. Tente gerar novamente.'"
    />
    <div class="player-track">
      <span class="track-icon"
        ><AudioLines :size="22" aria-hidden="true"
      /></span>
      <div>
        <strong>{{ src ? title : "Sua próxima narração" }}</strong
        >
      </div>
    </div>
    <div class="player-center">
      <div class="playback-actions">
        <button
          class="icon-button"
          :disabled="!src"
          aria-label="Parar reprodução"
          @click="stop"
        >
          <Square :size="15" /></button
        ><button
          class="play-button"
          :disabled="!src"
          :aria-label="playing ? 'Pausar narração' : 'Reproduzir narração'"
          @click="toggle"
        >
          <Pause v-if="playing" :size="20" fill="currentColor" /><Play
            v-else
            :size="20"
            fill="currentColor"
          /></button
        ><label class="speed-label"
          ><span class="sr-only">Velocidade do player</span
          ><select
            v-model="rate"
            aria-label="Velocidade do player"
            title="Só altera a reprodução"
          >
            <option :value="0.5">0,5×</option>
            <option :value="0.75">0,75×</option>
            <option :value="1">1×</option>
            <option :value="1.25">1,25×</option>
            <option :value="1.5">1,5×</option>
            <option :value="1.75">1,75×</option>
            <option :value="2">2×</option>
          </select></label
        >
      </div>
      <div class="timeline">
        <span>{{ time(current) }}</span
        ><input
          type="range"
          aria-label="Posição da reprodução"
          :max="duration || 1"
          step="0.1"
          :value="current"
          :disabled="!src"
          @input="seek"
        /><span>{{ time(duration) }}</span>
      </div>
    </div>
    <div class="player-utilities">
      <div class="volume-control">
        <button
          class="icon-button"
          :aria-label="volume ? 'Silenciar áudio' : 'Ativar som'"
          :aria-pressed="volume === 0"
          @click="toggleMute"
        >
          <Volume2 v-if="volume" :size="18" /><VolumeX v-else :size="18" />
        </button>
        <input
          v-model.number="volume"
          type="range"
          min="0"
          max="1"
          step="0.01"
          aria-label="Volume da reprodução"
          :aria-valuetext="`${volumePercent}%`"
        />
        <span class="volume-percent" aria-hidden="true"
          >{{ volumePercent }}%</span
        >
      </div>
      <a
        class="download-button"
        aria-label="Baixar WAV"
        title="Baixar WAV"
        :class="{ disabled: !src }"
        :href="src || undefined"
        :download="filename"
        :aria-disabled="!src"
        :tabindex="src ? 0 : -1"
        ><Download :size="17" /> <span>Baixar WAV</span></a
      >
      <slot name="actions" />
    </div>
    <p v-if="error" class="player-error" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.player {
  padding: 12px 28px;
  display: grid;
  grid-template-columns: minmax(130px, 1fr) minmax(220px, 2fr) auto;
  align-items: center;
  gap: 24px;
  min-width: 0;
  background: var(--color-surface);
}
.player-track {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}
.player-track > div {
  min-width: 0;
}
.track-icon {
  width: 38px;
  height: 38px;
  border: 1px solid var(--color-border);
  border-radius: 7px;
  display: grid;
  place-items: center;
  color: var(--color-muted);
  flex-shrink: 0;
  background: var(--color-surface-raised);
}
.player-track strong {
  display: block;
  font-size: 11px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.player-track div > span {
  font-size: 9px;
  color: var(--color-muted);
  display: block;
  margin-top: 5px;
  line-height: 1.5;
}
.player-center {
  min-width: 0;
}
.playback-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
}
.play-button {
  width: 36px;
  height: 36px;
  border: 0;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  display: grid;
  place-items: center;
}
.play-button:disabled {
  background: var(--color-muted);
}
.speed-label {
  margin: 0;
}
.speed-label select {
  min-height: auto;
  padding: 5px;
  border: 0;
  font-size: 10px;
  color: var(--color-muted);
  background: transparent;
}
.timeline {
  display: flex;
  align-items: center;
  gap: 9px;
  color: var(--color-muted);
  font-size: 9px;
  font-variant-numeric: tabular-nums;
  margin-top: 6px;
}
.timeline input {
  width: 100%;
  min-width: 0;
  height: 16px;
  accent-color: var(--color-primary);
  cursor: pointer;
}
.player-utilities {
  display: flex;
  align-items: center;
  gap: 18px;
}
.volume-control {
  display: flex;
  align-items: center;
  gap: 6px;
}
.volume-control input {
  width: 72px;
  min-width: 0;
  height: 24px;
  accent-color: var(--color-primary);
  cursor: pointer;
}
.volume-percent {
  width: 32px;
  color: var(--color-muted);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.download-button {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
  padding: 10px 0;
  white-space: nowrap;
}
.download-button.disabled {
  opacity: 0.4;
  pointer-events: none;
}
.player-error {
  grid-column: 1/-1;
  font-size: 12px;
  color: #eab5a4;
}
@media (min-width: 1600px) {
  .player {
    padding-inline: 42px;
    gap: 32px;
  }
}
@media (min-width: 768px) and (max-width: 1100px) {
  .player {
    padding-inline: 20px;
    grid-template-columns: minmax(100px, 1fr) minmax(190px, 1.5fr) auto;
    gap: 16px;
  }
  .player-utilities {
    flex-direction: column;
    gap: 0;
  }
  .download-button {
    padding: 4px;
  }
  .track-icon {
    display: none;
  }
}
@media (max-width: 767px) {
  .player {
    padding: 10px 16px;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 8px 12px;
  }
  .player-track {
    gap: 8px;
  }
  .track-icon,
  .player-track div > span,
  .volume-percent,
  .download-button > span {
    display: none;
  }
  .player-center {
    grid-column: 1/-1;
    grid-row: 2;
  }
  .player-utilities {
    gap: 6px;
  }
  .volume-control {
    gap: 0;
  }
  .volume-control input {
    width: 55px;
  }
  .download-button {
    width: 32px;
    height: 36px;
    justify-content: center;
    padding: 0;
  }
}
</style>
