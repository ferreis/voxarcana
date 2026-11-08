import logging
import os
import re
import textwrap
from functools import lru_cache
from io import BytesIO
from threading import Lock

import numpy as np
import soundfile as sf

from .config import get_settings

logger = logging.getLogger(__name__)


def split_text(text: str, limit: int) -> list[str]:
    """Bound generation/decoding memory, preferring sentence and word boundaries."""
    chunks = []
    current = ""
    for sentence in re.split(r"(?<=[.!?;:])\s+|\n+", text.strip()):
        for part in textwrap.wrap(sentence, width=limit, break_on_hyphens=False):
            if current and len(current) + len(part) + 1 > limit:
                chunks.append(current)
                current = ""
            current = f"{current} {part}".strip()
    if current:
        chunks.append(current)
    return chunks

def _resolve_runtime(device_name: str, dtype_name: str):
    import torch

    if device_name == "auto":
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    else:
        device = device_name

    if dtype_name == "auto":
        if device.startswith("cuda"):
            with torch.cuda.device(device):
                dtype = (
                    torch.bfloat16
                    if torch.cuda.is_bf16_supported(including_emulation=False)
                    else torch.float16
                )
        else:
            dtype = torch.float32
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
        self._lock = Lock()

    def _load(self):
        if self._model is not None:
            return self._model

        os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
        os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

        from qwen_tts import Qwen3TTSModel

        settings = get_settings()
        device, dtype = _resolve_runtime(settings.device, settings.dtype)

        kwargs = {
            "device_map": device,
            "dtype": dtype,
        }
        if settings.attn:
            kwargs["attn_implementation"] = settings.attn

        model = Qwen3TTSModel.from_pretrained(settings.model, **kwargs)
        decoder_device = settings.decoder_device
        if decoder_device == "auto":
            import torch

            small_gpu = device.startswith("cuda") and (
                torch.cuda.get_device_properties(device).total_memory <= 8 * 1024**3
            )
            decoder_device = "cpu" if small_gpu else device
        if decoder_device != device:
            import torch

            tokenizer = model.model.speech_tokenizer
            tokenizer.model.to(device=decoder_device,
                               dtype=torch.float32 if decoder_device == "cpu" else dtype)
            # The wrapper caches the device separately from its torch module.
            tokenizer.device = torch.device(decoder_device)
            if device.startswith("cuda"):
                torch.cuda.empty_cache()
        logger.info("VoxArcana: model=%s, dtype=%s, decoder=%s", device, dtype, decoder_device)
        self._model = model
        return self._model

    def synthesize(self, text: str, instruction: str) -> bytes:
        # FastAPI executes sync routes on multiple threads. Only one generation
        # may use this model/GPU at a time, including its first load.
        with self._lock:
            return self._synthesize(text, instruction)

    def _synthesize(self, text: str, instruction: str) -> bytes:
        model = self._load()
        chunks = split_text(text, get_settings().chunk_chars)
        if not chunks:
            raise ValueError("O texto deve conter palavras para narrar.")
        audio_parts = []
        output_rate = None
        for chunk in chunks:
            wavs, sample_rate = model.generate_voice_design(
                text=chunk,
                language="Portuguese",
                instruct=instruction,
            )
            if output_rate is not None:
                if output_rate != sample_rate:
                    raise ValueError("O modelo retornou taxas de áudio diferentes entre trechos.")
                audio_parts.append(np.zeros(int(sample_rate * 0.15), dtype=np.float32))
            audio_parts.append(wavs[0])
            output_rate = sample_rate

        output = BytesIO()
        sf.write(output, np.concatenate(audio_parts), output_rate, format="WAV")
        return output.getvalue()


@lru_cache
def get_engine():
    if get_settings().engine == "chatterbox-br":
        from .brazilian import BrazilianEngine

        return BrazilianEngine()
    return QwenVoiceDesignEngine()
