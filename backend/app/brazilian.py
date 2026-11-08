"""Brazilian-only Chatterbox checkpoint with the pinned official demo loader."""
import importlib.util
import logging
import os
import sys
from io import BytesIO
from pathlib import Path
from threading import Lock

import numpy as np
import soundfile as sf

from .tts import split_text

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / 'models/chatterbox-ptbr'
SOURCE_DIR = ROOT / 'models/chatterbox-br-source/chatterbox/src/chatterbox'
REFERENCE_DIR = ROOT / 'voices/references'
logger = logging.getLogger('uvicorn.error')


class SpeechCancelled(Exception):
    pass


def voice_catalog():
    voices = [{'id': 'narrator-br', 'name': 'Brasileira · demonstração', 'locale': 'pt-BR',
               'description': 'Voz feminina da demonstração oficial brasileira.'}]
    for path in sorted(REFERENCE_DIR.glob('*.json')):
        import json
        try:
            item = json.loads(path.read_text())
            if (REFERENCE_DIR / f'{path.stem}.wav').is_file():
                voices.append({'id': path.stem, 'name': str(item['name']), 'locale': 'pt-BR',
                               'description': 'Sua gravação de referência.'})
        except (OSError, ValueError, KeyError):
            logger.warning('Perfil de referência inválido: %s', path.name)
    return voices


def reference_path(voice):
    if voice == 'narrator-br':
        return MODEL_DIR / 'pt_br_f2.wav'
    # Resolve only previously registered voice IDs, never an arbitrary client path.
    if voice not in {item['id'] for item in voice_catalog()}:
        raise ValueError('Voz não encontrada.')
    return REFERENCE_DIR / f'{voice}.wav'


class BrazilianEngine:
    def __init__(self):
        self._model = None
        self._lock = Lock()

    def _load(self):
        if self._model is not None:
            return self._model
        if not (MODEL_DIR / 't3_pt_br.safetensors').exists() or not (SOURCE_DIR / '__init__.py').exists():
            raise RuntimeError('Modelo brasileiro não instalado. Execute bash scripts/setup-br.sh.')
        os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
        import torch
        from .config import get_settings
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        device = get_settings().device
        if device == 'auto':
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        package_name = 'voxarcana_chatterbox_br'
        if package_name not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                package_name, SOURCE_DIR / '__init__.py',
                submodule_search_locations=[str(SOURCE_DIR)])
            package = importlib.util.module_from_spec(spec)
            sys.modules[package_name] = package
            try:
                spec.loader.exec_module(package)
            except Exception:
                for name in list(sys.modules):
                    if name == package_name or name.startswith(package_name + '.'):
                        sys.modules.pop(name, None)
                raise
        cls = sys.modules[package_name].ChatterboxTTS
        # CPU loading avoids a second full checkpoint allocation on the GPU.
        model = cls.from_local(MODEL_DIR, 'cpu')
        model.to(device)
        logger.info('Chatterbox PT-BR carregado em %s.', device)
        self._model = model
        return model

    def synthesize(self, text, instruction='', voice='narrator-br', style='neutral',
                   progress=None, cancelled=None):
        # Chatterbox uses reference audio, not prose describing the voice.
        if instruction and instruction.strip():
            raise ValueError('Este modelo usa gravação de referência para definir a voz. '
                             'Limpe a descrição textual de voz ou use o estúdio em uma aba.')
        with self._lock:
            model = self._load()
            reference = reference_path(voice)
            if not reference.exists():
                raise ValueError('Gravação de referência não encontrada. Reinstale o modelo brasileiro.')
            from .config import get_settings
            chunks = split_text(text, min(get_settings().chunk_chars, 280))
            if not chunks:
                raise ValueError('Digite um texto para narrar.')
            # Conservative controls; these are delivery presets, not voice design.
            expression = {'epic': 0.65, 'terror': 0.4, 'action': 0.65, 'suspense': 0.45,
                          'mystery': 0.45, 'calm': 0.35, 'noir': 0.4,
                          'storyteller': 0.55, 'documentary': 0.4, 'neutral': 0.45}[style]
            parts = []
            for index, chunk in enumerate(chunks):
                if cancelled and cancelled():
                    raise SpeechCancelled()
                if progress:
                    progress(index, len(chunks))
                wav = model.generate(chunk, language_id='pt',
                                     audio_prompt_path=str(reference) if index == 0 else None,
                                     exaggeration=expression, cfg_weight=0.5, temperature=0.65)
                if cancelled and cancelled():
                    raise SpeechCancelled()
                if index:
                    parts.append(np.zeros(int(model.sr * 0.15), dtype=np.float32))
                parts.append(wav.squeeze(0).detach().cpu().numpy())
            if progress:
                progress(len(chunks), len(chunks))
            output = BytesIO()
            sf.write(output, np.concatenate(parts), model.sr, format='WAV')
            return output.getvalue()
