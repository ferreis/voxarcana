from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
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
    reader_model: str = 'qwen3:4b-instruct-2507-q4_K_M'
    reader_url: str = 'http://127.0.0.1:11435'

    @field_validator('reader_url')
    @classmethod
    def local_reader_only(cls, value):
        parsed = urlparse(value)
        if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'}:
            raise ValueError('O analisador deve rodar neste computador.')
        return value.rstrip('/')

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VOXARCANA_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
