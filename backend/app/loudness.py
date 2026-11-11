"""Match generated voices by perceived loudness, without per-emotion gain."""
import json
import math
import shutil
import subprocess

import numpy as np

TARGET_LUFS = -18.0
TRUE_PEAK_DB = -1.5


def normalize_voice(samples, sample_rate):
    audio = np.asarray(samples, dtype=np.float32).reshape(-1)
    if not len(audio):
        return audio.copy()
    if not np.isfinite(audio).all():
        raise ValueError('O modelo gerou áudio inválido. Tente gerar novamente.')
    if np.max(np.abs(audio)) < 1e-7:
        return audio.copy()
    executable = shutil.which('ffmpeg')
    if not executable:
        raise RuntimeError('Instale o FFmpeg para normalizar o volume das vozes.')
    base = [executable, '-nostdin', '-hide_banner', '-loglevel', 'info',
            '-f', 'f32le', '-ar', str(sample_rate), '-ac', '1', '-i', 'pipe:0']
    target = f'loudnorm=I={TARGET_LUFS}:TP={TRUE_PEAK_DB}:LRA=11'
    data = audio.astype('<f4', copy=False).tobytes()
    try:
        measured = subprocess.run([*base, '-af', target + ':print_format=json', '-f', 'null', '-'],
                                  input=data, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                  check=True, timeout=30)
        report = measured.stderr.decode(errors='replace')
        # FFmpeg can append progress/output messages after the JSON report.
        stats = json.JSONDecoder().raw_decode(report[report.rfind('{'):])[0]
        if not math.isfinite(float(stats['input_i'])):
            # LUFS needs an integration window; very short words may lack one.
            active = np.abs(audio) >= np.max(np.abs(audio)) * .03
            rms = float(np.sqrt(np.mean(audio[active].astype(np.float64) ** 2)))
            gain = min(10 ** (TARGET_LUFS / 20) / max(rms, 1e-12),
                       10 ** (TRUE_PEAK_DB / 20) / float(np.max(np.abs(audio))))
            return (audio * gain).astype(np.float32)
        correction = (f":measured_I={stats['input_i']}:measured_TP={stats['input_tp']}"
                      f":measured_LRA={stats['input_lra']}:measured_thresh={stats['input_thresh']}"
                      f":offset={stats['target_offset']}:linear=true")
        result = subprocess.run([*base, '-af', target + correction,
                                 '-ar', str(sample_rate), '-ac', '1', '-f', 'f32le', 'pipe:1'],
                                input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                check=True, timeout=30)
        normalized = np.frombuffer(result.stdout, dtype='<f4').copy()
    except (subprocess.SubprocessError, ValueError, KeyError) as error:
        raise RuntimeError('Não consegui normalizar o volume da voz. Tente gerar novamente.') from error
    if len(normalized) != len(audio):
        raise RuntimeError('A normalização alterou a duração do trecho.')
    if not np.isfinite(normalized).all():
        raise RuntimeError('A normalização retornou áudio inválido.')
    return np.clip(normalized, -.98, .98)
