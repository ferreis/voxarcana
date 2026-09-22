from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .tts import get_engine
from .voices import VOICE_PROFILES

app = FastAPI(
    title="VoxArcana Local API",
    version="0.1.0",
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
    voice: str = "narrator-epic"
    instruction: str | None = Field(default=None, max_length=2_000)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/v1/voices")
def voices():
    return [
        {"id": voice.id, "name": voice.name}
        for voice in VOICE_PROFILES.values()
    ]


@app.post("/v1/speech")
def speech(request: SpeechRequest):
    profile = VOICE_PROFILES.get(request.voice)
    if profile is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    try:
        audio = get_engine().synthesize(
            text=request.text,
            profile=profile,
            instruction=request.instruction,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"TTS generation failed: {exc}") from exc

    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store"},
    )
