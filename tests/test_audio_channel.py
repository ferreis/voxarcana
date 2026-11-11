import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from backend.app.audio_channel import apply_channel
from backend.app.cast import build_units
from backend.app.scene import SceneLabels, apply_labels, conservative_scene, segment_text


class DeliveryAndChannelTest(unittest.TestCase):
    def test_direct_radio_cue_and_unrelated_radio(self):
        scene = conservative_scene(segment_text('"Recebido!" Garrin responde pelo canal. Ela entra. "Vou dormir onde não escuto rádio."'))
        lines = [span for span in scene.spans if span.kind == 'dialogue']
        self.assertEqual([line.channel for line in lines], ['radio', 'none'])
        self.assertEqual(conservative_scene(segment_text('Ela fala pelo rádio: "Cheguei."')).spans[-1].channel, 'radio')

    def test_model_channel_is_kept_on_the_right_speech(self):
        spans = segment_text('"Aqui é a central." A voz sai da televisão.')
        line = next(span for span in spans if span.kind == 'dialogue')
        labels = SceneLabels.model_validate({'cast': [{'name': 'Central'}], 'lines': [{'id': line.id, 'speaker': 'Central', 'delivery': 'urgent', 'channel': 'television'}]})
        apply_labels(spans, labels)
        self.assertEqual(line.channel, 'television')
        with TemporaryDirectory() as directory, patch('backend.app.cast.CAST_FILE', Path(directory) / 'cast.json'), patch('backend.app.brazilian.voice_catalog', return_value=[{'id': 'actor'}]):
            unit = build_units(conservative_scene(segment_text('"Aqui!" Garrin responde pelo canal.')), 'narrator')[0]
        self.assertEqual(unit.channel, 'radio')
        self.assertGreater(unit.expression, .9)

    def test_expression_from_action_cues(self):
        scene = conservative_scene(segment_text('"Volte!" Vasseur grita. "Pode descansar." Lia sussurra calmamente.'))
        lines = [span for span in scene.spans if span.kind == 'dialogue']
        self.assertEqual([line.delivery for line in lines], ['urgent', 'soft'])

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg necessário')
    def test_radio_reduces_low_and_high_frequencies_without_changing_length(self):
        rate = 24000
        time = np.arange(rate) / rate
        source = (np.sin(2*np.pi*100*time) + np.sin(2*np.pi*1000*time) + np.sin(2*np.pi*7000*time)).astype('float32') * .1
        result = apply_channel(source, rate, 'radio')
        self.assertEqual(len(result), len(source))
        def amplitude(audio, frequency):
            return abs(np.dot(audio, np.exp(-2j*np.pi*frequency*time)))
        self.assertLess(amplitude(result, 100), amplitude(source, 100) * .3)
        self.assertLess(amplitude(result, 7000), amplitude(source, 7000) * .3)
        self.assertGreater(amplitude(result, 1000), amplitude(source, 1000) * .7)
