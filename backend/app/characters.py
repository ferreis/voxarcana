"""User-owned character choices, separate from automatic casting suggestions."""
import json
from difflib import SequenceMatcher
from pathlib import Path
from threading import RLock
from uuid import uuid4

from .scene import identity, NARRATOR

CHARACTER_FILE = Path(__file__).resolve().parents[1] / 'voices/characters.json'
_lock = RLock()
GENDERS = {'male', 'female', 'neutral', 'unknown'}


def _write(records):
    CHARACTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = CHARACTER_FILE.with_suffix(f'.{uuid4()}.tmp')
    temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2))
    temporary.replace(CHARACTER_FILE)


def _read():
    if CHARACTER_FILE.exists():
        data = json.loads(CHARACTER_FILE.read_text())
        if not isinstance(data, dict):
            raise ValueError('O elenco salvo está inválido. Confira voices/characters.json.')
        return data
    # Recover the most recent choices from installations predating this book.
    from .cast import CAST_FILE
    try:
        previous = json.loads(CAST_FILE.read_text())
    except (OSError, ValueError):
        previous = {}
    records = {}
    for profile in previous.values() if isinstance(previous, dict) else []:
        if not isinstance(profile, dict):
            continue
        name = profile.get('name', '')
        if name and identity(name) not in {'narrador', 'personagem'} and profile.get('voice') and profile.get('gender') in GENDERS:
            records[identity(name)] = {'name': name, 'gender': profile['gender'],
                                      'voice_id': profile['voice'], 'aliases': []}
    _write(records)
    return records


def _find(records, name):
    key = identity(name)
    if key in {'', 'narrador', 'personagem'}:
        return None
    for record_id, record in records.items():
        if key == identity(record['name']):
            return record_id
    matches = [record_id for record_id, record in records.items()
               if key in {identity(a) for a in record.get('aliases', [])}]
    return matches[0] if len(matches) == 1 else None


def list_characters(catalog):
    voices = {v['id']: v for v in catalog}
    with _lock:
        records = _read()
        result = []
        for key, record in records.items():
            voice = voices.get(record['voice_id'])
            result.append({'id': key, **record, 'voice_name': voice.get('name') if voice else None,
                           'available': bool(voice and voice.get('role', 'both') in {'character', 'both'})})
        return sorted(result, key=lambda item: item['name'].casefold())


def apply_saved(scene, narrator_voice, catalog):
    voices = {v['id']: v for v in catalog}
    with _lock:
        records = _read()
        for span in scene.spans:
            if span.kind != 'dialogue' or not span.text:
                continue
            key = _find(records, span.speaker)
            if key is None:
                continue
            record = records[key]
            voice = voices.get(record['voice_id'])
            span.speaker = record['name']
            span.gender = record['gender']
            valid = voice and voice['id'] != narrator_voice and voice.get('role', 'both') in {'character', 'both'}
            span.character_saved = bool(valid)
            span.voice_override = record['voice_id'] if valid else ''
            span.voice_id = span.voice_override
            if valid:
                span.voice_kind = voice.get('kind', 'human')
    return scene


def remember_review(original, corrected):
    originals = {s.id: s for s in original.spans}
    chosen = {}
    sources = {}
    for span in corrected.spans:
        if span.kind != 'dialogue' or not span.text:
            continue
        key = identity(span.speaker)
        if key in {'', 'narrador', 'personagem'}:
            continue
        value = {'name': span.speaker, 'gender': span.gender, 'voice_id': span.voice_override}
        if key in chosen and chosen[key] != value:
            raise ValueError('Use o mesmo gênero e a mesma voz para todas as falas de um personagem.')
        chosen[key] = value
        source = originals[span.id].speaker
        if identity(source) not in {'narrador', 'personagem', ''}:
            sources.setdefault(source, set()).add(key)
    with _lock:
        records = _read()
        for key, value in chosen.items():
            existing = _find(records, value['name'])
            aliases = set(records.get(existing, {}).get('aliases', []))
            if existing and existing != key:
                aliases.add(records[existing]['name'])
                records.pop(existing)
            for source, targets in sources.items():
                original_id = _find(records, source)
                if (targets == {key} and identity(source) != key
                        and (original_id is None or original_id == existing)
                        and SequenceMatcher(None, identity(source), key).ratio() >= .85):
                    aliases.add(source)
            records[key] = {**value, 'aliases': sorted(aliases)}
        _write(records)


def update_character(record_id, name, gender, voice_id, catalog, aliases=None):
    voice = next((v for v in catalog if v['id'] == voice_id), None)
    if not voice or voice.get('role', 'both') not in {'character', 'both'}:
        raise ValueError('Escolha uma voz classificada como Personagem ou Ambos.')
    key = identity(name)
    if key in {'', 'narrador', 'personagem'}:
        raise ValueError('Escolha um nome de personagem válido.')
    with _lock:
        records = _read()
        if record_id not in records:
            raise LookupError('Personagem não encontrado.')
        existing = _find(records, name)
        if existing and existing != record_id:
            raise ValueError('Já existe outro personagem com esse nome.')
        previous = records[record_id]
        requested_aliases = previous.get('aliases', []) if aliases is None else aliases
        normalized_aliases = {}
        for alias in requested_aliases:
            alias_name = alias.strip()
            alias_key = identity(alias_name)
            if alias_key in {'', 'narrador', 'personagem'}:
                raise ValueError('Use apelidos ou sobrenomes válidos; Narrador é reservado à narração.')
            if alias_key != key:
                normalized_aliases.setdefault(alias_key, alias_name)
        if identity(previous['name']) != key:
            normalized_aliases.setdefault(identity(previous['name']), previous['name'])
        claimed_names = {key, *normalized_aliases}
        for other_id, other_record in records.items():
            if other_id == record_id:
                continue
            other_names = {identity(other_record['name']), *(identity(alias) for alias in other_record.get('aliases', []))}
            if claimed_names & other_names:
                raise ValueError('Esse nome, apelido ou sobrenome já está vinculado a outro personagem.')
        records.pop(record_id)
        records[key] = {'name': name, 'gender': gender, 'voice_id': voice_id,
                        'aliases': sorted(normalized_aliases.values())}
        _write(records)
    return next(record for record in list_characters(catalog) if record['id'] == key)
