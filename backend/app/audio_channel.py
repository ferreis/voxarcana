"""Filter speech that the scene explicitly identifies as a transmission."""
import shutil
import subprocess
import numpy as np


def apply_channel(samples, sample_rate, channel):
    if channel == 'none':
        return samples
    filters = {'radio': 'highpass=f=350,lowpass=f=3100',
               'television': 'highpass=f=180,lowpass=f=6000'}
    if channel not in filters:
        raise ValueError('Efeito de transmissão desconhecido.')
    executable = shutil.which('ffmpeg')
    if not executable:
        raise RuntimeError('Instale o FFmpeg para aplicar efeitos de transmissão.')
    audio = np.asarray(samples, dtype='<f4').reshape(-1)
    try:
        result = subprocess.run([executable, '-nostdin', '-hide_banner', '-loglevel', 'error',
                                 '-f', 'f32le', '-ar', str(sample_rate), '-ac', '1', '-i', 'pipe:0',
                                 '-af', filters[channel], '-f', 'f32le', 'pipe:1'],
                                input=audio.tobytes(), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=True, timeout=30)
    except (subprocess.SubprocessError, OSError) as error:
        raise RuntimeError('Não consegui aplicar o efeito de transmissão.') from error
    filtered = np.frombuffer(result.stdout, dtype='<f4').copy()
    if len(filtered) != len(audio) or not np.isfinite(filtered).all():
        raise RuntimeError('O efeito de transmissão retornou áudio inválido.')
    return filtered
