"""Automatic, persistent casting and bounded delivery controls."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from threading import Lock

from .scene import Scene, NARRATOR, identity
from .tts import split_text

CAST_FILE = Path(__file__).resolve().parents[1] / 'voices/cast.json'
_lock = Lock()

# These guide the existing TTS and simple post-processing. They do not simulate
# crying/laughter or promise exact acting from a reference-conditioned model.
DELIVERY = {
    'neutral': (.45, 1.0, 1.0, .18),
    'warm': (.5, .98, 1.0, .20),
    'playful': (.6, 1.03, 1.0, .15),
    'firm': (.55, .97, 1.0, .24),
    'urgent': (.65, 1.07, 1.0, .12),
    'soft': (.35, .95, 1.0, .24),
    'sad': (.4, .94, 1.0, .30),
    'tense': (.45, .96, 1.0, .30),
    'angry': (.65, 1.04, 1.0, .16),
    'fear': (.5, 1.04, 1.0, .16),
}


@dataclass
class Unit:
    text: str
    speaker: str
    voice: str
    gender: str
    delivery: str
    pitch: float
    speed: float
    gain: float
    expression: float
    pause: float
    seed: int
    source_id: int


def _profiles(scene, catalog, narrator_voice):
    """Choose actual references, rechecking eligibility after library edits."""
    with _lock:
        try:
            saved = json.loads(CAST_FILE.read_text())
            if not isinstance(saved, dict):
                saved = {}
        except (OSError, ValueError):
            saved = {}
        result = {}
        for span in scene.spans:
            if span.kind != 'dialogue':
                continue
            key = identity(span.speaker)
            digest = hashlib.sha256(key.encode()).digest()
            old = saved.get(key, {})
            gender = span.gender
            kind = span.voice_kind
            candidates = [v for v in catalog if v['id'] != narrator_voice
                          and v.get('role', 'both') in {'both', 'character'}
                          and v.get('kind', 'human') == kind
                          and (gender == 'unknown' or v.get('gender', 'unknown') == gender)]
            if span.voice_override:
                candidates = [v for v in catalog if v['id'] == span.voice_override and v['id'] != narrator_voice
                              and v.get('role', 'both') in {'both', 'character'}]
            if gender == 'unknown':
                neutral = [v for v in candidates if v.get('gender') in {'neutral', 'unknown'}]
                candidates = neutral or candidates
            if candidates:
                candidates = sorted(candidates, key=lambda v: v['id'])
                eligible = {v['id'] for v in candidates}
                previous = old.get('voice') if isinstance(old, dict) else None
                voice = previous if previous in eligible else candidates[int.from_bytes(digest[:4], 'big') % len(candidates)]['id']
            else:
                voice = None
            profile = {'name': span.speaker, 'gender': gender, 'kind': kind,
                       'voice': voice, 'pitch': 0,
                       'seed': int.from_bytes(digest[2:6], 'big') % 2147483647}
            saved[key] = result[key] = profile
        if result:
            CAST_FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary = CAST_FILE.with_suffix('.tmp')
            temporary.write_text(json.dumps(saved, ensure_ascii=False, indent=2))
            temporary.replace(CAST_FILE)
        return result


def build_units(scene: Scene, narrator_voice: str, limit: int = 240, style: str = 'neutral') -> list[Unit]:
    from .brazilian import voice_catalog
    profiles = _profiles(scene, voice_catalog(), narrator_voice)
    missing = sorted({span.speaker for span in scene.spans if span.text and span.kind == 'dialogue'
                      and not profiles.get(identity(span.speaker), {}).get('voice')})
    if missing:
        raise ValueError('Falta uma voz de personagem compatível para: ' + ', '.join(missing) +
                         '. Importe ou classifique outra gravação como Personagem ou Ambos, '
                         'com gênero e tipo compatíveis. A voz selecionada do narrador é reservada à narração.')
    units = []
    for span in scene.spans:
        if not span.text:
            continue
        profile = profiles.get(identity(span.speaker), {})
        gender = profile.get('gender', span.gender)
        voice = narrator_voice if span.kind != 'dialogue' else span.voice_override or profile['voice']
        # Preserve the recorded timbre; pitch shifting made voices sound artificial.
        pitch = 0.0
        chunks = split_text(span.text, limit)
        for chunk in chunks:
            # A new exclamation in an otherwise playful speech can become a
            # command without changing its speaker/reference.
            delivery = span.delivery
            if chunk.rstrip().endswith('!') and delivery in {'neutral', 'warm', 'playful'}:
                delivery = 'urgent'
            expr, pace, volume, gap = DELIVERY[delivery]
            if style == 'storyteller':
                expr = min(.8, expr + .12)
            elif style == 'calm':
                expr = max(.25, expr - .10)
            # Show the actual casting rather than only the inferred speaker.
            span.voice_id = voice
            units.append(Unit(chunk, span.speaker, voice, gender, delivery, pitch,
                              pace, volume, expr, gap,
                              int(profile.get('seed', 42)), span.id))
    return units

### Volume consistente entre vozes

Cada trecho sintetizado, incluindo o narrador, é normalizado antes da montagem. A referência é a sonoridade percebida (alvo de −18 LUFS), com controle de pico de −1,5 dBTP. Falas muito curtas usam um ajuste por energia com margem de pico quando a medição integrada não é possível. Silêncio não é amplificado. A normalização não altera duração, altura ou velocidade.

As emoções continuam guiando a expressividade e as pausas, mas deixam de multiplicar o volume de cada personagem. O nivelamento vale para novas gerações e para o WAV baixado; arquivos antigos precisam ser gerados novamente. A velocidade de exportação é aplicada depois desse nivelamento.
