from dataclasses import dataclass


BRAZILIAN_PORTUGUESE_RULES = (
    "Speak exclusively in natural Brazilian Portuguese with a neutral contemporary Brazilian accent. "
    "Keep Brazilian Portuguese pronunciation and phonology consistent from beginning to end. "
    "Do not use European Portuguese pronunciation, vowel reduction, rhythm, intonation or consonant patterns. "
    "Pronounce words naturally as a native Brazilian speaker would. "
)


@dataclass(frozen=True)
class VoiceProfile:
    id: str
    name: str
    instruction: str


VOICE_PROFILES = {
    "narrator-br": VoiceProfile(
        id="narrator-br",
        name="Narrador BR",
        instruction=(
            "Adult Brazilian male narrator with a deep, warm and resonant voice. "
            "Clear diction, natural delivery and an immersive storytelling presence. "
            + BRAZILIAN_PORTUGUESE_RULES
        ),
    ),
}
