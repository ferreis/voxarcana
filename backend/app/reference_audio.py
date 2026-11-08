"""Decode uploaded media locally into a bounded, mono PCM reference."""
from io import BytesIO
from pathlib import Path
import json
import shutil
import subprocess
from tempfile import TemporaryDirectory

import numpy as np
import soundfile as sf

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def normalize_reference(data: bytes) -> bytes:
    executable = shutil.which('ffmpeg')
    probe = shutil.which('ffprobe')
    if not executable or not probe:
        raise RuntimeError('Instale o FFmpeg para importar gravações MP3, M4A, MP4, WAV ou FLAC.')
    with TemporaryDirectory(prefix='voxarcana-reference-') as directory:
        source = Path(directory) / 'input.media'
        output = Path(directory) / 'reference.wav'
        source.write_bytes(data)
        try:
            metadata = subprocess.run([probe, '-v', 'error', '-protocol_whitelist', 'file,pipe',
                                       '-select_streams', 'a:0', '-show_entries', 'stream=duration',
                                       '-of', 'json', str(source)], check=True, timeout=10,
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            streams = json.loads(metadata.stdout).get('streams', [])
            if not streams:
                raise ValueError('Não consegui extrair áudio: o arquivo não contém uma faixa de áudio.')
            duration = streams[0].get('duration')
            duration = float(duration) if duration not in {None, 'N/A'} else None
            if duration is not None and duration > 51:
                raise ValueError('Use uma gravação de 3 a 50 segundos; arquivos maiores não são cortados automaticamente.')
            subprocess.run([executable, '-nostdin', '-hide_banner', '-loglevel', 'error',
                            '-protocol_whitelist', 'file,pipe', '-i', str(source),
                            '-map', '0:a:0', '-vn', '-t', str(duration) if duration is not None and 3 <= duration <= 50 else '51', '-ac', '1', '-ar', '24000',
                            '-c:a', 'pcm_s16le', '-y', str(output)],
                           check=True, timeout=30, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
            wav = output.read_bytes()
        except subprocess.TimeoutExpired as error:
            raise ValueError('A conversão demorou demais. Tente outro arquivo de até 50 segundos.') from error
        except (subprocess.CalledProcessError, OSError) as error:
            raise ValueError('Não consegui extrair áudio desse arquivo. Use MP3, M4A, MP4 com faixa de áudio, WAV ou FLAC.') from error
    info = sf.info(BytesIO(wav))
    if not 3 <= info.duration <= 50:
        raise ValueError('Use uma gravação de 3 a 50 segundos; arquivos maiores não são cortados automaticamente.')
    samples, _ = sf.read(BytesIO(wav), dtype='float32')
    if not np.isfinite(samples).all() or np.abs(samples).max() < .001:
        raise ValueError('A gravação está vazia ou não contém áudio audível.')
    return wav
