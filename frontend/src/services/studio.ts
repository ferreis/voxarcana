export interface Voice { id: string; name: string; locale?: string; description?: string }
export interface Style { id: string; name: string }
export interface Engine { id: string; name: string; locale: string; installed: boolean; reference_audio: boolean; voice_description: boolean }
export interface Job { id: string; status: 'queued' | 'running' | 'cancelling' | 'cancelled' | 'done' | 'error'; completed: number; total: number; error: string | null }
export interface Speech { text: string; voice: string; style: string }

async function request<T>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, { ...init, signal: init.signal ?? AbortSignal.timeout(15000) })
  if (!response.ok) {
    let detail = `Não foi possível concluir a operação (${response.status}).`
    try {
      const data = await response.json()
      detail = typeof data.detail === 'string' ? data.detail : 'Confira os campos e tente novamente.'
    } catch { /* Use the HTTP error above. */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}
export const studioApi = {
  engine: () => request<Engine>('/v1/engine'),
  voices: () => request<Voice[]>('/v1/voices'),
  styles: () => request<Style[]>('/v1/styles'),
  generate: (speech: Speech) => request<{ id: string }>('/v1/jobs', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(speech),
  }),
  job: (id: string, signal?: AbortSignal) => request<Job>(`/v1/jobs/${encodeURIComponent(id)}`, { signal }),
  cancel: (id: string) => request<Job>(`/v1/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  async audio(id: string, signal?: AbortSignal) {
    const response = await fetch(`/v1/jobs/${encodeURIComponent(id)}/audio`, { signal: signal ?? AbortSignal.timeout(30000) })
    if (!response.ok) throw new Error('Não consegui carregar o áudio. Gere a narração novamente.')
    return response.blob()
  },
  reference(name: string, file: File) {
    const form = new FormData()
    form.append('name', name)
    form.append('audio', file)
    return request<Voice>('/v1/voices/reference', { method: 'POST', body: form })
  },
}
