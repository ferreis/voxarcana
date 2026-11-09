from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from backend.app.jobs import JobQueue, Job
from backend.app.main import ReviewedLine
from backend.app.scene import Scene, Span, NARRATOR, SceneLabels, segment_text, apply_labels
from backend.app.cast import build_units


class CastReviewTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        for target, filename in [('backend.app.characters.CHARACTER_FILE', 'characters.json'),
                                 ('backend.app.cast.CAST_FILE', 'cast.json')]:
            patched = patch(target, Path(directory.name) / filename)
            patched.start()
            self.addCleanup(patched.stop)

    def scene(self):
        return Scene([Span(0, 0, 5, 'narration', 'Cena.', 'Cena.'),
                      Span(1, 5, 10, 'dialogue', 'Oi!', 'Oi!', speaker='Garri', gender='unknown')], 'test')

    def test_analysis_stops_for_review_and_does_not_load_tts(self):
        queue = JobQueue()
        reader = Mock()
        reader.analyze.return_value = self.scene()
        with patch('backend.app.scene.get_reader', return_value=reader), \
             patch('backend.app.jobs.get_engine') as engine:
            job = queue.submit({'text': 'Cena. "Oi!"', 'voice': 'narrator', 'style': 'neutral', 'automatic': True, 'review': True})
            queue.pool.shutdown(wait=True)
        self.assertEqual(job.status, 'review')
        self.assertEqual(job.public()['source_text'], 'Cena. "Oi!"')
        self.assertEqual(job.scene['segments'][1]['speaker'], 'Garri')
        engine.assert_not_called()

    def test_review_uses_original_text_and_honors_corrected_name_gender_and_voice(self):
        queue = JobQueue()
        scene = self.scene()
        job = Job('review', status='review', review_scene=scene,
                  review_payload={'text': 'Cena. "Oi!"', 'voice': 'narrator', 'style': 'neutral', 'automatic': True})
        queue.jobs[job.id] = job
        catalog = [{'id': 'narrator', 'role': 'both'}, {'id': 'actor', 'role': 'character', 'gender': 'male'}]
        engine = Mock()
        engine.synthesize.return_value = b'wav'
        line = ReviewedLine(id=1, speaker='Garrin', gender='male', voice_id='actor')
        with patch('backend.app.jobs.get_engine', return_value=engine):
            queue.perform_review(job.id, [line], 'narrator', 'neutral', catalog)
            queue.pool.shutdown(wait=True)
        payload = engine.synthesize.call_args.kwargs
        corrected = payload['scene'].spans[1]
        self.assertEqual((corrected.speaker, corrected.gender, corrected.voice_override), ('Garrin', 'male', 'actor'))
        self.assertEqual(corrected.text, scene.spans[1].text)
        self.assertEqual(scene.spans[1].speaker, 'Garri')
        with TemporaryDirectory() as directory, patch('backend.app.cast.CAST_FILE', Path(directory) / 'cast.json'), \
             patch('backend.app.brazilian.voice_catalog', return_value=catalog):
            self.assertEqual([u.voice for u in build_units(payload['scene'], 'narrator')], ['narrator', 'actor'])
        self.assertEqual(job.status, 'done')

    def test_review_rejects_narrator_voice_missing_duplicate_and_unknown_line_ids(self):
        queue = JobQueue()
        job = Job('review', status='review', review_scene=self.scene(), review_payload={'text': 'Original'})
        queue.jobs[job.id] = job
        catalog = [{'id': 'narrator', 'role': 'both'}, {'id': 'actor', 'role': 'character'}]
        line = ReviewedLine(id=1, speaker='Garrin', gender='male', voice_id='actor')
        invalid = [[], [line, line], [line.model_copy(update={'id': 99})],
                   [line.model_copy(update={'voice_id': 'narrator'})],
                   [line.model_copy(update={'speaker': NARRATOR})]]
        try:
            for lines in invalid:
                with self.assertRaises(ValueError):
                    queue.perform_review(job.id, lines, 'narrator', 'neutral', catalog)
                self.assertEqual(job.status, 'review')
            queue.cancel_job(job.id)
            self.assertEqual(job.status, 'cancelled')
            with self.assertRaises(ValueError):
                queue.perform_review(job.id, [line], 'narrator', 'neutral', catalog)
        finally:
            queue.pool.shutdown(wait=True)

    def test_review_http_approval_accepts_only_labels_and_keeps_server_text(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        queue = JobQueue()
        job = Job('review', status='review', review_scene=self.scene(),
                  review_payload={'text': 'Texto original.', 'automatic': True, 'voice': 'narrator'})
        queue.jobs[job.id] = job
        engine = Mock()
        engine.synthesize.return_value = b'wav'
        catalog = [{'id': 'narrator', 'role': 'both'}, {'id': 'actor', 'role': 'character'}]
        with patch('backend.app.main.queue', queue), patch('backend.app.main.voice_catalog', return_value=catalog), \
             patch('backend.app.jobs.get_engine', return_value=engine):
            client = TestClient(app)
            payload = {'voice': 'narrator', 'text': 'Não pode substituir.', 'speed': 1.25,
                       'lines': [{'id': 1, 'speaker': 'Garrin', 'gender': 'male', 'voice_id': 'actor'}]}
            self.assertEqual(client.post('/v1/jobs/review/perform', json=payload,
                                         headers={'Origin': 'https://outside.example'}).status_code, 403)
            self.assertEqual(client.post('/v1/jobs/review/perform', json=payload).status_code, 202)
            queue.pool.shutdown(wait=True)
            self.assertEqual(engine.synthesize.call_args.kwargs['text'], 'Texto original.')
            self.assertEqual(engine.synthesize.call_args.kwargs['speed'], 1.25)
            self.assertEqual(client.post('/v1/jobs/review/perform', json=payload).status_code, 422)

    def test_truncated_model_name_keeps_explicit_original_name_and_gender(self):
        scene = apply_labels(segment_text('"Oi!" Garrin responde.'), SceneLabels.model_validate({
            'cast': [{'name': 'Garri', 'gender': 'male'}], 'lines': [{'id': 0, 'speaker': 'Garri'}]}))
        self.assertEqual((scene.spans[0].speaker, scene.spans[0].gender), ('Garrin', 'male'))
