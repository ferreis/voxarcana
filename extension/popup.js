import { API_URL, DEFAULT_SETTINGS, normalizeSettings } from "./settings.js";

const $ = (id) => document.getElementById(id);
const styles = [
  ["neutral", "Neutro"], ["epic", "Fantasia Épica"], ["terror", "Terror"],
  ["action", "Ação"], ["suspense", "Suspense"], ["mystery", "Mistério"],
  ["calm", "Calmo"], ["noir", "Detetive Noir"],
  ["storyteller", "Contador de Histórias"], ["documentary", "Documentário"],
];
let settings = { ...DEFAULT_SETTINGS };
let phase = "idle";
let saving = Promise.resolve();
let voices = [];
let sending = false;

function options(select, items, selected) {
  select.replaceChildren(...items.map(([value, label]) => new Option(label, value)));
  if (items.some(([value]) => value === selected)) select.value = selected;
}

function renderSettings() {
  $("browser-settings").hidden = settings.engine !== "browser";
  $("local-settings").hidden = settings.engine !== "local";
  $("rate-value").value = `${Number($("rate").value).toLocaleString("pt-BR", { minimumFractionDigits: 1 })}×`;
  $("pitch-value").value = Number($("pitch").value).toLocaleString("pt-BR", { minimumFractionDigits: 1 });
}

function renderStatus(playback) {
  phase = playback?.phase || "idle";
  $("status").textContent = playback?.message || "Pronto para ler.";
  $("status").dataset.phase = phase;
  $("pause").disabled = !["playing", "paused"].includes(phase);
  $("pause").textContent = phase === "paused" ? "Continuar" : "Pausar";
  $("stop").disabled = !["loading", "playing", "paused"].includes(phase);
}

function collectSettings() {
  const voice = voices[Number($("browser-voice").value)];
  return normalizeSettings({
    engine: $("engine").value,
    voiceName: voice?.voiceName || "", extensionId: voice?.extensionId || "",
    voice: $("local-voice").value, style: $("style").value,
    instruction: $("instruction").value, rate: $("rate").value, pitch: $("pitch").value,
  });
}

function saveSettings() {
  settings = collectSettings();
  const snapshot = { ...settings };
  saving = saving.catch(() => {}).then(() => chrome.storage.local.set({ settings: snapshot }));
  void saving.catch((error) => renderStatus({ phase: "error", message: error.message }));
  renderSettings();
}

async function refreshVoices() {
  const available = await chrome.tts.getVoices();
  voices = available.filter((voice) => voice.lang?.toLowerCase().replace("_", "-") === "pt-br");
  const selected = voices.findIndex((voice) => voice.voiceName === settings.voiceName &&
    (voice.extensionId || "") === settings.extensionId);
  options($("browser-voice"), voices.length
    ? voices.map((voice, index) => [String(index), `${voice.voiceName}${voice.remote ? " · online" : ""}`])
    : [["", "Nenhuma voz PT-BR encontrada"]], String(Math.max(0, selected)));
  $("browser-voice").disabled = !voices.length;
  $("voice-help").textContent = voices.length
    ? "As vozes dependem do Chrome e do sistema. Algumas precisam de internet."
    : "Nenhuma voz brasileira disponível. Use o motor local ou instale uma voz PT-BR no sistema/Chrome. Depois clique em Atualizar vozes.";
}

async function checkLocal() {
  $("check-local").disabled = true;
  $("connection").textContent = "Verificando conexão…";
  try {
    const [voiceResponse, styleResponse] = await Promise.all([
      fetch(`${API_URL}/v1/voices`, { signal: AbortSignal.timeout(4000) }),
      fetch(`${API_URL}/v1/styles`, { signal: AbortSignal.timeout(4000) }),
    ]);
    if (!voiceResponse.ok || !styleResponse.ok) throw new Error("API indisponível");
    const [localVoices, localStyles] = await Promise.all([voiceResponse.json(), styleResponse.json()]);
    if (!localVoices.length || !localStyles.length) throw new Error("Sem perfis disponíveis");
    options($("local-voice"), localVoices.map((voice) => [voice.id, voice.name]), settings.voice);
    options($("style"), localStyles.map((style) => [style.id, style.name]), settings.style);
    $("connection").textContent = "Servidor conectado. O modelo será carregado na primeira leitura; isso pode levar alguns minutos.";
    saveSettings();
  } catch {
    $("connection").textContent = "Sem conexão. Inicie o backend em 127.0.0.1:8765 seguindo o README do projeto. Você também pode usar Vozes do Chrome.";
  } finally {
    $("check-local").disabled = false;
  }
}

async function command(type, extra = {}) {
  const response = await chrome.runtime.sendMessage({ target: "background", type, ...extra });
  if (!response?.ok) throw new Error(response?.error || "Não foi possível executar a leitura.");
}

async function run(action) {
  try { await action(); } catch (error) { renderStatus({ phase: "error", message: error.message }); }
}

async function init() {
  const [local, session] = await Promise.all([
    chrome.storage.local.get("settings"), chrome.storage.session.get(["draft", "playback"]),
  ]);
  settings = normalizeSettings(local.settings);
  $("engine").value = settings.engine;
  $("rate").value = settings.rate;
  $("pitch").value = settings.pitch;
  $("instruction").value = settings.instruction;
  options($("style"), styles, settings.style);
  $("local-voice").value = settings.voice;
  $("text").value = session.draft || "";
  $("count").value = `${$("text").value.length.toLocaleString("pt-BR")} / 10.000`;
  renderSettings();
  renderStatus(session.playback);
  // A voice list failure must not prevent using the local engine.
  await run(refreshVoices);
  await chrome.action.setBadgeText({ text: "" });

  $("reader").addEventListener("submit", (event) => {
    event.preventDefault();
    if (sending) return;
    void run(async () => {
      sending = true;
      $("speak").disabled = true;
      try {
        saveSettings();
        await saving;
        await command("speak", { text: $("text").value, settings });
      } finally {
        sending = false;
        $("speak").disabled = false;
      }
    });
  });
  $("pause").addEventListener("click", () => void run(() => command(phase === "paused" ? "resume" : "pause")));
  $("stop").addEventListener("click", () => void run(() => command("stop")));
  $("refresh-voices").addEventListener("click", () => void run(refreshVoices));
  $("check-local").addEventListener("click", () => void checkLocal());
  for (const id of ["engine", "browser-voice", "local-voice", "style", "instruction", "rate", "pitch"]) {
    $(id).addEventListener(id === "instruction" || id === "rate" || id === "pitch" ? "input" : "change", saveSettings);
  }
  $("text").addEventListener("input", () => {
    $("count").value = `${$("text").value.length.toLocaleString("pt-BR")} / 10.000`;
    void run(() => chrome.storage.session.set({ draft: $("text").value }));
  });
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session" && changes.playback) renderStatus(changes.playback.newValue);
});
void run(init);
