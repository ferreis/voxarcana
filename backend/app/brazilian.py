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
from .audio_speed import change_speed
from .loudness import normalize_voice

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / 'models/chatterbox-ptbr'
SOURCE_DIR = ROOT / 'models/chatterbox-br-source/chatterbox/src/chatterbox'
REFERENCE_DIR = ROOT / 'voices/references'
logger = logging.getLogger('uvicorn.error')


class SpeechCancelled(Exception):
    pass


def voice_catalog():
    voices = []
    for path in sorted(REFERENCE_DIR.glob('*.json')):
        import json
        try:
            item = json.loads(path.read_text())
            if (REFERENCE_DIR / f'{path.stem}.wav').is_file():
                voices.append({'id': path.stem, 'name': str(item['name']), 'locale': 'pt-BR',
                               'description': 'Sua gravação de referência.', 'editable': True,
                               **{key: item.get(key, default) for key, default in
                                  [('role', 'both'), ('gender', 'unknown'), ('kind', 'human')]}})
        except (OSError, ValueError, KeyError):
            logger.warning('Perfil de referência inválido: %s', path.name)
    return voices


def reference_path(voice):
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

    def synthesize(self, text, instruction='', voice='', style='neutral',
                   progress=None, cancelled=None, automatic=False, scene=None,
                   on_scene=None, on_unit=None, on_stage=None, on_analysis=None, speed=1.0):
        # Chatterbox uses reference audio, not prose describing the voice.
        if instruction and instruction.strip():
            raise ValueError('Este modelo usa gravação de referência para definir a voz. '
                             'Limpe a descrição textual de voz ou use o estúdio em uma aba.')
        if automatic:
            from .scene import get_reader
            from .cast import build_units
            if on_stage:
                on_stage('analyzing')
            scene = scene or get_reader().analyze(text, cancelled, on_progress=on_analysis)
            if cancelled and cancelled():
                raise SpeechCancelled()
            units = build_units(scene, voice, style=style)
            if on_scene:
                on_scene(scene.public())
        else:
            units = None
        with self._lock:
            if on_stage:
                on_stage('loading')
            model = self._load()
            if units is not None:
                output = self._perform(model, units, progress, cancelled, on_unit, on_stage)
                if cancelled and cancelled():
                    raise SpeechCancelled()
                return change_speed(output, speed)
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
                parts.append(normalize_voice(wav.squeeze(0).detach().cpu().numpy(), model.sr))
            if progress:
                progress(len(chunks), len(chunks))
            output = BytesIO()
            sf.write(output, np.concatenate(parts), model.sr, format='WAV')
            if on_stage:
                on_stage('assembling')
            return change_speed(output.getvalue(), speed)

    def _perform(self, model, units, progress, cancelled, on_unit, on_stage):
        import copy
        import torch
        if not units:
            raise ValueError('Digite um texto para narrar.')
        parts = []
        conditions = {}
        active_voice = None
        if on_stage:
            on_stage('synthesizing')
        for index, unit in enumerate(units):
            if cancelled and cancelled():
                raise SpeechCancelled()
            if progress:
                progress(index, len(units))
            if on_unit:
                on_unit(unit.speaker, unit.delivery)
            reference = reference_path(unit.voice)
            if not reference.is_file():
                raise ValueError('A referência de voz não foi encontrada.')
            prompt = None
            if active_voice != unit.voice:
                if unit.voice in conditions:
                    # Store conditioning on CPU; keep only the active voice on
                    # GPU so a larger cast does not exhaust a 6 GB card.
                    model.conds = copy.deepcopy(conditions[unit.voice]).to(model.device)
                else:
                    prompt = str(reference)
                active_voice = unit.voice
            torch.manual_seed(unit.seed)
            with torch.inference_mode():
                wav = model.generate(unit.text, language_id='pt', audio_prompt_path=prompt,
                                     exaggeration=unit.expression, cfg_weight=.5, temperature=.65)
                if prompt:
                    conditions[unit.voice] = copy.deepcopy(model.conds).to('cpu')
            if cancelled and cancelled():
                raise SpeechCancelled()
            audio = wav.squeeze(0).detach().cpu().numpy()
            # Keep model output at its native pace and pitch. Phase-vocoder
            # stretching can make speech sound doubled or metallic.
            audio = normalize_voice(audio, model.sr)
            # Fade only the outer 5 ms to prevent clicks at voice switches.
            fade = min(int(model.sr * .005), len(audio) // 2)
            if fade:
                audio[:fade] *= np.linspace(0, 1, fade)
                audio[-fade:] *= np.linspace(1, 0, fade)
            if index:
                parts.append(np.zeros(int(model.sr * units[index - 1].pause), dtype=np.float32))
            parts.append(audio)
        if progress:
            progress(len(units), len(units))
        if on_stage:
            on_stage('assembling')
        output = BytesIO()
        sf.write(output, np.concatenate(parts), model.sr, format='WAV')
        return output.getvalue()
