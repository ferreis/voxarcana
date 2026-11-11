export interface VoiceMetadata { name: string; role: 'narrator' | 'character' | 'both'; gender: 'male' | 'female' | 'neutral' | 'unknown'; kind: 'human' | 'robot' | 'entity' }
export interface Voice extends Partial<VoiceMetadata> { editable?: boolean; id: string; name: string; locale?: string; description?: string }
export interface Style { id: string; name: string }
export interface Engine { id: string; name: string; locale: string; installed: boolean; reference_audio: boolean; voice_description: boolean }
export interface SceneSegment { id: number; kind: string; text: string; speaker: string; gender: string; voice_id?: string; character_saved?: boolean; delivery: string; channel?: 'none' | 'radio' | 'television' }
export interface Scene { method: string; warning: string | null; segments: SceneSegment[] }
export interface Job { id: string; status: 'review' | 'queued' | 'running' | 'cancelling' | 'cancelled' | 'done' | 'error'; completed: number; total: number; error: string | null; source_text?: string | null; analysis_percent?: number; analysis_events?: string[]; stage?: string; scene?: Scene | null; speaker?: string | null; delivery?: string | null }
export interface Speech { text: string; voice: string; style: string; automatic?: boolean; review?: boolean; speed?: number }

export interface ReviewedLine { id: number; speaker: string; gender: string; voice_id: string }

export interface SavedCharacter { id: string; name: string; gender: string; voice_id: string; voice_name: string | null; available: boolean; aliases: string[] }

export class StudioError extends Error {
  constructor(message: string, public status: number) { super(message); this.name = 'StudioError' }
}

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { ...init, signal: init.signal ?? AbortSignal.timeout(15000) })
  if (!response.ok) {
    let detail = `Não foi possível concluir a operação (${response.status}).`
    try {
      const data = await response.json()
      detail = typeof data.detail === 'string' ? data.detail : 'Confira os campos e tente novamente.'
    } catch { /* Use the HTTP error above. */ }
    throw new StudioError(detail, response.status)
  }
  return response.json() as Promise<T>
}
export const studioApi = {
  async youtubeClip(url: string, startSeconds: number, signal?: AbortSignal) {
    const response = await fetch('/v1/audio/youtube', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, start_seconds: startSeconds }),
      signal: signal ?? AbortSignal.timeout(135000),
    })
    if (!response.ok) {
      let message = 'Não consegui extrair o áudio do YouTube. Tente outro vídeo.'
      try {
        const problem = await response.json()
        if (typeof problem.detail === 'string') message = problem.detail
      } catch { /* Keep the extraction error when the response is not JSON. */ }
      throw new StudioError(message, response.status)
    }
    return response.blob()
  },
  characters: () => request<SavedCharacter[]>('/v1/characters'),
  updateCharacter: (id: string, character: { name: string; gender: string; voice_id: string; aliases?: string[] }) => request<SavedCharacter>(`/v1/characters/${encodeURIComponent(id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(character) }),
  engine: () => request<Engine>('/v1/engine'),
  voices: () => request<Voice[]>('/v1/voices'),
  styles: () => request<Style[]>('/v1/styles'),
  generate: (speech: Speech) => request<{ id: string }>('/v1/jobs', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(speech),
  }),
  perform: (id: string, voice: string, style: string, lines: ReviewedLine[], speed: number) => request<{ id: string }>(`/v1/jobs/${encodeURIComponent(id)}/perform`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ voice, style, lines, speed }) }),
  job: (id: string, signal?: AbortSignal) => request<Job>(`/v1/jobs/${encodeURIComponent(id)}`, { signal }),
  cancel: (id: string) => request<Job>(`/v1/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  async audio(id: string, signal?: AbortSignal) {
    const response = await fetch(`/v1/jobs/${encodeURIComponent(id)}/audio`, { signal: signal ?? AbortSignal.timeout(30000) })
    if (!response.ok) throw new Error('Não consegui carregar o áudio. Gere a narração novamente.')
    return response.blob()
  },
  deleteVoice: (id: string) => request<{ id: string; deleted: boolean }>(`/v1/voices/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  updateVoice(id: string, metadata: VoiceMetadata) {
    return request<Voice>(`/v1/voices/${encodeURIComponent(id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(metadata) })
  },
  reference(name: string, file: File, metadata?: VoiceMetadata) {
    const form = new FormData()
    form.append('name', name)
    form.append('audio', file)
    if (metadata) for (const key of ['role', 'gender', 'kind'] as const) form.append(key, metadata[key])
    return request<Voice>('/v1/voices/reference', { method: 'POST', body: form, signal: AbortSignal.timeout(60000) })
  },
}
