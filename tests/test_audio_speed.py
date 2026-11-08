from io import BytesIO
import shutil
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from backend.app.audio_speed import change_speed
from backend.app.main import app


def wav_sample():
    sr = 24000
    samples = np.sin(2 * np.pi * 440 * np.arange(sr * 4) / sr).astype('float32') * .2
    out = BytesIO()
    sf.write(out, samples, sr, format='WAV')
    return out.getvalue()


class AudioSpeedTest(unittest.TestCase):
    def test_normal_speed_leaves_wav_unchanged(self):
        wav = wav_sample()
        self.assertIs(change_speed(wav, 1), wav)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg necessário')
    def test_export_speed_changes_duration_and_preserves_pitch(self):
        wav = wav_sample()
        for speed in [.75, 1.25, 2]:
            converted = change_speed(wav, speed)
            samples, sr = sf.read(BytesIO(converted))
            self.assertAlmostEqual(len(samples) / sr, 4 / speed, delta=.10)
            frequencies = np.fft.rfftfreq(len(samples), 1 / sr)
            peak = frequencies[np.argmax(abs(np.fft.rfft(samples)))]
            self.assertAlmostEqual(peak, 440, delta=3)
            self.assertEqual(int.from_bytes(converted[4:8], 'little'), len(converted) - 8)

    def test_invalid_speed_is_rejected(self):
        for speed in [0, -.5, 2.1, float('nan'), float('inf')]:
            with self.assertRaises(ValueError):
                change_speed(b'wav', speed)

    def test_api_forwards_speed_and_rejects_invalid_values(self):
        with patch('backend.app.main.get_settings', return_value=SimpleNamespace(engine='chatterbox-br')), \
             patch('backend.app.main.voice_catalog', return_value=[{'id': 'narrator', 'role': 'narrator'}]), \
             patch('backend.app.main.queue.submit', return_value=SimpleNamespace(id='job')) as submit:
            client = TestClient(app)
            response = client.post('/v1/jobs', json={'text': 'Uma cena.', 'speed': 1.25, 'review': True})
            self.assertEqual(response.status_code, 202)
            self.assertEqual(submit.call_args.args[0]['speed'], 1.25)
            for speed in [0, .1, 2.5]:
                self.assertEqual(client.post('/v1/jobs', json={'text': 'Uma cena.', 'speed': speed}).status_code, 422)
