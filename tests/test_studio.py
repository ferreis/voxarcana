from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf
import torch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.brazilian import BrazilianEngine, SpeechCancelled
from backend.app.jobs import JobQueue


def sample_wav(seconds=4):
    buffer = BytesIO()
    sf.write(buffer, np.sin(np.arange(16000 * seconds) * .07).astype('float32') * .2,
             16000, format='WAV')
    return buffer.getvalue()


class StudioApiTest(unittest.TestCase):
    def setUp(self):
        self.settings = patch('backend.app.main.get_settings', return_value=SimpleNamespace(engine='chatterbox-br'))
        self.settings.start()
        self.addCleanup(self.settings.stop)
        catalog = patch('backend.app.main.voice_catalog', return_value=[{'id': 'imported-narrator', 'role': 'narrator'}])
        catalog.start()
        self.addCleanup(catalog.stop)
        self.client = TestClient(app)

    def test_input_validation_and_unknown_voices(self):
        self.assertEqual(self.client.post('/v1/jobs', json={'text': '  '}).status_code, 422)
        self.assertEqual(self.client.post('/v1/jobs', json={'text': 'Olá', 'voice': '../secret'}).status_code, 404)
        self.assertEqual(self.client.post('/v1/jobs', json={'text': 'Olá', 'style': 'invalid'}).status_code, 404)
        self.assertEqual(self.client.post('/v1/jobs', json={'text': 'Olá', 'instruction': 'Voz grave'}).status_code, 422)

    def test_empty_library_requires_import_and_removed_defaults_are_not_selected(self):
        with patch('backend.app.main.voice_catalog', return_value=[]):
            self.assertEqual(self.client.post('/v1/jobs', json={'text': 'Uma cena.'}).status_code, 422)
            self.assertEqual(self.client.post('/v1/jobs', json={'text': 'Uma cena.', 'voice': 'narrator-br'}).status_code, 404)

    def test_dialogue_needs_another_character_voice_before_queueing(self):
        with patch('backend.app.main.voice_catalog', return_value=[{'id': 'carlos', 'role': 'both'}]), \
             patch('backend.app.main.queue.submit') as submit:
            response = self.client.post('/v1/jobs', json={'text': '"Volte!" disse Garrin.', 'voice': 'carlos'})
            self.assertEqual(response.status_code, 422)
            self.assertIn('outra voz', response.json()['detail'])
            submit.assert_not_called()
        with patch('backend.app.main.voice_catalog', return_value=[{'id': 'actor', 'role': 'character'}]):
            response = self.client.post('/v1/jobs', json={'text': 'Narração.', 'voice': 'actor'})
            self.assertEqual(response.status_code, 422)

    def test_external_origin_cannot_start_generation(self):
        response = self.client.post('/v1/jobs', json={'text': 'Olá'}, headers={'Origin': 'https://outside.example'})
        self.assertEqual(response.status_code, 403)

    def test_reference_upload_validates_audio_and_registers_normalized_file(self):
        with TemporaryDirectory() as directory, patch('backend.app.main.REFERENCE_DIR', Path(directory)):
            response = self.client.post('/v1/voices/reference', data={'name': 'Minha voz BR', 'role': 'character', 'gender': 'female', 'kind': 'human'},
                                        files={'audio': ('voice.wav', sample_wav(), 'audio/wav')})
            self.assertEqual(response.status_code, 200)
            voice_id = response.json()['id']
            self.assertEqual(response.json()['role'], 'character')
            self.assertEqual(response.json()['gender'], 'female')
            self.assertNotIn('register', response.json())
            self.assertTrue((Path(directory) / f'{voice_id}.wav').is_file())
            self.assertTrue((Path(directory) / f'{voice_id}.json').is_file())
            short = self.client.post('/v1/voices/reference', data={'name': 'Curta'},
                                    files={'audio': ('short.wav', sample_wav(1), 'audio/wav')})
            self.assertEqual(short.status_code, 422)
            invalid = self.client.post('/v1/voices/reference', data={'name': 'Inválida'},
                                      files={'audio': ('bad.wav', b'invalid', 'audio/wav')})
            self.assertEqual(invalid.status_code, 422)

    def test_unknown_job_and_unknown_reference_return_404(self):
        self.assertEqual(self.client.get('/v1/jobs/missing').status_code, 404)
        self.assertEqual(self.client.get('/v1/jobs/missing/audio').status_code, 404)
        self.assertEqual(self.client.get('/v1/voices/missing/reference').status_code, 404)

    def test_creation_only_passes_validated_payload_to_queue(self):
        with patch('backend.app.main.queue.submit', return_value=SimpleNamespace(id='job')) as submit:
            response = self.client.post('/v1/jobs', json={'text': ' Uma cena. ', 'style': 'epic'})
            self.assertEqual(response.status_code, 202)
            submit.assert_called_once_with({'text': 'Uma cena.', 'voice': 'imported-narrator', 'style': 'epic', 'automatic': True, 'speed': 1.0})


class BrazilianGenerationTest(unittest.TestCase):
    def test_language_reference_and_chunk_joining(self):
        engine = BrazilianEngine()
        engine._model = Mock(sr=24000)
        engine._model.generate.return_value = torch.zeros(1, 240)
        progress = Mock()
        with TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.wav'
            reference.write_bytes(b'reference')
            with patch('backend.app.brazilian.reference_path', return_value=reference), \
                 patch('backend.app.config.get_settings', return_value=SimpleNamespace(chunk_chars=100)):
                audio = engine.synthesize('Uma cena no Brasil. ' * 12, style='calm', progress=progress)
        data, rate = sf.read(BytesIO(audio))
        self.assertEqual(rate, 24000)
        self.assertGreater(len(data), 240)
        calls = engine._model.generate.call_args_list
        self.assertGreater(len(calls), 1)
        self.assertIsNotNone(calls[0].kwargs['audio_prompt_path'])
        for call in calls:
            self.assertEqual(call.kwargs['language_id'], 'pt')
            self.assertLessEqual(len(call.args[0]), 100)
        self.assertIsNone(calls[-1].kwargs['audio_prompt_path'])

    def test_cancellation_prevents_next_chunk_and_audio_result(self):
        engine = BrazilianEngine()
        engine._model = Mock(sr=24000)
        cancelled = Event()
        def generate(*args, **kwargs):
            cancelled.set()
            return torch.zeros(1, 240)
        engine._model.generate.side_effect = generate
        with TemporaryDirectory() as directory:
            reference = Path(directory) / 'reference.wav'
            reference.touch()
            with patch('backend.app.brazilian.reference_path', return_value=reference):
                with self.assertRaises(SpeechCancelled):
                    engine.synthesize('Uma cena. ' * 100, cancelled=cancelled.is_set)
        engine._model.generate.assert_called_once()


class QueueTest(unittest.TestCase):
    def test_analysis_progress_and_results_are_exposed_separately_from_audio(self):
        queue = JobQueue()
        engine = Mock()
        def generate(**kwargs):
            kwargs['on_stage']('analyzing')
            kwargs['on_analysis'](25, 'Interpretando a cena.')
            kwargs['on_analysis'](100, 'Interpretação validada.')
            kwargs['on_scene']({'method': 'test', 'segments': []})
            kwargs['on_stage']('synthesizing')
            kwargs['progress'](1, 2)
            return b'wav'
        engine.synthesize.side_effect = generate
        with patch('backend.app.jobs.get_engine', return_value=engine):
            job = queue.submit({'text': 'Cena.', 'automatic': True})
            queue.pool.shutdown(wait=True)
        result = queue.snapshot(job.id)
        self.assertEqual(result['analysis_percent'], 100)
        self.assertEqual(result['analysis_events'], ['Interpretando a cena.', 'Interpretação validada.'])
        self.assertEqual((result['completed'], result['total']), (1, 2))
        self.assertEqual(result['status'], 'done')

    def test_cancelled_active_and_queued_jobs_never_publish_audio(self):
        queue = JobQueue()
        started = Event()
        release = Event()
        engine = Mock()
        def generate(**kwargs):
            started.set()
            release.wait(timeout=3)
            return b'wav'
        engine.synthesize.side_effect = generate
        try:
            with patch('backend.app.jobs.get_engine', return_value=engine):
                first = queue.submit({'text': 'Primeiro'})
                self.assertTrue(started.wait(timeout=3))
                second = queue.submit({'text': 'Segundo'})
                third = queue.submit({'text': 'Terceiro'})
                with self.assertRaises(ValueError):
                    queue.submit({'text': 'Quarto'})
                queue.cancel_job(first.id)
                queue.cancel_job(second.id)
                queue.cancel_job(third.id)
                release.set()
                queue.pool.shutdown(wait=True)
                self.assertEqual(queue.snapshot(first.id)['status'], 'cancelled')
                self.assertEqual(queue.snapshot(second.id)['status'], 'cancelled')
                self.assertIsNone(first.audio)
                engine.synthesize.assert_called_once()
        finally:
            release.set()
            queue.pool.shutdown(wait=True)
