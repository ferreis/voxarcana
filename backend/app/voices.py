from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceProfile:
    id: str
    name: str
    instruction: str


VOICE_PROFILES = {
    "narrator-epic": VoiceProfile(
        id="narrator-epic",
        name="Narrador de Fantasia Épica",
        instruction=(
            "Adult male narrator with a deep, warm and resonant voice. "
            "Epic dark-fantasy storyteller, cinematic and serious. "
            "Clear Brazilian Portuguese diction. Slow, deliberate rhythm, "
            "natural dramatic pauses, controlled intensity, no commercial-announcer style."
        ),
    ),
    "narrator-mystery": VoiceProfile(
        id="narrator-mystery",
        name="Narrador de Mistério",
        instruction=(
            "Adult narrator with a low, intimate and mysterious voice. "
            "Brazilian Portuguese, restrained suspense, careful pacing and subtle tension."
        ),
    ),
}
