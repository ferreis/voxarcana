import unittest
import numpy as np
from backend.app.audio_silence import limit_silence


class GeneratedSilenceTest(unittest.TestCase):
    def test_limits_long_silence_and_preserves_short_pauses_and_speech(self):
        rate = 1000
        speech = np.full(1000, .1, dtype=np.float32)
        short_pause = np.zeros(700, dtype=np.float32)
        audio = np.concatenate([np.zeros(3000), speech, short_pause, speech,
                                np.zeros(4000), speech, np.zeros(2000)])
        result = limit_silence(audio, rate)
        self.assertEqual(len(result), 300 + 1000 + 700 + 1000 + 600 + 1000 + 300)
        self.assertEqual(np.count_nonzero(result), 3000)

    def test_silent_or_invalid_output_is_an_error(self):
        for samples in [np.zeros(2000), np.array([float('nan')]), np.array([])]:
            with self.assertRaises(ValueError):
                limit_silence(samples, 1000)
