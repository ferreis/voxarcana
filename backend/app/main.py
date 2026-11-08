import json
import logging
from pathlib import Path
from uuid import uuid4, UUID
from typing import Literal

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
from .brazilian import voice_catalog, reference_path, REFERENCE_DIR, MODEL_DIR
from .jobs import queue
from .reference_audio import MAX_UPLOAD_BYTES, normalize_reference

app = FastAPI(title='VoxArcana Studio', version='0.4.0', description='Narração local em PT-BR.')
LOCAL_ORIGINS = ['http://127.0.0.1:8765', 'http://localhost:8765',
                 'http://127.0.0.1:5173', 'http://localhost:5173']
app.add_middleware(CORSMiddleware, allow_origins=LOCAL_ORIGINS,
                   allow_origin_regex=r'chrome-extension://[a-p]{32}',
                   allow_credentials=False, allow_methods=['GET', 'POST', 'DELETE', 'PATCH'],
                   allow_headers=['Content-Type'])


@app.middleware('http')
async def local_origin(request, call_next):
    import re
    origin = request.headers.get('origin')
    if request.method in {'POST', 'DELETE', 'PATCH'} and origin and origin not in LOCAL_ORIGINS:
        if not re.fullmatch(r'chrome-extension://[a-p]{32}', origin):
            return Response(status_code=403, content='Origem não autorizada.')
    return await call_next(request)


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    voice: str = ''
    style: str = 'neutral'
    instruction: str | None = Field(default=None, max_length=2_000)
    automatic: bool = True
    review: bool = False
    speed: float = Field(default=1.0, ge=.5, le=2, allow_inf_nan=False)

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
    if not voice:
        voice = next((item['id'] for item in catalog if item.get('role', 'both') != 'character'), '')
        if not voice:
            raise HTTPException(422, 'Adicione uma voz de narrador à biblioteca antes de gerar.')
    if voice not in {item['id'] for item in catalog}:
        raise HTTPException(404, 'Voz não encontrada.')
    if get_settings().engine == 'chatterbox-br' and next(item for item in catalog if item['id'] == voice).get('role') == 'character':
        raise HTTPException(422, 'Essa voz é exclusiva de personagem. Escolha uma voz de narrador.')
    if style not in STYLE_PROFILES:
        raise HTTPException(404, 'Estilo não encontrado.')
    if get_settings().engine == 'chatterbox-br' and request.instruction and request.instruction.strip():
        raise HTTPException(422, 'Este modelo usa gravação de referência. Limpe a descrição textual da voz e use o estúdio.')
    if get_settings().engine == 'chatterbox-br' and request.automatic and not request.review:
        from .scene import segment_text
        if any(span.kind == 'dialogue' and span.text for span in segment_text(request.text)):
            if not any(item['id'] != voice and item.get('role', 'both') in {'character', 'both'} for item in catalog):
                raise HTTPException(422, 'Adicione ou classifique outra voz como Personagem ou Ambos. A voz selecionada do narrador é exclusiva da narração nesta cena.')
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


class VoiceMetadata(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    role: Literal['narrator', 'character', 'both'] = 'both'
    gender: Literal['male', 'female', 'neutral', 'unknown'] = 'unknown'
    kind: Literal['human', 'robot', 'entity'] = 'human'

    @field_validator('name')
    @classmethod
    def valid_name(cls, value):
        if not value.strip():
            raise ValueError('Dê um nome à voz.')
        return value.strip()


@app.patch('/v1/voices/{voice_id}')
def edit_reference(voice_id: str, metadata: VoiceMetadata):
    if get_settings().engine != 'chatterbox-br':
        raise HTTPException(409, 'Inicie o motor brasileiro.')
    try:
        if str(UUID(voice_id)) != voice_id:
            raise ValueError()
    except ValueError:
        raise HTTPException(404, 'Referência importada não encontrada.')
    path = REFERENCE_DIR / f'{voice_id}.json'
    if not path.is_file() or not path.with_suffix('.wav').is_file():
        raise HTTPException(404, 'Referência importada não encontrada.')
    temporary = path.with_suffix(f'.{uuid4()}.tmp')
    temporary.write_text(json.dumps(metadata.model_dump(by_alias=True), ensure_ascii=False))
    temporary.replace(path)
    return {'id': voice_id, **metadata.model_dump(by_alias=True), 'locale': 'pt-BR',
            'editable': True, 'description': 'Sua gravação de referência.'}


@app.delete('/v1/voices/{voice_id}')
def delete_reference(voice_id: str):
    if get_settings().engine != 'chatterbox-br':
        raise HTTPException(409, 'Inicie o motor brasileiro.')
    try:
        if str(UUID(voice_id)) != voice_id:
            raise ValueError()
    except ValueError:
        raise HTTPException(404, 'Referência importada não encontrada.')
    path = REFERENCE_DIR / f'{voice_id}.json'
    with queue.lock:
        if not path.is_file():
            raise HTTPException(404, 'Voz não encontrada.')
        if any(job.status in {'queued', 'running', 'cancelling'} for job in queue.jobs.values()):
            raise HTTPException(409, 'Aguarde a narração terminar ou cancele antes de excluir uma voz.')
        path.unlink()
        path.with_suffix('.wav').unlink(missing_ok=True)
    return {'id': voice_id, 'deleted': True}


@app.post('/v1/voices/reference')
def add_reference(audio: UploadFile = File(...), name: str = Form(min_length=1, max_length=60),
                  role: Literal['narrator', 'character', 'both'] = Form('both'),
                  gender: Literal['male', 'female', 'neutral', 'unknown'] = Form('unknown'),
                  kind: Literal['human', 'robot', 'entity'] = Form('human')):
    if get_settings().engine != 'chatterbox-br':
        raise HTTPException(409, 'Inicie o motor brasileiro para adicionar uma voz de referência.')
    data = audio.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, 'Use um arquivo de até 50 MB.')
    try:
        wav = normalize_reference(data)
    except RuntimeError as error:
        raise HTTPException(503, str(error)) from error
    except (ValueError, sf.LibsndfileError) as error:
        raise HTTPException(422, str(error)) from error
    if not name.strip():
        raise HTTPException(422, 'Dê um nome à voz.')
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    voice_id = str(uuid4())
    (REFERENCE_DIR / f'{voice_id}.wav').write_bytes(wav)
    (REFERENCE_DIR / f'{voice_id}.json').write_text(json.dumps({'name': name.strip(), 'role': role, 'gender': gender, 'kind': kind}, ensure_ascii=False))
    return {'id': voice_id, 'name': name.strip(), 'locale': 'pt-BR',
            'description': 'Sua gravação de referência.', 'editable': True,
            'role': role, 'gender': gender, 'kind': kind}


@app.get('/v1/voices/{voice_id}/reference')
def reference_audio(voice_id: str):
    if get_settings().engine != 'chatterbox-br':
        raise HTTPException(409, 'O motor ativo não usa referência de voz.')
    try:
        path = reference_path(voice_id)
    except ValueError as error:
        raise HTTPException(404, 'Voz não encontrada.') from error
    if not path.is_file():
        raise HTTPException(404, 'Referência não encontrada.')
    return FileResponse(path, media_type='audio/wav', headers={'Cache-Control': 'no-store'})


@app.post('/v1/speech')
def speech(request: SpeechRequest):
    voice, style = validate_profile(request)
    try:
        if get_settings().engine == 'chatterbox-br':
            audio = get_engine().synthesize(text=request.text, voice=voice, style=style,
                                            automatic=request.automatic, speed=request.speed)
        else:
            audio = get_engine().synthesize(text=request.text, instruction=build_instruction(
                voice_id=voice, style_id=style, custom_instruction=request.instruction))
            from .audio_speed import change_speed
            audio = change_speed(audio, request.speed)
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
        job = queue.submit({'text': request.text, 'voice': voice, 'style': style,
                            'automatic': request.automatic, 'speed': request.speed, **({'review': True} if request.review else {})})
    except ValueError as error:
        raise HTTPException(429, str(error)) from error
    return {'id': job.id}


class CharacterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    gender: Literal['male', 'female', 'neutral', 'unknown'] = 'unknown'
    voice_id: str = Field(min_length=1, max_length=80)

    @field_validator('name')
    @classmethod
    def nonblank_name(cls, value):
        if not value.strip():
            raise ValueError('Dê um nome ao personagem.')
        return value.strip()


@app.get('/v1/characters')
def characters():
    from .characters import list_characters
    return list_characters(voice_catalog())


@app.patch('/v1/characters/{record_id}')
def edit_character(record_id: str, request: CharacterRequest):
    from .characters import update_character
    try:
        return update_character(record_id, request.name, request.gender, request.voice_id, voice_catalog())
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


class ReviewedLine(BaseModel):
    id: int = Field(ge=0)
    speaker: str = Field(min_length=1, max_length=80)
    gender: Literal['male', 'female', 'neutral', 'unknown'] = 'unknown'
    voice_id: str = Field(min_length=1, max_length=80)

    @field_validator('speaker')
    @classmethod
    def nonblank_name(cls, value):
        if not value.strip():
            raise ValueError('Dê um nome ao personagem.')
        return value.strip()


class ReviewRequest(BaseModel):
    speed: float | None = Field(default=None, ge=.5, le=2, allow_inf_nan=False)
    voice: str
    style: str = 'neutral'
    lines: list[ReviewedLine] = Field(max_length=300)


@app.post('/v1/jobs/{job_id}/perform', status_code=202)
def perform_review(job_id: str, request: ReviewRequest):
    if request.style not in STYLE_PROFILES:
        raise HTTPException(422, 'Estilo não encontrado.')
    try:
        job = queue.perform_review(job_id, request.lines, request.voice, request.style, voice_catalog(), speed=request.speed)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
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
