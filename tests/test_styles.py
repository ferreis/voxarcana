import unittest

from backend.app.styles import STYLE_PROFILES, build_instruction
from backend.app.voices import BRAZILIAN_PORTUGUESE_RULES, VOICE_PROFILES


class VoiceInstructionsTest(unittest.TestCase):
    def test_default_voice_keeps_profile_and_style(self):
        result = build_instruction('narrator-br', 'calm')
        self.assertIn(VOICE_PROFILES['narrator-br'].instruction, result)
        self.assertIn(STYLE_PROFILES['calm'].instruction, result)

    def test_custom_timbre_replaces_default_and_keeps_brazilian_portuguese(self):
        result = build_instruction('narrator-br', 'neutral', '  Voz feminina suave.  ')
        self.assertIn('Voz feminina suave.', result)
        self.assertNotIn('Adult Brazilian male narrator', result)
        self.assertIn(BRAZILIAN_PORTUGUESE_RULES, result)
        self.assertIn(STYLE_PROFILES['neutral'].instruction, result)

    def test_blank_description_uses_default_voice(self):
        self.assertEqual(build_instruction('narrator-br', 'epic', '  '),
                         build_instruction('narrator-br', 'epic'))
