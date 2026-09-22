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
    await ensureOffscreenDocument();

    await chrome.runtime.sendMessage({
      target: "offscreen",
      type: "speak",
      text: info.selectionText,
      voice: "narrator-epic",
    });
  } catch (error) {
    console.error("VoxArcana:", error);
  }
});
