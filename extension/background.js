import { DEFAULT_SETTINGS, normalizeSettings, validateText } from "./settings.js";

const OFFSCREEN_URL = "offscreen.html";
let creating;
// Serialize commands so Stop wins over an earlier, still-starting read.
let commands = Promise.resolve();

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "voxarcana-read-selection", title: "Narrar com VoxArcana", contexts: ["selection"],
    });
  });
});

async function hasOffscreen() {
  const contexts = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT"],
    documentUrls: [chrome.runtime.getURL(OFFSCREEN_URL)],
  });
  return contexts.length > 0;
}

async function ensureOffscreenDocument() {
  if (creating) return creating;
  creating = (async () => {
    if (await hasOffscreen()) return;
    await chrome.offscreen.createDocument({
      url: OFFSCREEN_URL,
      // Blob URLs are needed after synthesis, which can take several minutes.
      reasons: ["AUDIO_PLAYBACK", "BLOBS"],
      justification: "Gerar e reproduzir áudio local com URLs de Blob, inclusive em gerações longas.",
    });
  })();
  try { await creating; } finally { creating = null; }
}

async function setStatus(phase, message, extra = {}) {
  await chrome.storage.session.set({ playback: { phase, message, ...extra } });
}

async function updateRequest(requestId, phase, message) {
  const { playback } = await chrome.storage.session.get("playback");
  if (playback?.requestId === requestId) {
    await setStatus(phase, message, { requestId, engine: playback.engine });
  }
}

async function stop() {
  // Invalidate old events before stopping either engine.
  await setStatus("idle", "Leitura parada.");
  chrome.tts.stop();
  if (await hasOffscreen()) {
    await chrome.runtime.sendMessage({ target: "offscreen", type: "stop" });
  }
}

async function speak(message) {
  const text = validateText(message.text);
  const saved = await chrome.storage.local.get("settings");
  const settings = normalizeSettings(message.settings ?? saved.settings ?? DEFAULT_SETTINGS);
  let selected;
  if (settings.engine === "browser") {
    const voices = await chrome.tts.getVoices();
    const brazilian = voices.filter((voice) => voice.lang?.toLowerCase().replace("_", "-") === "pt-br");
    selected = brazilian.find((voice) => voice.voiceName === settings.voiceName &&
      (voice.extensionId || "") === settings.extensionId) ?? brazilian[0];
    if (!selected) {
      throw new Error("Nenhuma voz PT-BR disponível no Chrome. Use o motor local ou instale uma voz brasileira no sistema/Chrome.");
    }
  }
  await stop();
  const requestId = crypto.randomUUID();
  await setStatus("loading", settings.engine === "local"
    ? "Gerando voz local… A primeira leitura pode levar alguns minutos."
    : "Preparando leitura…", { requestId, engine: settings.engine });
  if (settings.engine === "local") {
    await ensureOffscreenDocument();
    const response = await chrome.runtime.sendMessage({
      target: "offscreen", type: "speak", requestId, text, settings,
    });
    if (!response?.ok) throw new Error(response?.error || "Não foi possível iniciar o áudio local.");
    return;
  }
  chrome.tts.speak(text, {
    lang: "pt-BR", voiceName: selected.voiceName,
    ...(selected.extensionId ? { extensionId: selected.extensionId } : {}),
    rate: settings.rate, pitch: settings.pitch, enqueue: false,
    onEvent(event) {
      const states = {
        start: ["playing", "Lendo em português do Brasil…"],
        end: ["idle", "Leitura concluída."],
        interrupted: ["idle", "Leitura interrompida."],
        cancelled: ["idle", "Leitura cancelada."],
        error: ["error", event.errorMessage || "Não foi possível reproduzir essa voz."],
      };
      if (states[event.type]) void queue(() => updateRequest(requestId, ...states[event.type]));
    },
  }, () => {
    if (chrome.runtime.lastError) {
      const error = chrome.runtime.lastError.message;
      void queue(() => updateRequest(requestId, "error", error));
    }
  });
}

async function control(type) {
  const { playback } = await chrome.storage.session.get("playback");
  if (!playback || !["playing", "paused"].includes(playback.phase)) return;
  if (playback.engine === "local") {
    if (!(await hasOffscreen())) {
      await setStatus("idle", "O áudio foi encerrado. Inicie uma nova leitura.");
      return;
    }
    const response = await chrome.runtime.sendMessage({ target: "offscreen", type });
    if (!response?.ok) throw new Error(response?.error || "Não foi possível controlar o áudio.");
  } else {
    if (type === "pause") chrome.tts.pause();
    else chrome.tts.resume();
  }
  await setStatus(type === "pause" ? "paused" : "playing",
    type === "pause" ? "Leitura pausada." : "Lendo…",
    { requestId: playback.requestId, engine: playback.engine });
}

function queue(action) {
  const result = commands.then(action);
  commands = result.catch(() => {});
  return result;
}

function execute(action) {
  return queue(async () => {
    try {
      await action();
    } catch (error) {
      await stop();
      await setStatus("error", error.message);
      throw error;
    }
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || message.target !== "background") return;
  const actions = {
    speak: () => speak(message), stop,
    pause: () => control("pause"), resume: () => control("resume"),
    "audio-status": () => updateRequest(message.requestId, message.phase, message.message),
  };
  if (!Object.hasOwn(actions, message.type)) return;
  execute(actions[message.type]).then(() => sendResponse({ ok: true })).catch((error) => {
    sendResponse({ ok: false, error: error.message });
  });
  return true;
});

chrome.contextMenus.onClicked.addListener((info) => {
  if (info.menuItemId !== "voxarcana-read-selection") return;
  void execute(() => speak({ text: info.selectionText })).catch(async () => {
    await chrome.action.setBadgeText({ text: "!" });
    await chrome.action.setBadgeBackgroundColor({ color: "#b33838" });
  });
});
