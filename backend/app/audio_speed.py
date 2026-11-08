"""Apply an explicit export tempo to the completed WAV, preserving pitch."""
from io import BytesIO
import soundfile as sf
import math
import shutil
import subprocess


def change_speed(wav: bytes, speed: float = 1.0) -> bytes:
    if not math.isfinite(speed) or not .5 <= speed <= 2:
        raise ValueError('A velocidade de geração deve estar entre 0,5× e 2×.')
    if speed == 1:
        return wav
    executable = shutil.which('ffmpeg')
    if not executable:
        raise RuntimeError('Instale o FFmpeg para ajustar a velocidade do WAV.')
    try:
        result = subprocess.run([executable, '-nostdin', '-hide_banner', '-loglevel', 'error',
                                 '-i', 'pipe:0', '-af', f'atempo={speed:.6f}',
                                 '-c:a', 'pcm_s16le', '-f', 'wav', 'pipe:1'],
                                input=wav, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise RuntimeError('Não consegui aplicar a velocidade ao áudio. Tente gerar novamente.') from error
    # A seekable WAV header gives browsers the correct duration and seeking range.
    samples, rate = sf.read(BytesIO(result.stdout), dtype='int16', always_2d=True)
    output = BytesIO()
    sf.write(output, samples, rate, format='WAV', subtype='PCM_16')
    return output.getvalue()
