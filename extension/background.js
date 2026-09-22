const API_URL = "http://127.0.0.1:8765/v1/speech";
const OFFSCREEN_URL = "offscreen.html";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "voxarcana-read-selection",
    title: "Narrar com VoxArcana",
    contexts: ["selection"],
  });
});

async function ensureOffscreenDocument() {
  const contexts = await chrome.runtime.getContexts({
    contextTypes: ["OFFSCREEN_DOCUMENT"],
    documentUrls: [chrome.runtime.getURL(OFFSCREEN_URL)],
  });

  if (contexts.length > 0) {
    return;
  }

  await chrome.offscreen.createDocument({
    url: OFFSCREEN_URL,
    reasons: ["AUDIO_PLAYBACK"],
    justification: "Reproduzir o áudio TTS gerado localmente pelo VoxArcana.",
  });
}

chrome.contextMenus.onClicked.addListener(async (info) => {
  if (info.menuItemId !== "voxarcana-read-selection" || !info.selectionText) {
    return;
  }

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text: info.selectionText,
        voice: "narrator-epic",
      }),
    });

    if (!response.ok) {
      throw new Error(`VoxArcana API returned ${response.status}`);
    }

    const blob = await response.blob();
    const reader = new FileReader();
    const dataUrl = await new Promise((resolve, reject) => {
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });

    await ensureOffscreenDocument();
    await chrome.runtime.sendMessage({
      target: "offscreen",
      type: "play-audio",
      dataUrl,
    });
  } catch (error) {
    console.error("VoxArcana:", error);
  }
});
