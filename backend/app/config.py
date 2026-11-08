from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    engine: Literal["qwen", "chatterbox-br"] = "qwen"
    host: str = "127.0.0.1"
    port: int = 8765
    model: str = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    device: str = "auto"
    dtype: str = "auto"
    attn: str = "sdpa"
    # Keep waveform decoding off small GPUs; the language model stays accelerated.
    decoder_device: str = "auto"
    chunk_chars: int = Field(default=350, ge=100, le=2000)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VOXARCANA_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
