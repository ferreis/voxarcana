export const DEFAULT_SETTINGS = {
  engine: "browser", voiceName: "", extensionId: "", voice: "narrator-br",
  style: "neutral", instruction: "", rate: 1, pitch: 1,
};
export const API_URL = "http://127.0.0.1:8765";

export function normalizeSettings(value = {}) {
  const number = (input, min, max, fallback) => {
    const parsed = Number(input);
    return Number.isFinite(parsed) ? Math.min(max, Math.max(min, parsed)) : fallback;
  };
  return {
    engine: value.engine === "local" ? "local" : "browser",
    voiceName: typeof value.voiceName === "string" ? value.voiceName : "",
    extensionId: typeof value.extensionId === "string" ? value.extensionId : "",
    voice: typeof value.voice === "string" ? value.voice : "narrator-br",
    style: typeof value.style === "string" ? value.style : "neutral",
    instruction: typeof value.instruction === "string" ? value.instruction.slice(0, 2000) : "",
    rate: number(value.rate ?? 1, 0.5, 2, 1),
    pitch: number(value.pitch ?? 1, 0, 2, 1),
  };
}

export function validateText(text) {
  if (typeof text !== "string" || !text.trim()) throw new Error("Digite ou selecione um texto para ler.");
  if (text.length > 10000) throw new Error("Use até 10.000 caracteres por leitura.");
  return text.trim();
}
