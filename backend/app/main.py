from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .styles import LEGACY_VOICE_STYLE_MAP, STYLE_PROFILES, build_instruction
from .tts import get_engine
from .voices import VOICE_PROFILES

app = FastAPI(
    title="VoxArcana Local API",
    version="0.2.0",
    description="TTS local para narração imersiva de RPG.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    voice: str = "narrator-br"
    style: str = "epic"
    instruction: str | None = Field(default=None, max_length=2_000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/voices")
def voices():
    return [{"id": voice.id, "name": voice.name} for voice in VOICE_PROFILES.values()]


@app.get("/v1/styles")
def styles():
    return [{"id": style.id, "name": style.name} for style in STYLE_PROFILES.values()]


@app.post("/v1/speech")
def speech(request: SpeechRequest):
    voice_id = request.voice
    style_id = request.style

    if voice_id in LEGACY_VOICE_STYLE_MAP:
        voice_id, style_id = LEGACY_VOICE_STYLE_MAP[voice_id]

    if voice_id not in VOICE_PROFILES:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    if style_id not in STYLE_PROFILES:
        raise HTTPException(status_code=404, detail="Style profile not found")

    try:
        instruction = build_instruction(
            voice_id=voice_id,
            style_id=style_id,
            custom_instruction=request.instruction,
        )
        audio = get_engine().synthesize(
            text=request.text,
            instruction=instruction,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {exc}") from exc

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )
