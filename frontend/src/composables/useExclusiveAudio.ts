import { onMounted, onUnmounted } from 'vue'

/** Only one preview or narration may play at a time, including other studio tabs. */
export function useExclusiveAudio() {
  let channel: BroadcastChannel | undefined
  const pauseAll = (except?: EventTarget | null) => {
    document.querySelectorAll('audio').forEach(audio => { if (audio !== except) audio.pause() })
  }
  const onPlay = (event: Event) => {
    if (!(event.target instanceof HTMLAudioElement)) return
    pauseAll(event.target)
    channel?.postMessage('playing')
  }
  onMounted(() => {
    if (typeof BroadcastChannel !== 'undefined') {
      channel = new BroadcastChannel('voxarcana.audio')
      channel.onmessage = () => pauseAll()
    }
    document.addEventListener('play', onPlay, true)
  })
  onUnmounted(() => { document.removeEventListener('play', onPlay, true); channel?.close(); pauseAll() })
}
