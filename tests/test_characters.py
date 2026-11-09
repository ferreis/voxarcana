import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from backend.app import characters
from backend.app.jobs import JobQueue
from backend.app.scene import Scene, Span


class CharacterMemoryTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name)
        for target, filename in [('backend.app.characters.CHARACTER_FILE', 'characters.json'),
                                 ('backend.app.cast.CAST_FILE', 'cast.json')]:
            patched = patch(target, self.path / filename)
            patched.start()
            self.addCleanup(patched.stop)
        self.catalog = [{'id': 'carlos', 'name': 'Carlos', 'role': 'narrator'},
                        {'id': 'ditador', 'name': 'Ditador', 'role': 'character', 'gender': 'male'},
                        {'id': 'atriz', 'name': 'Atriz', 'role': 'character', 'gender': 'female'}]

    def scene(self, name='Garrin', gender='unknown'):
        return Scene([Span(0, 0, 4, 'dialogue', 'Oi!', 'Oi!', speaker=name, gender=gender)], 'test')

    def remember(self, name='Garrin', voice='ditador', gender='male', original=None):
        source = self.scene(original or name)
        corrected = copy.deepcopy(source)
        corrected.spans[0].speaker = name
        corrected.spans[0].gender = gender
        corrected.spans[0].voice_override = voice
        characters.remember_review(source, corrected)

    def test_manual_choice_survives_reload_and_overrides_later_model_gender(self):
        self.remember()
        self.assertTrue((self.path / 'characters.json').is_file())
        scene = characters.apply_saved(self.scene(gender='female'), 'carlos', self.catalog)
        span = scene.spans[0]
        self.assertEqual((span.speaker, span.gender, span.voice_override), ('Garrin', 'male', 'ditador'))
        self.assertTrue(span.character_saved)
        self.assertEqual(characters.list_characters(self.catalog)[0]['voice_name'], 'Ditador')
        # Fresh disk read, independent of an old queue or in-memory scene.
        characters.update_character('garrin', 'Garrin', 'male', 'atriz', self.catalog)
        scene = characters.apply_saved(self.scene(), 'carlos', self.catalog)
        self.assertEqual(scene.spans[0].voice_override, 'atriz')

    def test_previous_cast_is_recovered_and_not_overwritten_by_automatic_profiles(self):
        (self.path / 'cast.json').write_text(json.dumps({'garrin': {'name': 'Garrin', 'gender': 'male', 'voice': 'ditador'}}))
        self.assertEqual(characters.list_characters(self.catalog)[0]['voice_id'], 'ditador')
        (self.path / 'cast.json').write_text('{}')
        self.assertEqual(characters.list_characters(self.catalog)[0]['voice_id'], 'ditador')

    def test_missing_voice_narrator_collision_and_narrator_only_require_review(self):
        self.remember()
        for narrator, catalog in [('carlos', []), ('ditador', self.catalog),
                                    ('carlos', [{**v, 'role': 'narrator'} for v in self.catalog])]:
            span = characters.apply_saved(self.scene(), narrator, catalog).spans[0]
            self.assertFalse(span.character_saved)
            self.assertEqual(span.voice_override, '')
        self.assertEqual(characters.list_characters([])[0]['voice_id'], 'ditador')
        self.assertFalse(characters.list_characters([])[0]['available'])

    def test_corrected_spelling_is_remembered_but_reassigned_dialogue_does_not_merge_people(self):
        self.remember(original='Garri')
        self.assertEqual(characters.apply_saved(self.scene('Garri'), 'carlos', self.catalog).spans[0].speaker, 'Garrin')
        self.remember(name='Brigitte', voice='atriz', gender='female', original='Garrin')
        self.assertEqual(characters.apply_saved(self.scene(), 'carlos', self.catalog).spans[0].voice_override, 'ditador')
        self.assertEqual(characters.apply_saved(self.scene('Brigitte'), 'carlos', self.catalog).spans[0].voice_override, 'atriz')

    def test_known_cast_skips_questions_but_new_character_stops_before_tts(self):
        self.remember()
        for name, expected in [('Garrin', 'done'), ('Novo', 'review')]:
            queue = JobQueue()
            reader = Mock()
            reader.analyze.return_value = self.scene(name, 'female')
            engine = Mock()
            engine.synthesize.return_value = b'wav'
            with patch('backend.app.scene.get_reader', return_value=reader), \
                 patch('backend.app.brazilian.voice_catalog', return_value=self.catalog), \
                 patch('backend.app.jobs.get_engine', return_value=engine):
                job = queue.submit({'text': '"Oi!"', 'voice': 'carlos', 'review': True})
                queue.pool.shutdown(wait=True)
            self.assertEqual(job.status, expected)
            if expected == 'done':
                self.assertEqual(engine.synthesize.call_args.kwargs['scene'].spans[0].voice_override, 'ditador')
            else:
                engine.assert_not_called()

    def test_character_api_lists_and_edits_saved_choice(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        self.remember()
        with patch('backend.app.main.voice_catalog', return_value=self.catalog):
            client = TestClient(app)
            self.assertEqual(client.get('/v1/characters').json()[0]['name'], 'Garrin')
            payload = {'name': 'Garrin', 'gender': 'male', 'voice_id': 'atriz'}
            self.assertEqual(client.patch('/v1/characters/garrin', json=payload,
                                         headers={'Origin': 'https://outside.example'}).status_code, 403)
            self.assertEqual(client.patch('/v1/characters/garrin', json=payload).status_code, 200)
            self.assertEqual(client.get('/v1/characters').json()[0]['voice_id'], 'atriz')
            self.assertEqual(client.patch('/v1/characters/garrin', json={**payload, 'voice_id': 'carlos'}).status_code, 422)
