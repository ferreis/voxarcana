import json
import logging
from pathlib import Path
from io import BytesIO
from uuid import uuid4

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .config import get_settings
from .styles import LEGACY_VOICE_STYLE_MAP, STYLE_PROFILES, build_instruction
from .tts import get_engine
from .voices import VOICE_PROFILES
from .brazilian import voice_catalog, REFERENCE_DIR, MODEL_DIR
from .jobs import queue

app = FastAPI(title='VoxArcana Studio', version='0.4.0', description='Narração local em PT-BR.')
LOCAL_ORIGINS = ['http://127.0.0.1:8765', 'http://localhost:8765',
                 'http://127.0.0.1:5173', 'http://localhost:5173']
app.add_middleware(CORSMiddleware, allow_origins=LOCAL_ORIGINS,
                   allow_origin_regex=r'chrome-extension://[a-p]{32}',
                   allow_credentials=False, allow_methods=['GET', 'POST', 'DELETE'],
                   allow_headers=['Content-Type'])


@app.middleware('http')
async def local_origin(request, call_next):
    import re
    origin = request.headers.get('origin')
    if request.method in {'POST', 'DELETE'} and origin and origin not in LOCAL_ORIGINS:
        if not re.fullmatch(r'chrome-extension://[a-p]{32}', origin):
            return Response(status_code=403, content='Origem não autorizada.')
    return await call_next(request)


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    voice: str = 'narrator-br'
    style: str = 'neutral'
    instruction: str | None = Field(default=None, max_length=2_000)

    @field_validator('text')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Digite um texto para narrar.')
        return value.strip()


def validate_profile(request):
    voice, style = request.voice, request.style
    if voice in LEGACY_VOICE_STYLE_MAP:
        voice, style = LEGACY_VOICE_STYLE_MAP[voice]
    catalog = voice_catalog() if get_settings().engine == 'chatterbox-br' else [
        {'id': item.id} for item in VOICE_PROFILES.values()]
    if voice not in {item['id'] for item in catalog}:
        raise HTTPException(404, 'Voz não encontrada.')
    if style not in STYLE_PROFILES:
        raise HTTPException(404, 'Estilo não encontrado.')
    if get_settings().engine == 'chatterbox-br' and request.instruction and request.instruction.strip():
        raise HTTPException(422, 'Este modelo usa gravação de referência. Limpe a descrição textual da voz e use o estúdio.')
    return voice, style


@app.get('/health')
def health():
    return {'status': 'ok', 'engine': get_settings().engine}


@app.get('/v1/engine')
def engine_info():
    brazilian = get_settings().engine == 'chatterbox-br'
    return {'id': get_settings().engine,
            'name': 'Chatterbox · Português brasileiro' if brazilian else 'Qwen · Multilíngue',
            'locale': 'pt-BR' if brazilian else 'pt', 'reference_audio': brazilian,
            'voice_description': not brazilian,
            'installed': (MODEL_DIR / 't3_pt_br.safetensors').is_file() if brazilian else True}


@app.get('/v1/voices')
def voices():
    if get_settings().engine == 'chatterbox-br':
        return voice_catalog()
    return [{'id': voice.id, 'name': voice.name} for voice in VOICE_PROFILES.values()]


@app.get('/v1/styles')
def styles():
    return [{'id': style.id, 'name': style.name} for style in STYLE_PROFILES.values()]


@app.post('/v1/voices/reference')
def add_reference(audio: UploadFile = File(...), name: str = Form(min_length=1, max_length=60)):
    if get_settings().engine != 'chatterbox-br':
        raise HTTPException(409, 'Inicie o motor brasileiro para adicionar uma voz de referência.')
    data = audio.file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, 'Use uma gravação de até 10 MB.')
    try:
        info = sf.info(BytesIO(data))
        if not 3 <= info.duration <= 30 or not 8000 <= info.samplerate <= 96000:
            raise ValueError('Use uma gravação de 3 a 30 segundos.')
        samples, rate = sf.read(BytesIO(data), dtype='float32', always_2d=True)
        samples = samples.mean(axis=1)
        if not np.isfinite(samples).all() or np.abs(samples).max() < 0.001:
            raise ValueError('A gravação está vazia ou não contém áudio audível.')
    except (RuntimeError, ValueError, sf.LibsndfileError) as error:
        raise HTTPException(422, str(error) if isinstance(error, ValueError) else
                            'Não consegui abrir o áudio. Use WAV ou FLAC.') from error
    if not name.strip():
        raise HTTPException(422, 'Dê um nome à voz.')
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    voice_id = str(uuid4())
    sf.write(REFERENCE_DIR / f'{voice_id}.wav', samples, rate, subtype='PCM_16')
    (REFERENCE_DIR / f'{voice_id}.json').write_text(json.dumps({'name': name.strip()}, ensure_ascii=False))
    return {'id': voice_id, 'name': name.strip(), 'locale': 'pt-BR',
            'description': 'Sua gravação de referência.'}


@app.post('/v1/speech')
def speech(request: SpeechRequest):
    voice, style = validate_profile(request)
    try:
        if get_settings().engine == 'chatterbox-br':
            audio = get_engine().synthesize(text=request.text, voice=voice, style=style)
        else:
            audio = get_engine().synthesize(text=request.text, instruction=build_instruction(
                voice_id=voice, style_id=style, custom_instruction=request.instruction))
    except Exception as error:
        logging.getLogger(__name__).exception('Falha ao gerar áudio TTS')
        raise HTTPException(500, f'Não foi possível gerar a narração: {error}') from error
    return Response(content=audio, media_type='audio/wav', headers={'Cache-Control': 'no-store'})


@app.post('/v1/jobs', status_code=202)
def create_job(request: SpeechRequest):
    if get_settings().engine != 'chatterbox-br':
        raise HTTPException(409, 'Inicie o estúdio com bash scripts/start-studio.sh para usar o modelo brasileiro.')
    voice, style = validate_profile(request)
    try:
        job = queue.submit({'text': request.text, 'voice': voice, 'style': style})
    except ValueError as error:
        raise HTTPException(429, str(error)) from error
    return {'id': job.id}


@app.get('/v1/jobs/{job_id}')
def job_status(job_id: str):
    job = queue.snapshot(job_id)
    if job is None:
        raise HTTPException(404, 'Narração não encontrada. O servidor pode ter sido reiniciado.')
    return job


@app.delete('/v1/jobs/{job_id}')
def cancel_job(job_id: str):
    job = queue.cancel_job(job_id)
    if job is None:
        raise HTTPException(404, 'Narração não encontrada.')
    return job


@app.get('/v1/jobs/{job_id}/audio')
def job_audio(job_id: str):
    with queue.lock:
        job = queue.jobs.get(job_id)
        if job is None:
            raise HTTPException(404, 'Áudio não encontrado.')
        if job.status != 'done':
            raise HTTPException(409, 'O áudio ainda não está pronto.')
        audio = job.audio
    return Response(content=audio, media_type='audio/wav',
                    headers={'Cache-Control': 'no-store', 'Content-Disposition': 'attachment; filename="voxarcana.wav"'})


DIST = Path(__file__).resolve().parents[2] / 'frontend/dist'
app.mount('/assets', StaticFiles(directory=DIST / 'assets', check_dir=False), name='assets')


@app.get('/', include_in_schema=False)
def studio():
    if not (DIST / 'index.html').is_file():
        raise HTTPException(503, 'Prepare a interface: npm --prefix frontend ci && npm --prefix frontend run build')
    return FileResponse(DIST / 'index.html', headers={'Cache-Control': 'no-cache'})
