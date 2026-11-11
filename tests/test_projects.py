import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from backend.app import characters, projects
from backend.app.jobs import JobQueue
from backend.app.main import app, ReviewedLine
from backend.app.scene import Scene, Span


class ProjectCastingTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        directory_path = Path(directory.name)
        storage = patch('backend.app.audio_storage.DATA_DIR', directory_path / 'Data')
        storage.start()
        self.addCleanup(storage.stop)
        for target, filename in [('backend.app.projects.PROJECT_FILE', 'projects.json'),
                                 ('backend.app.characters.CHARACTER_FILE', 'characters.json'),
                                 ('backend.app.cast.CAST_FILE', 'cast.json')]:
            patched = patch(target, directory_path / filename)
            patched.start()
            self.addCleanup(patched.stop)
        self.client = TestClient(app)
        self.catalog = [{'id': 'narrator', 'role': 'narrator'},
                        {'id': 'actor', 'role': 'character'},
                        {'id': 'another-actor', 'role': 'character'}]

    def scene(self):
        return Scene([Span(0, 0, 3, 'dialogue', 'Oi!', 'Oi!', speaker='Lia', gender='female')], 'test')

    def remember(self, project_id, voice_id='actor'):
        original = self.scene()
        corrected = copy.deepcopy(original)
        corrected.spans[0].voice_override = voice_id
        characters.remember_review(original, corrected, project_id)

    def test_projects_keep_existing_cast_and_allow_independent_voice_choices(self):
        self.remember('default')
        project = projects.create_project('Outra história')
        self.assertEqual(characters.list_characters(self.catalog, project['id']), [])
        self.remember(project['id'], 'another-actor')
        self.assertEqual(characters.list_characters(self.catalog, 'default')[0]['voice_id'], 'actor')
        self.assertEqual(characters.list_characters(self.catalog, project['id'])[0]['voice_id'], 'another-actor')
        # A voice may belong to a different character in another project.
        characters.update_character('lia', 'Bia', 'female', 'actor', self.catalog, project_id=project['id'])
        self.assertEqual(characters.list_characters(self.catalog, 'default')[0]['name'], 'Lia')
        self.assertEqual(characters.list_characters(self.catalog, project['id'])[0]['name'], 'Bia')
        self.assertEqual(projects.list_projects()[1], project)

    def test_project_api_validates_names_and_scopes_character_edits(self):
        self.remember('default')
        response = self.client.post('/v1/projects', json={'name': '  Campanha  '})
        self.assertEqual(response.status_code, 201)
        project = response.json()
        self.assertEqual(project['name'], 'Campanha')
        self.assertEqual(len(self.client.get('/v1/projects').json()), 2)
        for name in [' ', 'campanha']:
            self.assertEqual(self.client.post('/v1/projects', json={'name': name}).status_code, 422)
        with patch('backend.app.main.voice_catalog', return_value=self.catalog):
            self.assertEqual(self.client.get('/v1/characters', params={'project_id': project['id']}).json(), [])
            response = self.client.patch('/v1/characters/lia', params={'project_id': project['id']},
                                         json={'name': 'Lia', 'voice_id': 'actor'})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(self.client.get('/v1/characters').json()[0]['name'], 'Lia')
        for project_id in ['unknown', '../characters.json']:
            self.assertEqual(self.client.get('/v1/characters', params={'project_id': project_id}).status_code, 404)
            self.assertEqual(self.client.post('/v1/jobs', json={'text': 'Oi', 'project_id': project_id}).status_code, 404)

    def test_new_project_does_not_import_automatic_cast_back_into_initial_project(self):
        projects.create_project('Outra campanha')
        from backend.app.cast import CAST_FILE
        CAST_FILE.write_text('{"lia": {"name": "Lia", "gender": "female", "voice": "actor"}}')
        self.assertEqual(characters.list_characters(self.catalog, 'default'), [])

    def test_review_job_uses_and_saves_only_its_original_project(self):
        self.remember('default', 'another-actor')
        project = projects.create_project('Novo elenco')
        queue = JobQueue()
        reader = Mock()
        reader.analyze.return_value = self.scene()
        engine = Mock()
        engine.synthesize.return_value = b'wav'
        with patch('backend.app.scene.get_reader', return_value=reader), \
             patch('backend.app.brazilian.voice_catalog', return_value=self.catalog), \
             patch('backend.app.jobs.get_engine', return_value=engine):
            job = queue.submit({'text': 'Oi!', 'voice': 'narrator', 'review': True, 'project_id': project['id']})
            queue.pool.submit(lambda: None).result(timeout=5)
            self.assertFalse(job.scene['segments'][0].get('voice_id'))
            self.assertEqual(job.public()['project_id'], project['id'])
            queue.perform_review(job.id, [ReviewedLine(id=0, speaker='Lia', gender='female', voice_id='actor')],
                                 'narrator', 'neutral', self.catalog)
            queue.pool.shutdown(wait=True)
        self.assertEqual(job.status, 'done')
        self.assertNotIn('project_id', engine.synthesize.call_args.kwargs)
        self.assertEqual(characters.list_characters(self.catalog, project['id'])[0]['voice_id'], 'actor')
        self.assertEqual(characters.list_characters(self.catalog, 'default')[0]['voice_id'], 'another-actor')
