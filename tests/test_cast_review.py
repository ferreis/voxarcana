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

    def test_narration_only_waits_until_explicit_generation(self):
        queue = JobQueue()
        self.addCleanup(queue.pool.shutdown, wait=True)
        scene = Scene([Span(0, 0, 5, 'narration', 'Cena.', 'Cena.')], 'test')
        reader = Mock()
        reader.analyze.return_value = scene
        job = Job('narration-only')
        queue.jobs[job.id] = job
        engine = Mock()
        engine.synthesize.return_value = b'wav'
        payload = {'text': 'Cena.', 'voice': 'narrator', 'style': 'neutral',
                   'automatic': True, 'review': True}
        with patch('backend.app.scene.get_reader', return_value=reader), \
             patch('backend.app.jobs.get_engine', return_value=engine):
            queue._run(job, payload)
            self.assertEqual(job.status, 'review')
            self.assertIsNone(job.audio)
            engine.assert_not_called()
            queue.perform_review(job.id, [], 'narrator', 'neutral',
                                 [{'id': 'narrator', 'role': 'narrator'}])
            queue.pool.shutdown(wait=True)
        self.assertEqual(job.status, 'done')
        self.assertEqual(job.audio, b'wav')
        reader.analyze.assert_called_once()
        engine.synthesize.assert_called_once()

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

    def test_completed_job_regenerates_with_new_narrator_and_keeps_review_without_llm(self):
        queue = JobQueue()
        self.addCleanup(queue.pool.shutdown, wait=True)
        scene = self.scene()
        job = Job('completed', status='done', audio=b'old-wav', completed=4, total=4,
                  speaker='Garrin', delivery='neutral', review_scene=scene,
                  review_payload={'text': 'Cena. "Oi!"', 'voice': 'old-narrator',
                                  'style': 'neutral', 'automatic': True, 'speed': 1.25})
        queue.jobs[job.id] = job
        catalog = [{'id': 'new-narrator', 'role': 'narrator'},
                   {'id': 'actor', 'role': 'character', 'gender': 'male'}]
        corrected_line = ReviewedLine(id=1, speaker='Garrin', gender='male', voice_id='actor')
        engine = Mock()
        engine.synthesize.return_value = b'new-wav'
        with patch.object(queue.pool, 'submit') as submit, \
             patch('backend.app.scene.get_reader') as reader, \
             patch('backend.app.jobs.get_engine', return_value=engine):
            queue.perform_review(job.id, [corrected_line], 'new-narrator', 'calm', catalog)
            self.assertEqual((job.status, job.completed, job.total, job.audio), ('queued', 0, 0, None))
            self.assertIsNone(job.speaker)
            submitted_payload = submit.call_args.args[2]
            queue._run(job, submitted_payload)
        reader.assert_not_called()
        payload = engine.synthesize.call_args.kwargs
        self.assertEqual((payload['voice'], payload['style'], payload['speed']), ('new-narrator', 'calm', 1.25))
        self.assertEqual(payload['text'], 'Cena. "Oi!"')
        self.assertEqual((payload['scene'].spans[1].speaker, payload['scene'].spans[1].voice_id), ('Garrin', 'actor'))
        self.assertEqual([span.text for span in payload['scene'].spans], [span.text for span in scene.spans])
        self.assertEqual((job.status, job.audio), ('done', b'new-wav'))

    def test_active_jobs_and_done_jobs_without_analysis_cannot_be_reapproved(self):
        queue = JobQueue()
        self.addCleanup(queue.pool.shutdown, wait=True)
        for status in ['queued', 'running', 'cancelling']:
            job = Job(status, status=status, review_scene=self.scene(), review_payload={'text': 'Cena.'})
            queue.jobs[job.id] = job
            with self.subTest(status=status), self.assertRaises(ValueError):
                queue.perform_review(job.id, [], 'narrator', 'neutral', [])
            self.assertEqual(job.status, status)
        job = Job('narration', status='done', audio=b'original')
        queue.jobs[job.id] = job
        with self.assertRaises(ValueError):
            queue.perform_review(job.id, [], 'narrator', 'neutral', [])
        self.assertEqual(job.audio, b'original')

    def test_review_http_approval_accepts_only_labels_and_keeps_server_text(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app
        queue = JobQueue()
        self.addCleanup(queue.pool.shutdown, wait=True)
        job = Job('review', status='review', review_scene=self.scene(),
                  review_payload={'text': 'Texto original.', 'automatic': True, 'voice': 'narrator'})
        queue.jobs[job.id] = job
        engine = Mock()
        engine.synthesize.return_value = b'wav'
        catalog = [{'id': 'narrator', 'role': 'both'}, {'id': 'new-narrator', 'role': 'narrator'},
                   {'id': 'actor', 'role': 'character'}]
        with patch('backend.app.main.queue', queue), patch('backend.app.main.voice_catalog', return_value=catalog), \
             patch('backend.app.jobs.get_engine', return_value=engine):
            client = TestClient(app)
            payload = {'voice': 'narrator', 'text': 'Não pode substituir.', 'speed': 1.25,
                       'lines': [{'id': 1, 'speaker': 'Garrin', 'gender': 'male', 'voice_id': 'actor'}]}
            self.assertEqual(client.post('/v1/jobs/review/perform', json=payload,
                                         headers={'Origin': 'https://outside.example'}).status_code, 403)
            self.assertEqual(client.post('/v1/jobs/review/perform', json=payload).status_code, 202)
            queue.pool.submit(lambda: None).result(timeout=3)
            self.assertEqual(engine.synthesize.call_args.kwargs['text'], 'Texto original.')
            self.assertEqual(engine.synthesize.call_args.kwargs['speed'], 1.25)
            self.assertEqual(client.post('/v1/jobs/review/perform', json={**payload, 'voice': 'new-narrator'}).status_code, 202)
            queue.pool.shutdown(wait=True)
            self.assertEqual(engine.synthesize.call_count, 2)
            self.assertEqual(engine.synthesize.call_args.kwargs['voice'], 'new-narrator')
            self.assertEqual(engine.synthesize.call_args.kwargs['text'], 'Texto original.')

    def test_truncated_model_name_keeps_explicit_original_name_and_gender(self):
        scene = apply_labels(segment_text('"Oi!" Garrin responde.'), SceneLabels.model_validate({
            'cast': [{'name': 'Garri', 'gender': 'male'}], 'lines': [{'id': 0, 'speaker': 'Garri'}]}))
        self.assertEqual((scene.spans[0].speaker, scene.spans[0].gender), ('Garrin', 'male'))
