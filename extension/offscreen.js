const API_URL = "http://127.0.0.1:8765/v1/speech";
const player = document.getElementById("player");
let currentObjectUrl = null;
let controller;
let activeRequest;

function releaseCurrentAudio() {
  controller?.abort();
  controller = null;
  activeRequest = null;
  player.pause();
  player.removeAttribute("src");
  player.load();
  if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl);
  currentObjectUrl = null;
}

async function report(requestId, phase, message) {
  await chrome.runtime.sendMessage({
    target: "background", type: "audio-status", requestId, phase, message,
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id || message.target !== "offscreen") return;
  if (message.type === "speak") {
    void speak(message);
    sendResponse({ ok: true });
  } else if (message.type === "stop") {
    releaseCurrentAudio();
    sendResponse({ ok: true });
  } else if (message.type === "pause") {
    player.pause();
    sendResponse({ ok: true });
  } else if (message.type === "resume") {
    player.play().then(() => sendResponse({ ok: true })).catch((error) => {
      sendResponse({ ok: false, error: error.message });
    });
    return true;
  }
});

player.addEventListener("ended", () => {
  const requestId = activeRequest;
  releaseCurrentAudio();
  if (requestId) void report(requestId, "idle", "Leitura concluída.");
});
player.addEventListener("error", () => {
  const requestId = activeRequest;
  releaseCurrentAudio();
  if (requestId) void report(requestId, "error", "Não foi possível reproduzir o áudio gerado.");
});

async function speak({ text, settings, requestId }) {
  releaseCurrentAudio();
  activeRequest = requestId;
  const requestController = new AbortController();
  controller = requestController;
  const timeout = setTimeout(() => requestController.abort(), 15 * 60 * 1000);
  try {
    const response = await fetch(API_URL, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice: settings.voice, style: settings.style,
        instruction: settings.instruction || null }),
      signal: requestController.signal,
    });
    if (!response.ok) {
      let detail = "Falha ao gerar a voz.";
      try { detail = (await response.json()).detail || detail; } catch { /* Non-JSON error. */ }
      throw new Error(`Motor local (${response.status}): ${String(detail).slice(0, 400)}`);
    }
    const audioBlob = await response.blob();
    if (activeRequest !== requestId) return;
    currentObjectUrl = URL.createObjectURL(audioBlob);
    player.src = currentObjectUrl;
    player.playbackRate = settings.rate;
    await player.play();
    if (activeRequest === requestId) await report(requestId, "playing", "Lendo com voz personalizada…");
  } catch (error) {
    if (activeRequest !== requestId) return;
    releaseCurrentAudio();
    const message = error.name === "AbortError"
      ? "O motor local excedeu 15 minutos. Verifique o terminal do servidor e tente um texto menor."
      : error instanceof TypeError
        ? "Sem conexão com o motor local. Inicie o backend em 127.0.0.1:8765 ou selecione Vozes do Chrome."
        : error.message;
    await report(requestId, "error", message);
  } finally {
    clearTimeout(timeout);
  }
}
