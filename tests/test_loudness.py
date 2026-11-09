from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
import torch

from backend.app.loudness import normalize_voice, TARGET_LUFS
from backend.app.brazilian import BrazilianEngine
from backend.app.cast import Unit


def loudness(audio, rate=24000):
    result = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-nostats', '-f', 'f32le',
        '-ar', str(rate), '-ac', '1', '-i', 'pipe:0', '-af', 'loudnorm=print_format=json',
        '-f', 'null', '-'], input=np.asarray(audio, dtype='<f4').tobytes(), stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE, check=True)
    report = result.stderr.decode()
    return json.loads(report[report.rfind('{'):])


def speech_like():
    time = np.arange(24000 * 3) / 24000
    envelope = .35 + .65 * np.sin(2 * np.pi * 2.5 * time) ** 2
    return ((np.sin(2 * np.pi * 180 * time) + .3 * np.sin(2 * np.pi * 900 * time)) * envelope).astype('float32')


@unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg necessário')
class LoudnessTest(unittest.TestCase):
    def test_quiet_and_loud_voices_reach_same_perceived_level_with_peak_headroom(self):
        measured = []
        for amplitude in [.008, .08, .6]:
            source = speech_like() * amplitude
            result = normalize_voice(source, 24000)
            stats = loudness(result)
            measured.append(float(stats['input_i']))
            self.assertAlmostEqual(measured[-1], TARGET_LUFS, delta=.3)
            self.assertLessEqual(float(stats['input_tp']), -1.4)
            self.assertEqual(len(result), len(source))
            self.assertTrue(np.isfinite(result).all())
        self.assertLess(max(measured) - min(measured), .3)

    def test_silence_short_words_and_invalid_output_are_handled(self):
        silent = np.zeros(24000, dtype='float32')
        np.testing.assert_array_equal(normalize_voice(silent, 24000), silent)
        short = speech_like()[:2400] * .02
        result = normalize_voice(short, 24000)
        self.assertEqual(len(result), len(short))
        self.assertGreater(np.max(abs(result)), np.max(abs(short)))
        self.assertLess(np.max(abs(result)), .85)
        with self.assertRaises(ValueError):
            normalize_voice(np.array([float('nan')], dtype='float32'), 24000)

    def test_character_and_narrator_are_normalized_before_assembly_ignoring_emotion_gain(self):
        class Conditions:
            def to(self, device): return self
        class Model:
            sr = 24000
            device = 'cpu'
            conds = Conditions()
            def __init__(self): self.calls = 0
            def generate(self, *args, **kwargs):
                amplitude = [.015, .5, .07][self.calls]
                self.calls += 1
                return torch.from_numpy(speech_like() * amplitude).unsqueeze(0)
        first = Unit('Cena.', 'Narrador', 'narrator', 'unknown', 'neutral', 0, 1, 1.8, .45, .1, 42, 0)
        units = [first, replace(first, speaker='Garrin', voice='actor', gain=.4, delivery='soft'),
                 replace(first, speaker='Lise', voice='other', gain=1.3, delivery='urgent')]
        with TemporaryDirectory() as directory:
            for voice in ['narrator', 'actor', 'other']: Path(directory, voice + '.wav').touch()
            with patch('backend.app.brazilian.reference_path', side_effect=lambda v: Path(directory, v + '.wav')):
                wav = BrazilianEngine()._perform(Model(), units, None, None, None, None)
        samples, rate = sf.read(BytesIO(wav))
        levels = [float(loudness(samples[int(index * 3.1 * rate):int((index * 3.1 + 3) * rate)], rate)['input_i']) for index in range(3)]
        self.assertLess(max(levels) - min(levels), .3)
        for level in levels: self.assertAlmostEqual(level, TARGET_LUFS, delta=.3)
