from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    host: str = "127.0.0.1"
    port: int = 8765
    model: str = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
    device: str = "auto"
    dtype: str = "auto"
    attn: str = "sdpa"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="VOXARCANA_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
