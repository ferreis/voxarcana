from io import BytesIO
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import soundfile as sf
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.reference_audio import normalize_reference


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg necessário para testar conversão real')
class MediaImportTest(unittest.TestCase):
    def mp4(self, directory, seconds=38, audio=True):
        path = Path(directory) / 'sample.mp4'
        source = 'sine=frequency=440:sample_rate=16000' if audio else 'color=c=black:s=16x16:r=1'
        codec = ['-c:a', 'aac', '-b:a', '32k'] if audio else ['-c:v', 'mpeg4', '-an']
        subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i', source,
                        '-t', str(seconds), *codec, '-y', str(path)], check=True)
        return path.read_bytes()

    def test_mp4_38_seconds_converts_and_registers_classification_with_wav_only(self):
        with TemporaryDirectory() as directory, patch('backend.app.main.REFERENCE_DIR', Path(directory)), \
             patch('backend.app.main.get_settings', return_value=SimpleNamespace(engine='chatterbox-br')):
            media = self.mp4(directory)
            response = TestClient(app).post('/v1/voices/reference',
                data={'name': 'Amiga', 'role': 'character', 'gender': 'female', 'kind': 'human'},
                files={'audio': ('gravação.mp4', media, 'video/mp4')})
            self.assertEqual(response.status_code, 200, response.text)
            record = response.json()
            self.assertEqual(record['role'], 'character')
            self.assertEqual(record['gender'], 'female')
            saved = Path(directory) / f"{record['id']}.wav"
            info = sf.info(saved)
            self.assertAlmostEqual(info.duration, 38, delta=.15)
            self.assertEqual((info.channels, info.samplerate, info.subtype), (1, 24000, 'PCM_16'))
            self.assertTrue(saved.with_suffix('.json').exists())

    def test_mp3_38_and_50_seconds_are_imported_as_wav(self):
        with TemporaryDirectory() as directory, patch('backend.app.main.REFERENCE_DIR', Path(directory)), \
             patch('backend.app.main.get_settings', return_value=SimpleNamespace(engine='chatterbox-br')):
            for duration in [38, 50]:
                source = Path(directory) / 'sample.mp3'
                subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi',
                                '-i', 'sine=frequency=440:sample_rate=24000', '-t', str(duration),
                                '-c:a', 'libmp3lame', '-y', str(source)], check=True)
                response = TestClient(app).post('/v1/voices/reference',
                    data={'name': 'Voz MP3', 'role': 'character', 'gender': 'female'},
                    files={'audio': ('amiga.mp3', source.read_bytes(), 'audio/mpeg')})
                self.assertEqual(response.status_code, 200, response.text)
                info = sf.info(Path(directory) / (response.json()['id'] + '.wav'))
                self.assertAlmostEqual(info.duration, duration, delta=.01)
                self.assertEqual(info.subtype, 'PCM_16')
                self.assertEqual(response.json()['role'], 'character')

    def test_duration_bounds_and_mp4_without_audio_are_rejected(self):
        with TemporaryDirectory() as directory:
            for seconds in [1, 51]:
                with self.assertRaisesRegex(ValueError, '3 a 50 segundos'):
                    normalize_reference(self.mp4(directory, seconds))
            with self.assertRaisesRegex(ValueError, 'extrair áudio'):
                normalize_reference(self.mp4(directory, 4, audio=False))
            with self.assertRaisesRegex(ValueError, 'extrair áudio'):
                normalize_reference(b'invalid mp4')
            wav = normalize_reference(self.mp4(directory, 50))
            self.assertLessEqual(sf.info(BytesIO(wav)).duration, 50)

    def test_oversized_upload_and_missing_converter_have_clear_errors(self):
        client = TestClient(app)
        with patch('backend.app.main.get_settings', return_value=SimpleNamespace(engine='chatterbox-br')), \
             patch('backend.app.main.MAX_UPLOAD_BYTES', 8):
            response = client.post('/v1/voices/reference', data={'name': 'Longa'},
                                   files={'audio': ('x.mp4', b'123456789', 'video/mp4')})
            self.assertEqual(response.status_code, 413)
        with patch('backend.app.reference_audio.shutil.which', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'Instale o FFmpeg'):
                normalize_reference(b'media')
