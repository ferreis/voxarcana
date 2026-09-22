import os
from functools import lru_cache
from io import BytesIO

import soundfile as sf

from .config import get_settings
from .voices import VoiceProfile


def _resolve_runtime(device_name: str, dtype_name: str):
    import torch

    if device_name == "auto":
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    else:
        device = device_name

    if dtype_name == "auto":
        dtype = torch.bfloat16 if device.startswith("cuda") else torch.float32
    else:
        values = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        try:
            dtype = values[dtype_name]
        except KeyError as exc:
            raise ValueError(f"Unsupported dtype: {dtype_name}") from exc

    return device, dtype


class QwenVoiceDesignEngine:
    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is not None:
            return self._model

        # O modelo padrão do VoxArcana é público. Evita que um token
        # Hugging Face inválido salvo no ambiente quebre downloads públicos.
        os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

        from qwen_tts import Qwen3TTSModel

        settings = get_settings()
        device, dtype = _resolve_runtime(settings.device, settings.dtype)

        kwargs = {
            "device_map": device,
            "dtype": dtype,
        }
        if settings.attn:
            kwargs["attn_implementation"] = settings.attn

        self._model = Qwen3TTSModel.from_pretrained(settings.model, **kwargs)
        return self._model

    def synthesize(
        self,
        text: str,
        profile: VoiceProfile,
        instruction: str | None = None,
    ) -> bytes:
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
