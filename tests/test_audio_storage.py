from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import wave

from backend.app import audio_storage
from backend.app.jobs import Job, JobQueue
from backend.app.main import SpeechRequest, speech


def sample_audio():
    buffer = BytesIO()
    with wave.open(buffer, 'wb') as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(24000)
        recording.writeframes(b'\x01\x00' * 2400)
    return buffer.getvalue()


class AudioStorageTest(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.audio_directory = Path(directory.name) / 'Data'
        storage = patch('backend.app.audio_storage.DATA_DIR', self.audio_directory)
        storage.start()
        self.addCleanup(storage.stop)

    def test_each_generation_creates_an_independent_wav_file(self):
        original_audio = sample_audio()
        first_path = audio_storage.save_generated_audio(original_audio)
        second_path = audio_storage.save_generated_audio(original_audio)
        self.assertNotEqual(first_path, second_path)
        self.assertEqual(first_path.parent, self.audio_directory)
        self.assertEqual(first_path.read_bytes(), original_audio)
        self.assertEqual(second_path.read_bytes(), original_audio)
        self.assertEqual(len(list(self.audio_directory.iterdir())), 2)

    def test_queue_saves_completed_audio_and_keeps_previous_generation(self):
        queue = JobQueue()
        self.addCleanup(queue.pool.shutdown, wait=True)
        job = Job('same-job')
        engine = Mock()
        engine.synthesize.return_value = sample_audio()
        with patch('backend.app.jobs.get_engine', return_value=engine):
            queue._run(job, {'text': 'Uma cena.', 'automatic': False})
            self.assertEqual(job.status, 'done')
            queue._run(job, {'text': 'Outra versão.', 'automatic': False})
        self.assertEqual(len(list(self.audio_directory.glob('*.wav'))), 2)
        for audio_path in self.audio_directory.glob('*.wav'):
            self.assertEqual(audio_path.read_bytes(), job.audio)

    def test_cancelled_generation_does_not_save_audio(self):
        queue = JobQueue()
        self.addCleanup(queue.pool.shutdown, wait=True)
        job = Job('cancelled-job')
        engine = Mock()

        def cancel_during_synthesis(**arguments):
            job.cancel.set()
            return sample_audio()

        engine.synthesize.side_effect = cancel_during_synthesis
        with patch('backend.app.jobs.get_engine', return_value=engine):
            queue._run(job, {'text': 'Uma cena.', 'automatic': False})
        self.assertEqual(job.status, 'cancelled')
        self.assertFalse(self.audio_directory.exists())

    def test_speech_endpoint_saves_the_same_audio_it_returns(self):
        original_audio = sample_audio()
        engine = Mock()
        engine.synthesize.return_value = original_audio
        with patch('backend.app.main.get_engine', return_value=engine), \
             patch('backend.app.main.get_settings', return_value=SimpleNamespace(engine='chatterbox-br')), \
             patch('backend.app.main.validate_profile', return_value=('narrator', 'neutral')):
            response = speech(SpeechRequest(text='Uma cena.', automatic=False))
        saved_paths = list(self.audio_directory.glob('*.wav'))
        self.assertEqual(len(saved_paths), 1)
        self.assertEqual(saved_paths[0].read_bytes(), response.body)
        self.assertEqual(response.body, original_audio)
