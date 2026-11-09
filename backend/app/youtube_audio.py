"""Extract a fixed audio reference from a canonical YouTube video URL."""
from importlib.util import find_spec
from io import BytesIO
from pathlib import Path
import logging
import math
import os
import re
import shutil
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from urllib.parse import parse_qs, urlsplit

import soundfile as sf

from .reference_audio import MAX_UPLOAD_BYTES, normalize_reference

CLIP_SECONDS = 30
DOWNLOAD_TIMEOUT = 120
download_slot = BoundedSemaphore(1)
logger = logging.getLogger(__name__)


class ExtractionBusy(RuntimeError):
    pass


def canonical_video_url(url: str) -> str:
    try:
        parsed = urlsplit(url.strip())
        if (parsed.scheme not in {'http', 'https'} or parsed.username or parsed.password
                or parsed.port is not None):
            raise ValueError()
        if parsed.hostname == 'youtu.be':
            video_id = parsed.path.removeprefix('/')
        elif parsed.hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'}:
            if parsed.path == '/watch':
                video_id = parse_qs(parsed.query).get('v', [''])[0]
            else:
                match = re.fullmatch(r'/(?:shorts|embed|live)/([A-Za-z0-9_-]{11})/?', parsed.path)
                video_id = match.group(1) if match else ''
        else:
            raise ValueError()
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
            raise ValueError()
    except ValueError as error:
        raise ValueError('Cole um link válido de vídeo do YouTube, Shorts ou youtu.be.') from error
    # Discard playlist, redirect and unrelated parameters supplied by the caller.
    return f'https://www.youtube.com/watch?v={video_id}'


def extract_youtube_audio(url: str, start_seconds: float) -> bytes:
    canonical_url = canonical_video_url(url)
    if not math.isfinite(start_seconds) or not 0 <= start_seconds <= 86400:
        raise ValueError('Informe um início entre 0 e 86.400 segundos.')
    if find_spec('yt_dlp') is None:
        raise RuntimeError('Reinicie com ./start para instalar o extrator de áudio do YouTube.')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('Instale o FFmpeg para extrair o áudio do YouTube.')
    if not download_slot.acquire(blocking=False):
        raise ExtractionBusy('Já há uma extração em andamento. Aguarde e tente novamente.')
    try:
        with TemporaryDirectory(prefix='voxarcana-youtube-') as directory:
            output = Path(directory) / 'clip.wav'
            command = [sys.executable, '-m', 'yt_dlp', '--ignore-config', '--no-plugin-dirs',
                       '--no-playlist', '--no-progress', '--no-warnings', '--no-cache-dir',
                       '--socket-timeout', '15', '--retries', '1', '--fragment-retries', '1',
                       '--js-runtimes', 'node', '--match-filters', '!is_live & !is_upcoming',
                       '--format', 'bestaudio', '--download-sections',
                       f'*{start_seconds:.3f}-{start_seconds + CLIP_SECONDS:.3f}',
                       '--extract-audio', '--audio-format', 'wav',
                       '--postprocessor-args', 'ExtractAudio+ffmpeg_o:-t 30 -ar 24000 -ac 1',
                       '--output', str(Path(directory) / 'clip.%(ext)s'), '--', canonical_url]
            # Terminate FFmpeg as well if the downloader exceeds the time limit.
            with subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                  start_new_session=True) as process:
                try:
                    _, diagnostics = process.communicate(timeout=DOWNLOAD_TIMEOUT)
                except subprocess.TimeoutExpired as error:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.communicate()
                    raise ValueError('A extração demorou demais. Tente novamente ou use outro vídeo.') from error
            if process.returncode:
                logger.warning('Extração do YouTube falhou: %s', diagnostics.decode(errors='replace')[-2000:])
                raise ValueError('Não consegui extrair esse vídeo. Ele pode estar indisponível ou exigir login. '
                                 'Tente outro vídeo público ou importe um arquivo do computador.')
            if not output.is_file():
                raise ValueError('O vídeo não contém um trecho disponível nesse horário. Confira o início.')
            if output.stat().st_size > MAX_UPLOAD_BYTES:
                raise ValueError('O áudio extraído ultrapassou o limite de 50 MB.')
            wav = normalize_reference(output.read_bytes())
            if sf.info(BytesIO(wav)).duration < CLIP_SECONDS - .1:
                raise ValueError('O vídeo termina antes dos 30 segundos selecionados. Escolha um início anterior.')
            return wav
    finally:
        download_slot.release()
