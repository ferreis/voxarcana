from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.brazilian import voice_catalog
from backend.app.cast import build_units
from backend.app.scene import Scene, Span, SceneLabels, apply_labels, segment_text


class LibraryTest(unittest.TestCase):
    def test_legacy_recording_keeps_name_and_audio_and_can_be_classified(self):
        voice_id = '96773208-264c-421f-b1e7-f1b81d7dc1a1'
        with TemporaryDirectory() as directory, \
             patch('backend.app.brazilian.REFERENCE_DIR', Path(directory)), \
             patch('backend.app.main.REFERENCE_DIR', Path(directory)), \
             patch('backend.app.main.get_settings', return_value=SimpleNamespace(engine='chatterbox-br')):
            wav = Path(directory) / f'{voice_id}.wav'
            wav.write_bytes(b'original audio')
            metadata = wav.with_suffix('.json')
            metadata.write_text('{"name": "Minha voz antiga"}')
            legacy = next(v for v in voice_catalog() if v['id'] == voice_id)
            self.assertEqual(legacy['gender'], 'unknown')
            self.assertEqual(legacy['name'], 'Minha voz antiga')
            client = TestClient(app)
            response = client.patch(f'/v1/voices/{voice_id}', json={
                'name': 'Minha voz antiga', 'role': 'character', 'gender': 'neutral',
                'kind': 'robot', 'register': 'low'})
            self.assertEqual(response.status_code, 200)
            current = next(v for v in voice_catalog() if v['id'] == voice_id)
            self.assertEqual((current['role'], current['gender'], current['kind']), ('character', 'neutral', 'robot'))
            self.assertEqual(wav.read_bytes(), b'original audio')
            self.assertEqual(client.patch(f'/v1/voices/{voice_id}', json={'name': 'x', 'gender': 'invalid'}).status_code, 422)
            self.assertEqual(client.patch('/v1/voices/narrator-br', json={'name': 'x'}).status_code, 404)
            self.assertEqual(client.patch(f'/v1/voices/{voice_id}', json={'name': 'x'}, headers={'Origin': 'https://outside.example'}).status_code, 403)
            self.assertEqual(json.loads(metadata.read_text())['kind'], 'robot')

    def test_delete_removes_only_selected_reference_and_blocks_active_jobs(self):
        voice_id = '96773208-264c-421f-b1e7-f1b81d7dc1a1'
        with TemporaryDirectory() as directory, \
             patch('backend.app.main.REFERENCE_DIR', Path(directory)), \
             patch('backend.app.brazilian.REFERENCE_DIR', Path(directory)), \
             patch('backend.app.main.get_settings', return_value=SimpleNamespace(engine='chatterbox-br')), \
             patch('backend.app.main.queue.jobs', {}) as jobs:
            metadata = Path(directory) / f'{voice_id}.json'
            metadata.write_text('{"name": "Voz descartável", "register": "low"}')
            metadata.with_suffix('.wav').write_bytes(b'audio')
            other = Path(directory) / 'other.wav'
            other.write_bytes(b'keep')
            catalog = voice_catalog()
            self.assertEqual(len(catalog), 1)
            self.assertNotIn('register', catalog[0])
            client = TestClient(app)
            jobs['active'] = SimpleNamespace(status='running')
            self.assertEqual(client.delete(f'/v1/voices/{voice_id}').status_code, 409)
            self.assertTrue(metadata.exists())
            jobs.clear()
            self.assertEqual(client.delete(f'/v1/voices/{voice_id}', headers={'Origin': 'https://outside.example'}).status_code, 403)
            self.assertEqual(client.delete(f'/v1/voices/{voice_id}').status_code, 200)
            self.assertFalse(metadata.exists())
            self.assertFalse(metadata.with_suffix('.wav').exists())
            self.assertEqual(other.read_bytes(), b'keep')
            self.assertEqual(voice_catalog(), [])
            self.assertEqual(client.delete(f'/v1/voices/{voice_id}').status_code, 404)
            self.assertEqual(client.delete('/v1/voices/narrator-br').status_code, 404)

    def test_uploaded_cast_matches_role_gender_kind_and_refreshes_after_edit(self):
        catalog = [dict(id='stock', role='both', gender='female', kind='human', register='medium', editable=False),
                   dict(id='narrator-only', role='narrator', gender='female', kind='human', editable=True),
                   dict(id='actor', role='character', gender='female', kind='human', register='medium', editable=True),
                   dict(id='robot', role='character', gender='neutral', kind='robot', editable=True),
                   dict(id='entity', role='character', gender='neutral', kind='entity', editable=True)]
        spans = [Span(0, 0, 1, 'narration', 'a', 'a'),
                 Span(1, 1, 2, 'dialogue', 'b', 'b', speaker='Bela', gender='female'),
                 Span(2, 2, 3, 'dialogue', 'c', 'c', speaker='Máquina', gender='neutral', voice_kind='robot'),
                 Span(3, 3, 4, 'dialogue', 'd', 'd', speaker='Espírito', gender='neutral', voice_kind='entity'),
                 Span(4, 4, 5, 'dialogue', 'e', 'e', speaker='Incerto', gender='unknown')]
        with TemporaryDirectory() as directory, patch('backend.app.cast.CAST_FILE', Path(directory) / 'cast.json'), \
             patch('backend.app.brazilian.voice_catalog', return_value=catalog):
            first = build_units(Scene(spans, 'test'), 'chosen')
            self.assertEqual([u.voice for u in first], ['chosen', 'actor', 'robot', 'entity', 'stock'])
            self.assertTrue(all(u.pitch == 0 for u in first))
            self.assertEqual([u.voice for u in build_units(Scene(spans, 'test'), 'chosen')], [u.voice for u in first])
            catalog[2]['role'] = 'narrator'
            changed = build_units(Scene(spans, 'test'), 'chosen')
            self.assertEqual(changed[1].voice, 'stock')
            expressive = build_units(Scene(spans, 'test'), 'chosen', style='storyteller')
            self.assertGreater(expressive[0].expression, first[0].expression)
            robot_unknown = replace(spans[2], gender='unknown')
            self.assertEqual(build_units(Scene([robot_unknown], 'test'), 'chosen')[0].voice, 'robot')

    def test_selected_narrator_is_excluded_even_when_both_or_persisted_actor(self):
        narrator = dict(id='carlos', role='both', gender='male', kind='human')
        actor = dict(id='actor', role='character', gender='male', kind='human')
        scene = Scene([Span(0, 0, 1, 'narration', 'a', 'a'),
                       Span(1, 1, 2, 'dialogue', 'b', 'b', speaker='Garrin', gender='male')], 'test')
        with TemporaryDirectory() as directory, patch('backend.app.cast.CAST_FILE', Path(directory) / 'cast.json'), \
             patch('backend.app.brazilian.voice_catalog', return_value=[narrator, actor]):
            Path(directory, 'cast.json').write_text('{"garrin": {"voice": "carlos"}}')
            units = build_units(scene, 'carlos')
            self.assertEqual([u.voice for u in units], ['carlos', 'actor'])
        with TemporaryDirectory() as directory, patch('backend.app.cast.CAST_FILE', Path(directory) / 'cast.json'), \
             patch('backend.app.brazilian.voice_catalog', return_value=[narrator]):
            with self.assertRaisesRegex(ValueError, 'Falta uma voz de personagem.*Garrin'):
                build_units(scene, 'carlos')
            only_narration = build_units(Scene(scene.spans[:1], 'test'), 'carlos')
            self.assertEqual(only_narration[0].voice, 'carlos')

    def test_reader_distinguishes_robot_kind_and_neutral_gender(self):
        scene = apply_labels(segment_text('"Olá," disse Unidade.'), SceneLabels.model_validate({
            'cast': [{'name': 'Unidade', 'gender': 'neutral', 'voice_kind': 'robot'}],
            'lines': [{'id': 0, 'speaker': 'Unidade'}]}))
        self.assertEqual(scene.spans[0].voice_kind, 'robot')
        self.assertEqual(scene.spans[0].gender, 'neutral')
