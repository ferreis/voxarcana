from dataclasses import replace
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
import torch

from backend.app.scene import (segment_text, apply_labels, conservative_scene,
                               SceneLabels, Scene, NARRATOR, LocalReader)
from backend.app.cast import build_units, Unit
from backend.app.brazilian import BrazilianEngine, SpeechCancelled


class SceneSegmentationTest(unittest.TestCase):
    def test_original_scene_is_preserved_with_offsets_and_internal_quotation(self):
        text = Path('tests/fixtures/rpg_scene.txt').read_text()
        spans = segment_text(text)
        self.assertEqual(''.join(span.raw for span in spans), text)
        self.assertEqual(len([span for span in spans if span.kind == 'dialogue']), 10)
        for span in spans:
            self.assertEqual(text[span.start:span.end], span.raw)
        internal = next(span for span in spans if "'cinzas'" in span.text)
        self.assertEqual(internal.kind, 'dialogue')
        self.assertIn('Confia em mim', internal.text)

    def test_context_hints_follow_subjects_not_names_mentioned_in_speech(self):
        text = Path('tests/fixtures/rpg_scene.txt').read_text()
        spans = segment_text(text)
        expected = ['Garrin', 'Garrin', 'Brigitte', 'Amira', 'Amira',
                    'Tomoe', 'Tomoe', 'Tomoe', 'Lise', 'Lise']
        self.assertEqual([span.speaker_hint for span in spans if span.kind == 'dialogue'], expected)
        # The same attribution rules must work with unrelated character names.
        renamed = text.replace('Garrin', 'Arlen').replace('Brigitte', 'Nara')
        expected = [name.replace('Garrin', 'Arlen').replace('Brigitte', 'Nara') for name in expected]
        self.assertEqual([span.speaker_hint for span in segment_text(renamed) if span.kind == 'dialogue'], expected)

    def test_existing_dash_dialogue_and_speaker_labels_preserve_original_offsets(self):
        for text in ['Maia entra.\n— Cuidado! — disse Maia — A ponte caiu.\n',
                     'Narrador: Uma cena.\nMaia: Olá!\nDario: Volte aqui.\n']:
            spans = segment_text(text)
            self.assertEqual(''.join(span.raw for span in spans), text)
            self.assertTrue(any(span.kind == 'dialogue' for span in spans))
        labelled = segment_text('Maia: Olá!\n')
        self.assertEqual(next(span.speaker_hint for span in labelled if span.kind == 'dialogue'), 'Maia')
        self.assertFalse(any(span.text == 'Maia:' for span in labelled))

    def test_explicit_delivery_beats_generic_model_mood(self):
        scene = conservative_scene(segment_text('Lia segura o tablet, tagarela numa respiração só: "Está tudo pronto!" Ela engole seco, e a voz dela quebra: "Volte para casa."'))
        lines = [span for span in scene.spans if span.kind == 'dialogue']
        self.assertEqual(lines[0].delivery, 'urgent')
        self.assertEqual(lines[1].delivery, 'sad')
        self.assertEqual(lines[1].speaker, 'Lia')

    def test_curly_nested_quotes_and_unmatched_quote_do_not_drop_text(self):
        for text in ['Ela disse: “Quando eu falar \'cinzas\', corra.” Fim.',
                     'Ela diz: «Eu disse “volte” ontem.»',
                     'Narração. "Uma fala ainda sem fechamento']:
            spans = segment_text(text)
            self.assertEqual(''.join(span.raw for span in spans), text)
            self.assertTrue(any(span.kind == 'dialogue' for span in spans))

    def test_attribution_cannot_replace_text_or_turn_narration_into_character(self):
        spans = segment_text('"Corra!" Bela responde. "Mas volte," ela pede.')
        original = [span.text for span in spans]
        labels = SceneLabels.model_validate({'cast': [{'name': 'Bela', 'gender': 'female', 'register': 'low'}],
            'lines': [{'id': 0, 'speaker': 'Bela', 'delivery': 'urgent'},
                      {'id': 1, 'speaker': 'Bela', 'delivery': 'firm'},
                      {'id': 2, 'speaker': 'Bela', 'delivery': 'sad'}]})
        scene = apply_labels(spans, labels)
        self.assertEqual([span.text for span in scene.spans], original)
        self.assertEqual(scene.spans[1].speaker, NARRATOR)
        self.assertEqual(scene.spans[0].speaker, 'Bela')
        self.assertEqual(scene.spans[2].delivery, 'sad')
        self.assertIsNone(scene.warning)

    def test_partial_or_unknown_attribution_stays_neutral_without_dropping_words(self):
        spans = segment_text('"Quem está aí?" "Não sei."')
        labels = SceneLabels(cast=[], lines=[])
        scene = apply_labels(spans, labels)
        self.assertIsNotNone(scene.warning)
        self.assertEqual([span.speaker for span in spans if span.kind == 'dialogue'],
                         ['Personagem', 'Personagem'])
        self.assertEqual(conservative_scene(segment_text('Só a história.')).spans[0].speaker, NARRATOR)

    def test_quoted_dialogue_and_model_can_correct_inferred_hint(self):
        text = '\"Eu sei!\" Lise dispara. \\\n\"Descansar,\" Amira repete.'
        spans = segment_text(text)
        self.assertEqual(''.join(span.raw for span in spans), text)
        lines = [span for span in spans if span.kind == 'dialogue']
        self.assertEqual([span.text for span in lines], ['Eu sei!', 'Descansar,'])
        labels = SceneLabels.model_validate({'cast': [{'name': 'Lise'}, {'name': 'Amira'}],
            'lines': [{'id': lines[0].id, 'speaker': 'Lise'},
                      {'id': lines[1].id, 'speaker': 'Amira'}]})
        lines[1].speaker_hint = 'Lise'
        apply_labels(spans, labels)
        self.assertEqual([span.speaker for span in lines], ['Lise', 'Amira'])

    def test_invalid_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            apply_labels(segment_text('"Olá"'), SceneLabels.model_validate({
                'cast': [], 'lines': [{'id': 100, 'speaker': 'X'}]}))


class AutomaticCastTest(unittest.TestCase):
    def test_narrator_reference_is_preserved_and_cast_is_stable(self):
        spans = segment_text('Uma cena. "Olá!" disse Maia. "Cuidado," respondeu Dario.')
        scene = apply_labels(spans, SceneLabels.model_validate({
            'cast': [{'name': 'Maia', 'gender': 'female', 'register': 'high'},
                     {'name': 'Dario', 'gender': 'male', 'register': 'low'}],
            'lines': [{'id': 1, 'speaker': 'Maia', 'delivery': 'warm'},
                      {'id': 3, 'speaker': 'Dario', 'delivery': 'firm'}]}))
        with TemporaryDirectory() as directory, patch('backend.app.cast.CAST_FILE', Path(directory) / 'cast.json'), \
             patch('backend.app.brazilian.voice_catalog', return_value=[
                 {'id': 'narrator-br', 'gender': 'male'}, {'id': 'br-demo', 'gender': 'female'}]):
            first = build_units(scene, 'uploaded-narrator', 100)
            second = build_units(scene, 'another-narrator', 100)
        self.assertEqual(first[0].voice, 'uploaded-narrator')
        self.assertEqual(second[0].voice, 'another-narrator')
        maia = next(unit for unit in first if unit.speaker == 'Maia')
        dario = next(unit for unit in first if unit.speaker == 'Dario')
        self.assertEqual(maia.voice, 'br-demo')
        self.assertEqual(dario.voice, 'narrator-br')
        self.assertEqual(maia.pitch, next(unit for unit in second if unit.speaker == 'Maia').pitch)
        self.assertEqual(maia.seed, next(unit for unit in second if unit.speaker == 'Maia').seed)
        self.assertEqual(maia.pitch, 0)
        self.assertEqual(dario.pitch, 0)

    def test_ambiguous_dialogue_uses_character_voice_without_guessing_gender(self):
        scene = conservative_scene(segment_text('"Olá, quem é você?"'))
        with TemporaryDirectory() as directory, patch('backend.app.cast.CAST_FILE', Path(directory) / 'cast.json'), \
             patch('backend.app.brazilian.voice_catalog', return_value=[
                 {'id': 'narrator-br', 'gender': 'male'}, {'id': 'br-demo', 'gender': 'female'}]):
            unit = build_units(scene, 'chosen-narrator')[0]
        self.assertNotEqual(unit.voice, 'chosen-narrator')
        self.assertIn(unit.voice, {'narrator-br', 'br-demo'})
        self.assertEqual(unit.gender, 'unknown')


class Conditionals:
    def __init__(self, voice): self.voice = voice
    def to(self, device): return self


class SwitchingModel:
    sr = 24000
    device = 'cpu'
    conds = None
    def __init__(self): self.voices = []; self.prompts = []
    def generate(self, text, audio_prompt_path=None, **kwargs):
        if audio_prompt_path:
            self.conds = Conditionals(Path(audio_prompt_path).stem)
        self.voices.append(self.conds.voice)
        self.prompts.append(audio_prompt_path)
        return torch.full((1, 2400), .1)


class ContextAudioTest(unittest.TestCase):
    def test_switching_back_to_narrator_restores_conditioning_not_previous_actor(self):
        engine = BrazilianEngine()
        model = SwitchingModel()
        unit = Unit('Uma cena.', NARRATOR, 'my-narrator', 'unknown', 'neutral', 0, 1, 1, .45, .1, 42, 0)
        units = [unit, replace(unit, speaker='Bela', voice='br-demo'), unit,
                 replace(unit, speaker='Bela', voice='br-demo')]
        with TemporaryDirectory() as directory:
            for voice in ['my-narrator', 'br-demo']: (Path(directory) / (voice + '.wav')).touch()
            with patch('backend.app.brazilian.reference_path', side_effect=lambda voice: Path(directory) / (voice + '.wav')):
                audio = engine._perform(model, units, None, None, None, None)
        self.assertEqual(model.voices, ['my-narrator', 'br-demo', 'my-narrator', 'br-demo'])
        self.assertEqual(sum(prompt is not None for prompt in model.prompts), 2)
        samples, rate = sf.read(BytesIO(audio))
        self.assertEqual(rate, 24000)
        self.assertTrue(np.isfinite(samples).all())

    def test_generation_preserves_native_audio_without_pitch_or_time_stretch(self):
        engine = BrazilianEngine()
        model = SwitchingModel()
        unit = Unit('Uma cena.', NARRATOR, 'my-narrator', 'unknown', 'urgent', 1, 1.07, 1, .45, .1, 42, 0)
        with TemporaryDirectory() as directory:
            reference = Path(directory) / 'my-narrator.wav'
            reference.touch()
            with patch('backend.app.brazilian.reference_path', return_value=reference):
                audio = engine._perform(model, [unit], None, None, None, None)
        samples, rate = sf.read(BytesIO(audio))
        self.assertEqual(len(samples), 2400)
        self.assertLess(np.ptp(samples[200:-200]), 1e-4)
        self.assertGreater(samples[300], 0)

    def test_cancel_before_context_audio_does_not_start_model_generation(self):
        engine = BrazilianEngine()
        model = SwitchingModel()
        unit = Unit('Uma cena.', NARRATOR, 'my-narrator', 'unknown', 'neutral', 0, 1, 1, .45, .1, 42, 0)
        with self.assertRaises(SpeechCancelled):
            engine._perform(model, [unit], None, lambda: True, None, None)
        self.assertEqual(model.voices, [])


class ReaderTransportTest(unittest.TestCase):
    def _response(self, content):
        from unittest.mock import MagicMock
        import json
        response = MagicMock()
        response.__enter__.return_value = response
        response.iter_lines.return_value = iter([json.dumps({'message': {'content': content}, 'done': True, 'done_reason': 'stop'}).encode()])
        return response

    def test_validated_analysis_is_cached_without_remote_text_rewriting(self):
        from unittest.mock import Mock
        reader = LocalReader()
        reader.prepare = Mock()
        settings = SimpleNamespace(reader_model='local', reader_url='http://127.0.0.1:11435')
        response = self._response('{"cast": [], "lines": [], "narration_delivery": "tense", "text": "REWRITE THIS"}')
        with TemporaryDirectory() as directory, patch('backend.app.scene.ANALYSIS_DIR', Path(directory)), \
             patch('backend.app.config.get_settings', return_value=settings), \
             patch('backend.app.scene.requests.post', return_value=response) as post:
            first = reader.analyze('A porta rangeu.')
            second = reader.analyze('A porta rangeu.')
        self.assertEqual(first.spans[0].text, 'A porta rangeu.')
        self.assertEqual(second.spans[0].delivery, 'tense')
        self.assertEqual(post.call_count, 1)
        self.assertEqual(reader.prepare.call_count, 1)
        self.assertEqual(post.call_args.kwargs['json']['options']['num_gpu'], 0)

    def test_progress_reports_stages_and_cache_without_model_private_content(self):
        from unittest.mock import Mock
        reader = LocalReader()
        reader.prepare = Mock()
        settings = SimpleNamespace(reader_model='local', reader_url='http://127.0.0.1:11435')
        response = self._response('{"cast": [{"name": "Nara", "gender": "female"}], "lines": [{"id": 0, "speaker": "Nara", "delivery": "urgent"}]}')
        events = []
        with TemporaryDirectory() as directory, patch('backend.app.scene.ANALYSIS_DIR', Path(directory)), \
             patch('backend.app.config.get_settings', return_value=settings), \
             patch('backend.app.scene.requests.post', return_value=response):
            scene = reader.analyze('"Corra!" disse Nara.', on_progress=lambda p, m: events.append((p, m)))
            cached = []
            reader.analyze('"Corra!" disse Nara.', on_progress=lambda p, m: cached.append((p, m)))
        self.assertEqual(scene.spans[0].speaker, 'Nara')
        percentages = [p for p, message in events]
        self.assertEqual(percentages, sorted(percentages))
        self.assertEqual(percentages[-1], 100)
        self.assertTrue(any('1 de 1' in message for p, message in events))
        self.assertIn('cache', cached[-1][1])
        self.assertFalse(any('"cast"' in message for p, message in events))

    def test_invalid_model_output_uses_conservative_reading_and_preserves_text(self):
        from unittest.mock import Mock
        reader = LocalReader()
        reader.prepare = Mock()
        settings = SimpleNamespace(reader_model='local', reader_url='http://127.0.0.1:11435')
        text = 'Nara grita: "Corra!"'
        with TemporaryDirectory() as directory, patch('backend.app.scene.ANALYSIS_DIR', Path(directory)), \
             patch('backend.app.config.get_settings', return_value=settings), \
             patch('backend.app.scene.requests.post', return_value=self._response('invalid JSON')):
            scene = reader.analyze(text)
        self.assertEqual(scene.method, 'conservative')
        self.assertEqual(''.join(span.raw for span in scene.spans), text)
        self.assertEqual(scene.spans[-1].speaker, 'Nara')

    def test_cancelled_stream_does_not_fall_back_and_generate_audio(self):
        from unittest.mock import Mock
        reader = LocalReader()
        reader.prepare = Mock()
        settings = SimpleNamespace(reader_model='local', reader_url='http://127.0.0.1:11435')
        with TemporaryDirectory() as directory, patch('backend.app.scene.ANALYSIS_DIR', Path(directory)), \
             patch('backend.app.config.get_settings', return_value=settings), \
             patch('backend.app.scene.requests.post', return_value=self._response('{}')):
            with self.assertRaises(SpeechCancelled):
                reader.analyze('Texto.', cancelled=lambda: True)
