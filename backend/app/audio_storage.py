"""Save completed narrations independently of the server working directory."""
from pathlib import Path
from uuid import uuid4

DATA_DIR = Path(__file__).resolve().parents[2] / 'Data'


def save_generated_audio(audio: bytes) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = DATA_DIR / f'{uuid4()}.wav'
    temporary_path = audio_path.with_suffix('.tmp')
    try:
        temporary_path.write_bytes(audio)
        temporary_path.replace(audio_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return audio_path
