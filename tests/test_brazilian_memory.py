import contextlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import torch

from backend.app.brazilian import BrazilianEngine


class BrazilianModelMemoryTest(unittest.TestCase):
    def load_model(self, configured_device, transfer_error=None, cuda_available=True):
        model = Mock()
        model.to.side_effect = [transfer_error, None] if transfer_error else None
        factory = SimpleNamespace(from_local=Mock(return_value=model))
        engine = BrazilianEngine()
        with patch.object(Path, 'exists', return_value=True), \
             patch.dict(sys.modules, {
                 'voxarcana_chatterbox_br': SimpleNamespace(ChatterboxTTS=factory),
             }), \
             patch('backend.app.config.get_settings',
                   return_value=SimpleNamespace(device=configured_device)), \
             patch.object(torch, 'set_num_threads'), \
             patch.object(torch.cuda, 'is_available', return_value=cuda_available), \
             patch.object(torch.cuda, 'device', return_value=contextlib.nullcontext()) as cuda_device, \
             patch.object(torch.cuda, 'empty_cache') as empty_cache:
            try:
                result = engine._load()
            except Exception as error:
                result = error
            cached_model = engine._model
            if cached_model is not None:
                self.assertIs(engine._load(), cached_model)
            factory.from_local.assert_called_once()
        return result, model, cached_model, empty_cache, cuda_device

    def test_auto_recovers_from_partial_cuda_transfer_and_caches_cpu_model(self):
        result, model, cached_model, empty_cache, _ = self.load_model(
            'auto', torch.OutOfMemoryError('GPU full'))
        self.assertIs(result, model)
        self.assertIs(cached_model, model)
        self.assertEqual(model.to.call_args_list, [call('cuda'), call('cpu')])
        empty_cache.assert_called_once()

    def test_auto_keeps_cuda_when_transfer_succeeds(self):
        result, model, _, empty_cache, _ = self.load_model('auto')
        self.assertIs(result, model)
        model.to.assert_called_once_with('cuda')
        empty_cache.assert_not_called()

    def test_auto_without_cuda_uses_cpu(self):
        result, model, _, empty_cache, _ = self.load_model('auto', cuda_available=False)
        self.assertIs(result, model)
        model.to.assert_called_once_with('cpu')
        empty_cache.assert_not_called()

    def test_explicit_cuda_cleans_partial_transfer_and_reports_actionable_error(self):
        result, model, cached_model, empty_cache, cuda_device = self.load_model(
            'cuda:1', torch.OutOfMemoryError('GPU full'))
        self.assertIsInstance(result, RuntimeError)
        self.assertIn('VOXARCANA_DEVICE=auto', str(result))
        self.assertIsNone(cached_model)
        self.assertEqual(model.to.call_args_list, [call('cuda:1'), call('cpu')])
        empty_cache.assert_called_once()
        cuda_device.assert_called_once_with('cuda:1')

    def test_unrelated_transfer_errors_are_preserved(self):
        failure = RuntimeError('Invalid device')
        result, model, cached_model, empty_cache, _ = self.load_model('auto', failure)
        self.assertIs(result, failure)
        self.assertIsNone(cached_model)
        model.to.assert_called_once_with('cuda')
        empty_cache.assert_not_called()

    def test_cpu_memory_failure_does_not_use_cuda_cleanup(self):
        failure = torch.OutOfMemoryError('CPU full')
        result, model, cached_model, empty_cache, _ = self.load_model('cpu', failure)
        self.assertIs(result, failure)
        self.assertIsNone(cached_model)
        model.to.assert_called_once_with('cpu')
        empty_cache.assert_not_called()
