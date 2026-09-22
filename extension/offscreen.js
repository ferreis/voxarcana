const API_URL = "http://127.0.0.1:8765/v1/speech";
const player = document.getElementById("player");

let currentObjectUrl = null;

function releaseCurrentAudio() {
  player.pause();

  if (currentObjectUrl) {
    URL.revokeObjectURL(currentObjectUrl);
    currentObjectUrl = null;
  }
}

chrome.runtime.onMessage.addListener((message) => {
  if (message.target !== "offscreen" || message.type !== "speak") {
    return;
  }

  void speak(message.text, message.voice);
});

async function speak(text, voice) {
  try {
    releaseCurrentAudio();

    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        text,
        voice,
      }),
    });

    if (!response.ok) {
      throw new Error(`VoxArcana API returned ${response.status}`);
    }

    const audioBlob = await response.blob();
    currentObjectUrl = URL.createObjectURL(audioBlob);

    player.src = currentObjectUrl;
    player.currentTime = 0;
    await player.play();
  } catch (error) {
    console.error("VoxArcana audio playback failed:", error);
  }
}
