from dataclasses import dataclass


@dataclass(frozen=True)
class StyleProfile:
    id: str
    name: str
    instruction: str


STYLE_PROFILES = {
    "epic": StyleProfile(
        id="epic",
        name="Fantasia Épica",
        instruction=(
            "Epic dark-fantasy storyteller. Cinematic, serious and immersive. "
            "Use a slow, deliberate rhythm, natural dramatic pauses and controlled intensity. "
            "Sound grand without becoming a commercial announcer."
        ),
    ),
    "terror": StyleProfile(
        id="terror",
        name="Terror",
        instruction=(
            "Dark horror narration. Lower the intensity rather than shouting. "
            "Use tense pauses, restrained dread, subtle unease and an intimate ominous delivery."
        ),
    ),
    "action": StyleProfile(
        id="action",
        name="Ação",
        instruction=(
            "Energetic action narration. Use a faster pace, strong momentum and clear emphasis. "
            "Keep articulation natural and controlled, without sounding rushed."
        ),
    ),
    "suspense": StyleProfile(
        id="suspense",
        name="Suspense",
        instruction=(
            "Suspenseful cinematic narration. Build tension progressively with careful pacing, "
            "short dramatic pauses and restrained anticipation."
        ),
    ),
    "mystery": StyleProfile(
        id="mystery",
        name="Mistério",
        instruction=(
            "Mysterious investigative narration. Sound observant, restrained and intriguing, "
            "with a measured pace and subtle emphasis on clues and uncertainty."
        ),
    ),
    "calm": StyleProfile(
        id="calm",
        name="Calmo",
        instruction=(
            "Calm and comfortable narration. Use a warm tone, relaxed rhythm, soft transitions "
            "and natural pauses while remaining clear and attentive."
        ),
    ),
    "noir": StyleProfile(
        id="noir",
        name="Detetive Noir",
        instruction=(
            "Classic noir detective narration. Low, introspective and slightly weary delivery, "
            "with dry restraint, measured pauses and a cinematic internal-monologue feel."
        ),
    ),
    "storyteller": StyleProfile(
        id="storyteller",
        name="Contador de Histórias",
        instruction=(
            "Traditional storyteller delivery. Warm, expressive and inviting, with clear phrasing, "
            "gentle variation in rhythm and emphasis appropriate for oral storytelling."
        ),
    ),
    "documentary": StyleProfile(
        id="documentary",
        name="Documentário",
        instruction=(
            "Professional documentary narration. Neutral, confident and informative, "
            "with steady pacing, precise diction and restrained emotional emphasis."
        ),
    ),
    "neutral": StyleProfile(
        id="neutral",
        name="Neutro",
        instruction=(
            "Natural neutral narration. Use conversational pacing, clear diction and minimal dramatic stylization."
        ),
    ),
}


LEGACY_VOICE_STYLE_MAP = {
    "narrator-epic": ("narrator-br", "epic"),
    "narrator-mystery": ("narrator-br", "mystery"),
}


def build_instruction(voice_id: str, style_id: str, custom_instruction: str | None = None) -> str:
    voice = VOICE_PROFILES[voice_id]
    style = STYLE_PROFILES[style_id]

    parts = [voice.instruction, style.instruction]

    if custom_instruction and custom_instruction.strip():
        parts.append(custom_instruction.strip())

    return " ".join(parts)
