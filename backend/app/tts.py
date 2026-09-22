from functools import lru_cache
from io import BytesIO

import soundfile as sf

from .config import get_settings
from .voices import VoiceProfile


def _resolve_torch_dtype(name: str):
    import torch

    values = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }
    try:
        return values[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported dtype: {name}") from exc


class QwenVoiceDesignEngine:
    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model

        from qwen_tts import Qwen3TTSModel

        settings = get_settings()
        kwargs = {
            "device_map": settings.device,
            "dtype": _resolve_torch_dtype(settings.dtype),
        }
        if settings.attn:
            kwargs["attn_implementation"] = settings.attn

        self._model = Qwen3TTSModel.from_pretrained(settings.model, **kwargs)
        return self._model

    def synthesize(self, text: str, profile: VoiceProfile, instruction: str | None = None) -> bytes:
        model = self._load()
        prompt = instruction.strip() if instruction and instruction.strip() else profile.instruction

        wavs, sample_rate = model.generate_voice_design(
            text=text,
            language="Portuguese",
            instruct=prompt,
        )

        output = BytesIO()
        sf.write(output, wavs[0], sample_rate, format="WAV")
        return output.getvalue()


@lru_cache
def get_engine() -> QwenVoiceDesignEngine:
    return QwenVoiceDesignEngine()
