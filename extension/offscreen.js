const player = document.getElementById("player");

chrome.runtime.onMessage.addListener((message) => {
  if (message.target !== "offscreen" || message.type !== "play-audio") {
    return;
  }

  player.pause();
  player.src = message.dataUrl;
  player.currentTime = 0;
  player.play().catch((error) => {
    console.error("VoxArcana audio playback failed:", error);
  });
});
