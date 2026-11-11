import contextlib
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from types import SimpleNamespace
import sys
import time
import unittest
from unittest.mock import Mock, patch

import numpy as np
import soundfile as sf
import torch

from backend.app.tts import QwenVoiceDesignEngine, _resolve_runtime, split_text


class MemorySafeSpeechTest(unittest.TestCase):
    def test_chunking_bounds_length_and_preserves_words(self):
        text = ('Uma mensagem em português brasileiro. Outra frase com palavras e emoção!\n' * 30)
        chunks = split_text(text, 120)
        self.assertTrue(all(0 < len(chunk) <= 120 for chunk in chunks))
        self.assertEqual(' '.join(' '.join(chunks).split()), ' '.join(text.split()))
        self.assertGreater(len(chunks), 1)

    def test_line_end_backslash_is_not_sent_to_speech_model(self):
        text = 'Primeira frase.\\\nSegunda frase com 0,3.'
        self.assertEqual(split_text(text, 200), ['Primeira frase. Segunda frase com 0,3.'])
        self.assertEqual(split_text('caminho\\arquivo', 200), ['caminho\\arquivo'])

    def test_chunking_handles_long_words_and_blank_text(self):
        self.assertEqual(split_text(' ', 100), [])
        self.assertEqual(''.join(split_text('a' * 301, 100)), 'a' * 301)

    def test_auto_dtype_uses_float16_on_gpu_without_bfloat16(self):
        with patch.object(torch.cuda, 'is_available', return_value=True), \
             patch.object(torch.cuda, 'is_bf16_supported', return_value=False), \
             patch.object(torch.cuda, 'device', return_value=contextlib.nullcontext()):
            self.assertEqual(_resolve_runtime('auto', 'auto'), ('cuda:0', torch.float16))
        self.assertEqual(_resolve_runtime('cpu', 'auto'), ('cpu', torch.float32))

    def test_small_gpu_moves_decoder_to_cpu_and_updates_wrapper_device(self):
        tokenizer = SimpleNamespace(model=Mock(), device=None)
        loaded = SimpleNamespace(model=SimpleNamespace(speech_tokenizer=tokenizer))
        factory = SimpleNamespace(from_pretrained=Mock(return_value=loaded))
        settings = SimpleNamespace(device='cuda:0', dtype='float16', attn='sdpa',
                                   model='test-model', decoder_device='auto')
        with patch.dict(sys.modules, {'qwen_tts': SimpleNamespace(Qwen3TTSModel=factory)}), \
             patch('backend.app.tts.get_settings', return_value=settings), \
             patch.object(torch.cuda, 'get_device_properties', return_value=SimpleNamespace(total_memory=6 * 1024**3)), \
             patch.object(torch.cuda, 'empty_cache') as empty_cache:
            engine = QwenVoiceDesignEngine()
            self.assertIs(engine._load(), loaded)
            tokenizer.model.to.assert_called_once_with(device='cpu', dtype=torch.float32)
            self.assertEqual(tokenizer.device, torch.device('cpu'))
            empty_cache.assert_called_once()
            engine._load()
            factory.from_pretrained.assert_called_once()

    def test_multiple_chunks_form_one_valid_wav(self):
        model = Mock()
        model.generate_voice_design.return_value = ([np.zeros(240, dtype=np.float32)], 24000)
        engine = QwenVoiceDesignEngine()
        engine._model = model
        text = 'Uma frase brasileira. ' * 25
        chunks = split_text(text, 100)
        with patch('backend.app.tts.get_settings', return_value=SimpleNamespace(chunk_chars=100)):
            audio = engine.synthesize(text, 'Voz suave')
        data, rate = sf.read(BytesIO(audio))
        self.assertEqual(rate, 24000)
        self.assertEqual(len(data), 240 * len(chunks) + 3600 * (len(chunks) - 1))
        self.assertEqual(model.generate_voice_design.call_count, len(chunks))
        for call in model.generate_voice_design.call_args_list:
            self.assertLessEqual(len(call.kwargs['text']), 100)
            self.assertEqual(call.kwargs['instruct'], 'Voz suave')

    def test_concurrent_requests_never_generate_simultaneously(self):
        engine = QwenVoiceDesignEngine()
        running = 0
        peak = 0

        def generate(*_args):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            time.sleep(0.02)
            running -= 1
            return b'wav'

        with patch.object(engine, '_synthesize', side_effect=generate), ThreadPoolExecutor(2) as pool:
            results = list(pool.map(lambda _: engine.synthesize('Olá', 'Neutro'), range(2)))
        self.assertEqual(results, [b'wav', b'wav'])
        self.assertEqual(peak, 1)
