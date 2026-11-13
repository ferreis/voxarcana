import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  studioApi,
  StudioError,
  type Engine,
  type Project,
  type Job,
  type Voice,
  type Style,
  type VoiceMetadata,
  type ReviewedLine,
} from "../services/studio";

const STORAGE = "voxarcana.studio.v1";
interface Saved {
  activeProject?: string;
  projects?: Record<string, Saved>;
  text?: string;
  title?: string;
  generationTitle?: string;
  voice?: string;
  style?: string;
  speed?: number;
  job?: string;
  narrationOnly?: boolean;
}
function readSaved(): Saved {
  try {
    return JSON.parse(localStorage.getItem(STORAGE) || "{}") ?? {};
  } catch {
    return {};
  }
}
export function useStudio() {
  const workspace = readSaved();
  const projectId = ref(workspace.activeProject || 'default');
  const saved = workspace.projects?.[projectId.value] || (projectId.value === 'default' ? workspace : {});
  const projects = ref<Project[]>([]);
  const text = ref(
    typeof saved.text === "string" ? saved.text.slice(0, 10000) : "",
  );
  const title = ref(
    typeof saved.title === "string"
      ? saved.title.slice(0, 80)
      : "Nova narração",
  );
  const generationTitle = ref(saved.generationTitle || title.value.trim() || "Narração");
  const voice = ref(typeof saved.voice === "string" ? saved.voice : "");
  const style = ref(typeof saved.style === "string" ? saved.style : "neutral");
  const speed = ref(
    typeof saved.speed === "number" && saved.speed >= 0.5 && saved.speed <= 2
      ? saved.speed
      : 1,
  );
  const voices = ref<Voice[]>([]);
  const styles = ref<Style[]>([]);
  const engine = ref<Engine | null>(null);
  const connected = ref(false);
  const checking = ref(false);
  const submitting = ref(false);
  const restoringProject = ref(false);
  const error = ref("");
  const notice = ref("");
  const job = ref<Job | null>(null);
  const narrationOnly = ref(saved.narrationOnly === true);
  const audioUrl = ref("");
  const audioTitle = ref("");
  const elapsed = ref(0);
  let startedAt = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let unmounted = false;
  const controller = new AbortController();
  const busy = computed(
    () =>
      restoringProject.value || submitting.value ||
      (!!job.value &&
        ["queued", "running", "cancelling"].includes(job.value.status)),
  );
  const canPerform = computed(
    () =>
      !busy.value &&
      connected.value &&
      !!voice.value &&
      !narrationOnly.value &&
      !!job.value?.scene &&
      ["review", "done"].includes(job.value.status) &&
      job.value.source_text === text.value.trim(),
  );
  const words = computed(
    () => text.value.trim().split(/\s+/).filter(Boolean).length,
  );
  const selectedVoice = computed(() =>
    voices.value.find((item) => item.id === voice.value),
  );
  const status = computed(() => {
    if (submitting.value && !job.value)
      return narrationOnly.value
        ? "Preparando a narração…"
        : "Preparando a análise…";
    if (job.value?.status === "review")
      return "Análise pronta. Revise os personagens e escolha suas vozes.";
    if (job.value?.status === "queued")
      return narrationOnly.value || job.value.scene
        ? "A geração do áudio está na fila…"
        : "A análise do texto está na fila…";
    if (job.value?.status === "cancelling")
      return job.value.stage === "analyzing"
        ? "Cancelando a análise da cena…"
        : "Cancelando após o trecho atual…";
    if (job.value?.status === "running" && job.value.stage === "analyzing")
      return "Entendendo a cena e identificando as vozes…";
    if (job.value?.status === "running" && job.value.stage === "assembling")
      return "Unindo as vozes da sua cena…";
    if (job.value?.status === "running")
      return job.value.total
        ? `Narrando ${job.value.speaker || "a cena"} · trecho ${Math.min(job.value.completed + 1, job.value.total)} de ${job.value.total}`
        : "Preparando a voz brasileira…";
    if (job.value?.status === "done") return "Sua narração está pronta.";
    if (job.value?.status === "cancelled") return "Narração cancelada.";
    return "Pronto para a próxima história.";
  });
  function persist() {
    try {
      const previousWorkspace = readSaved();
      localStorage.setItem(
        STORAGE,
        JSON.stringify({
          ...previousWorkspace,
          activeProject: projectId.value,
          projects: {
            ...previousWorkspace.projects,
            [projectId.value]: {
              text: text.value,
              title: title.value,
              generationTitle: generationTitle.value,
              voice: voice.value,
              style: style.value,
              speed: speed.value,
              job: job.value?.id,
              narrationOnly: narrationOnly.value,
            },
          },
        }),
      );
    } catch {
      /* Private/full storage: keep working in memory. */
    }
  }
  watch(
    [text, title, generationTitle, voice, style, speed, narrationOnly, () => job.value?.id],
    persist,
  );
  const clock = setInterval(() => {
    if (busy.value) elapsed.value = Math.round((Date.now() - startedAt) / 1000);
  }, 1000);

  async function connect() {
    checking.value = true;
    error.value = "";
    try {
      const [nextEngine, nextVoices, nextStyles, nextProjects] = await Promise.all([
        studioApi.engine(),
        studioApi.voices(),
        studioApi.styles(),
        studioApi.projects(),
      ]);
      projects.value = nextProjects;
      engine.value = nextEngine;
      voices.value = nextVoices;
      styles.value = nextStyles;
      connected.value = true;
      if (
        !nextVoices.some(
          (item) => item.id === voice.value && item.role !== "character",
        )
      )
        voice.value =
          nextVoices.find((item) => item.role !== "character")?.id || "";
      if (
        !nextStyles.some((item) => item.id === style.value) ||
        (nextEngine.id === "chatterbox-br" &&
          !["neutral", "storyteller", "calm"].includes(style.value))
      )
        style.value = "neutral";
      if (nextEngine.id !== "chatterbox-br")
        error.value =
          "O motor brasileiro ainda não está ativo. Inicie com ./start.";
    } catch {
      connected.value = false;
      error.value =
        "Não consegui conectar ao estúdio. Confira se o servidor está aberto e tente reconectar.";
    } finally {
      checking.value = false;
    }
  }

  async function poll(id: string) {
    const requestedProject = projectId.value;
    try {
      const next = await studioApi.job(id, controller.signal);
      if (unmounted || requestedProject !== projectId.value) return;
      if ((next.project_id || 'default') !== requestedProject) {
        notice.value = 'Essa análise pertence a outro projeto. Analise este texto novamente.';
        return;
      }
      if (next.status === "review" && job.value?.status !== "review" &&
          next.scene?.title && next.source_text === text.value.trim() &&
          (title.value.trim() || "Narração") === generationTitle.value) {
        title.value = next.scene.title.trim().slice(0, 80);
      }
      // Keep the review form intact when polling only updates generation progress.
      if (job.value?.id === next.id && next.scene &&
          JSON.stringify(next.scene) === JSON.stringify(job.value.scene)) {
        next.scene = job.value.scene;
      }
      job.value = next;
      if (next.status === "done") {
        const blob = await studioApi.audio(id, controller.signal);
        if (unmounted || requestedProject !== projectId.value) return;
        if (audioUrl.value) URL.revokeObjectURL(audioUrl.value);
        audioUrl.value = URL.createObjectURL(blob);
        audioTitle.value = generationTitle.value;
      } else if (next.status === "error") {
        error.value =
          next.error ||
          "Não foi possível gerar a narração. Tente um texto menor.";
      } else if (["queued", "running", "cancelling"].includes(next.status)) {
        timer = setTimeout(() => void poll(id), 1500);
      }
    } catch (problem) {
      if (unmounted || requestedProject !== projectId.value) return;
      if (problem instanceof StudioError && problem.status === 404) {
        job.value = null;
        notice.value = "";
        return;
      }
      error.value =
        problem instanceof Error ? problem.message : "Falha de conexão.";
      // Preserve the ID so a reload/reconnect can recover a running job.
      notice.value =
        "A geração pode continuar no servidor. Clique em Reconectar para recuperar o andamento.";
    }
  }

  async function reconnect() {
    await connect();
    if (connected.value && job.value?.id) {
      clearTimeout(timer);
      notice.value = "";
      await poll(job.value.id);
    }
  }
  async function startGeneration(interpret: boolean) {
    if (busy.value) return;
    error.value = "";
    notice.value = "";
    if (!voice.value) {
      error.value = "Adicione uma voz de narrador antes de continuar.";
      return;
    }
    if (!text.value.trim()) {
      error.value = "Cole ou escreva o texto que você quer narrar.";
      return;
    }
    generationTitle.value = title.value.trim() || "Narração";
    submitting.value = true;
    narrationOnly.value = !interpret;
    job.value = null;
    startedAt = Date.now();
    elapsed.value = 0;
    try {
      const result = await studioApi.generate({
        project_id: projectId.value,
        text: text.value,
        voice: voice.value,
        style: style.value,
        automatic: interpret,
        review: interpret,
        speed: speed.value,
      });
      job.value = {
        id: result.id,
        status: "queued",
        stage: interpret ? "analyzing" : "queued",
        completed: 0,
        total: 0,
        error: null,
      };
      await poll(result.id);
    } catch (problem) {
      error.value =
        problem instanceof Error
          ? problem.message
          : "Não foi possível iniciar o processamento.";
    } finally {
      submitting.value = false;
    }
  }
  function analyze() {
    return startGeneration(true);
  }
  function narrate() {
    return startGeneration(false);
  }
  async function perform(lines: ReviewedLine[]) {
    if (busy.value || !job.value) return;
    if (job.value.source_text !== text.value.trim()) {
      error.value = "O texto mudou. Analise novamente antes de gerar.";
      return;
    }
    if (!canPerform.value) return;
    generationTitle.value = title.value.trim() || "Narração";
    submitting.value = true;
    error.value = "";
    startedAt = Date.now();
    elapsed.value = 0;
    try {
      const result = await studioApi.perform(
        job.value.id,
        voice.value,
        style.value,
        lines,
        speed.value,
      );
      job.value = {
        ...job.value,
        status: "queued",
        stage: "queued",
        completed: 0,
        total: 0,
        error: null,
      };
      await poll(result.id);
    } catch (problem) {
      error.value =
        problem instanceof Error
          ? problem.message
          : "Não consegui iniciar o áudio.";
    } finally {
      submitting.value = false;
    }
  }
  async function selectProject(nextProjectId: string) {
    if (busy.value || nextProjectId === projectId.value || !projects.value.some(project => project.id === nextProjectId)) return;
    persist();
    clearTimeout(timer);
    const draft = readSaved().projects?.[nextProjectId] || {};
    projectId.value = nextProjectId;
    text.value = draft.text || '';
    title.value = draft.title || 'Nova narração';
    generationTitle.value = draft.generationTitle || title.value.trim() || 'Narração';
    voice.value = voices.value.find(candidate => candidate.id === draft.voice && candidate.role !== 'character')?.id
      || voices.value.find(candidate => candidate.role !== 'character')?.id || '';
    style.value = draft.style || 'neutral';
    speed.value = draft.speed || 1;
    narrationOnly.value = draft.narrationOnly === true;
    job.value = null;
    elapsed.value = 0;
    error.value = ''; notice.value = '';
    if (audioUrl.value) URL.revokeObjectURL(audioUrl.value);
    audioUrl.value = ''; audioTitle.value = '';
    persist();
    if (draft.job) {
      restoringProject.value = true;
      try { await poll(draft.job); }
      finally { restoringProject.value = false; }
    }
  }
  async function createProject(name: string) {
    if (busy.value) return;
    const project = await studioApi.createProject(name);
    projects.value = [...projects.value, project];
    await selectProject(project.id);
  }
  async function cancel() {
    if (!job.value) return;
    try {
      job.value = await studioApi.cancel(job.value.id);
    } catch (problem) {
      error.value =
        problem instanceof Error
          ? problem.message
          : "Não foi possível cancelar.";
    }
  }
  async function addReference(
    name: string,
    file: File,
    metadata?: VoiceMetadata,
  ) {
    const result = await studioApi.reference(name, file, metadata);
    voices.value = [...voices.value, result];
    if (result.role !== "character") voice.value = result.id;
  }
  async function updateVoice(id: string, metadata: VoiceMetadata) {
    const result = await studioApi.updateVoice(id, metadata);
    voices.value = voices.value.map((item) => (item.id === id ? result : item));
    if (voice.value === id && result.role === "character")
      voice.value =
        voices.value.find((item) => item.role !== "character")?.id || "";
  }
  async function deleteVoice(id: string) {
    await studioApi.deleteVoice(id);
    voices.value = voices.value.filter((item) => item.id !== id);
    if (voice.value === id)
      voice.value =
        voices.value.find((item) => item.role !== "character")?.id || "";
  }
  onMounted(async () => {
    await connect();
    if (typeof saved.job === "string" && connected.value) {
      startedAt = Date.now();
      await poll(saved.job);
    }
  });
  onUnmounted(() => {
    unmounted = true;
    clearInterval(clock);
    clearTimeout(timer);
    controller.abort();
    if (audioUrl.value) URL.revokeObjectURL(audioUrl.value);
  });
  return {
    projectId,
    projects,
    selectProject,
    createProject,
    text,
    title,
    voice,
    style,
    speed,
    voices,
    styles,
    engine,
    connected,
    checking,
    busy,
    canPerform,
    job,
    narrationOnly,
    error,
    notice,
    audioUrl,
    audioTitle,
    elapsed,
    words,
    selectedVoice,
    status,
    analyze,
    narrate,
    perform,
    cancel,
    reconnect,
    addReference,
    updateVoice,
    deleteVoice,
  };
}
