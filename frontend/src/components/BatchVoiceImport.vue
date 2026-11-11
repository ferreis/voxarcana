<script setup lang="ts">
import { onBeforeUnmount, ref } from "vue";
import { Upload, Trash2, LoaderCircle } from "lucide-vue-next";
import type { VoiceMetadata } from "../services/studio";

interface Entry {
  id: number;
  file: File;
  url: string;
  metadata: VoiceMetadata;
  error: string;
}
const props = defineProps<{
  save: (name: string, file: File, metadata: VoiceMetadata) => Promise<void>;
}>();
const emit = defineEmits<{ busy: [value: boolean]; done: [] }>();
const entries = ref<Entry[]>([]);
const busy = ref(false);
const message = ref("");
let nextId = 0;
function select(event: Event) {
  const input = event.target as HTMLInputElement;
  for (const file of Array.from(input.files || [])) {
    const name =
      file.name
        .replace(/\.[^.]+$/, "")
        .trim()
        .slice(0, 60) || "Voz";
    entries.value.push({
      id: nextId++,
      file,
      url: URL.createObjectURL(file),
      metadata: { name, role: "both", gender: "unknown", kind: "human" },
      error: "",
    });
  }
  input.value = "";
  message.value = "";
}
function remove(entry: Entry) {
  URL.revokeObjectURL(entry.url);
  entries.value = entries.value.filter((item) => item.id !== entry.id);
}
function pauseOthers(event: Event) {
  const current = event.target as HTMLAudioElement;
  current
    .closest(".batch-list")
    ?.querySelectorAll("audio")
    .forEach((audio) => {
      if (audio !== current) audio.pause();
    });
}
async function submit() {
  if (busy.value || !entries.value.length) return;
  busy.value = true;
  emit("busy", true);
  message.value = "";
  let saved = 0;
  for (const entry of [...entries.value]) {
    entry.error = "";
    const name = entry.metadata.name.trim();
    if (!name) {
      entry.error = "Informe um nome para a voz.";
      continue;
    }
    if (entry.file.size > 50 * 1024 * 1024) {
      entry.error = "O arquivo ultrapassa 50 MB.";
      continue;
    }
    try {
      await props.save(name, entry.file, { ...entry.metadata, name });
      remove(entry);
      saved++;
    } catch (problem) {
      entry.error =
        problem instanceof Error
          ? problem.message
          : "Não consegui importar esta voz.";
    }
  }
  busy.value = false;
  emit("busy", false);
  if (!entries.value.length) {
    emit("done");
    return;
  }
  message.value = `${saved} voz(es) importada(s). Revise os arquivos que ficaram na lista e tente novamente.`;
}
onBeforeUnmount(() =>
  entries.value.forEach((entry) => URL.revokeObjectURL(entry.url)),
);
</script>

<template>
  <div class="batch-import">
    <label class="upload-area batch-upload" for="batch-files"
      ><Upload :size="21" /><span
        ><strong>Selecionar áudios</strong><br />MP3, M4A, MP4, WAV ou FLAC ·
        até 50 MB por arquivo</span
      ><input
        id="batch-files"
        type="file"
        multiple
        accept=".mp3,audio/mpeg,.mp4,.m4a,.wav,.flac,video/mp4,audio/mp4,audio/wav,audio/flac"
        :disabled="busy"
        @change="select"
    /></label>
    <p class="batch-help">
      Ouça e classifique cada voz. O nome começa com o nome do arquivo e pode
      ser alterado.
    </p>
    <div v-if="entries.length" class="batch-list">
      <div class="batch-header" aria-hidden="true">
        <span>Arquivo e nome</span><span>Ouvir</span><span>Uso</span
        ><span>Gênero</span><span>Tipo de voz</span><span></span>
      </div>
      <div v-for="entry in entries" :key="entry.id" class="batch-row">
        <div class="batch-name">
          <span class="filename" :title="entry.file.name">{{
            entry.file.name
          }}</span
          ><label :for="`batch-name-${entry.id}`">Nome da voz</label
          ><input
            :id="`batch-name-${entry.id}`"
            v-model="entry.metadata.name"
            maxlength="60"
            :disabled="busy"
          />
        </div>
        <div>
          <span class="mobile-label">Ouvir</span
          ><audio
            controls
            preload="metadata"
            :src="entry.url"
            :aria-label="`Ouvir ${entry.file.name}`"
            @play="pauseOthers"
          ></audio>
        </div>
        <div>
          <label :for="`batch-role-${entry.id}`">Uso</label
          ><select
            :id="`batch-role-${entry.id}`"
            v-model="entry.metadata.role"
            :disabled="busy"
          >
            <option value="both">Narrador e personagem</option>
            <option value="narrator">Só narrador</option>
            <option value="character">Só personagem</option>
          </select>
        </div>
        <div>
          <label :for="`batch-gender-${entry.id}`">Gênero</label
          ><select
            :id="`batch-gender-${entry.id}`"
            v-model="entry.metadata.gender"
            :disabled="busy"
          >
            <option value="unknown">Não classificada</option>
            <option value="male">Masculina</option>
            <option value="female">Feminina</option>
            <option value="neutral">Neutra · sem gênero</option>
          </select>
        </div>
        <div>
          <label :for="`batch-kind-${entry.id}`">Tipo de voz</label
          ><select
            :id="`batch-kind-${entry.id}`"
            v-model="entry.metadata.kind"
            :disabled="busy"
          >
            <option value="human">Humana</option>
            <option value="robot">Robótica</option>
            <option value="entity">Criatura ou entidade</option>
          </select>
        </div>
        <button
          type="button"
          class="icon-button"
          :disabled="busy"
          :aria-label="`Remover ${entry.file.name}`"
          @click="remove(entry)"
        >
          <Trash2 :size="18" />
        </button>
        <p v-if="entry.error" class="error-message row-error" role="alert">
          {{ entry.error }}
        </p>
      </div>
    </div>
    <p v-else class="batch-empty">Nenhum áudio selecionado.</p>
    <p v-if="message" role="status" class="batch-message">{{ message }}</p>
    <div class="batch-footer">
      <span>Use gravações suas ou autorizadas.</span
      ><button
        type="button"
        class="primary-button"
        :disabled="busy || !entries.length"
        @click="submit"
      >
        <LoaderCircle v-if="busy" class="spin" :size="18" />{{
          busy
            ? "Importando vozes…"
            : `Importar ${entries.length || ""} ${entries.length === 1 ? "voz" : "vozes"}`
        }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.batch-import {
  padding: 24px 30px 0;
}
.batch-upload {
  flex-direction: row;
  justify-content: flex-start;
  text-align: left;
  gap: 14px;
  padding: 15px;
  margin: 0;
}
.batch-upload span {
  font-size: 11px;
  line-height: 1.7;
}
.batch-help,
.batch-empty,
.batch-message {
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.5;
}
.batch-list {
  margin: 18px 0;
}
.batch-header,
.batch-row {
  display: grid;
  grid-template-columns: minmax(150px, 1.2fr) minmax(175px, 1.1fr) repeat(
      3,
      minmax(120px, 1fr)
    ) 32px;
  gap: 10px;
  align-items: center;
}
.batch-header {
  color: var(--color-muted);
  font-size: 11px;
  padding: 0 0 8px;
}
.batch-row {
  padding: 12px 0;
  border-top: 1px solid var(--color-border);
}
.batch-row > div {
  min-width: 0;
}
.batch-row label,
.mobile-label {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}
.batch-row input,
.batch-row select {
  width: 100%;
  min-width: 0;
  font-size: 12px;
}
.filename {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-muted);
  font-size: 11px;
  margin-bottom: 5px;
}
audio {
  width: 100%;
  height: 36px;
}
.row-error {
  grid-column: 1 / -1;
  margin: 0;
}
.batch-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  padding: 18px 0;
  border-top: 1px solid var(--color-border);
  color: var(--color-muted);
  font-size: 11px;
}
@media (max-width: 900px) {
  .batch-header {
    display: none;
  }
  .batch-row {
    grid-template-columns: repeat(3, minmax(0, 1fr)) 32px;
    align-items: end;
  }
  .batch-name {
    grid-column: span 2;
  }
  .batch-row > div:nth-child(2) {
    grid-column: span 2;
  }
  .batch-row label,
  .mobile-label {
    position: static;
    display: block;
    width: auto;
    height: auto;
    clip-path: none;
    margin-bottom: 5px;
    font-size: 11px;
  }
}
@media (max-width: 600px) {
  .batch-import {
    padding: 20px 20px 0;
  }
  .batch-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .batch-name,
  .batch-row > div:nth-child(2) {
    grid-column: span 2;
  }
  .batch-footer {
    flex-wrap: wrap;
  }
}
</style>
