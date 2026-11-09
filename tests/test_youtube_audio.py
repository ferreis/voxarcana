from io import BytesIO
from pathlib import Path
import subprocess
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.youtube_audio import canonical_video_url, extract_youtube_audio, ExtractionBusy


def reference_wav(seconds=30):
    output = BytesIO()
    sample_rate = 24000
    timeline = np.arange(sample_rate * seconds) / sample_rate
    sf.write(output, .1 * np.sin(2 * np.pi * 220 * timeline), sample_rate, format='WAV')
    return output.getvalue()


class YouTubeUrlTest(unittest.TestCase):
    def test_supported_links_are_canonicalized_without_playlist_or_redirect(self):
        for url in [
            'https://www.youtube.com/watch?v=BaW_jenozKc&list=playlist&t=60',
            'https://youtu.be/BaW_jenozKc?t=60',
            'https://m.youtube.com/shorts/BaW_jenozKc',
            'https://youtube.com/embed/BaW_jenozKc',
        ]:
            with self.subTest(url=url):
                self.assertEqual(canonical_video_url(url), 'https://www.youtube.com/watch?v=BaW_jenozKc')

    def test_arbitrary_urls_credentials_ports_and_shell_inputs_are_rejected(self):
        for url in [
            'http://127.0.0.1/admin', 'file:///etc/passwd',
            'https://youtube.com.evil.example/watch?v=BaW_jenozKc',
            'https://youtube.com@evil.example/watch?v=BaW_jenozKc',
            'https://user:secret@youtube.com/watch?v=BaW_jenozKc',
            'https://youtube.com:443/watch?v=BaW_jenozKc',
            'https://youtube.com/watch?v=$(touch /tmp/unwanted)',
            '--exec touch /tmp/unwanted', 'https://youtube.com/playlist?list=abc',
        ]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_video_url(url)


class YouTubeExtractionTest(unittest.TestCase):
    def setUp(self):
        for dependency in [
            patch('backend.app.youtube_audio.find_spec', return_value=object()),
            patch('backend.app.youtube_audio.shutil.which', return_value='/usr/bin/ffmpeg'),
            patch('backend.app.youtube_audio.normalize_reference', side_effect=lambda recording: recording),
        ]:
            dependency.start()
            self.addCleanup(dependency.stop)

    def downloader(self, seconds=30):
        process = MagicMock()
        process.__enter__.return_value = process
        process.returncode = 0
        process.communicate.return_value = (None, b'')

        def create_clip(command, **options):
            output_template = command[command.index('--output') + 1]
            Path(output_template.replace('%(ext)s', 'wav')).write_bytes(reference_wav(seconds))
            return process

        return process, create_clip

    def test_extracts_only_selected_audio_range_and_normalizes_wav(self):
        process, downloader = self.downloader()
        with patch('backend.app.youtube_audio.subprocess.Popen', side_effect=downloader) as launch:
            wav = extract_youtube_audio('https://youtu.be/BaW_jenozKc?list=ignored', 80)
        arguments = launch.call_args.args[0]
        self.assertEqual(arguments[arguments.index('--download-sections') + 1], '*80.000-110.000')
        self.assertEqual(arguments[arguments.index('--format') + 1], 'bestaudio')
        self.assertEqual(arguments[-1], 'https://www.youtube.com/watch?v=BaW_jenozKc')
        self.assertTrue(launch.call_args.kwargs['start_new_session'])
        self.assertFalse(Path(arguments[arguments.index('--output') + 1]).parent.exists())
        info = sf.info(BytesIO(wav))
        self.assertEqual((info.duration, info.samplerate, info.channels, info.subtype), (30, 24000, 1, 'PCM_16'))

    def test_incomplete_clip_is_rejected(self):
        process, downloader = self.downloader(seconds=10)
        with patch('backend.app.youtube_audio.subprocess.Popen', side_effect=downloader):
            with self.assertRaisesRegex(ValueError, 'termina antes'):
                extract_youtube_audio('https://youtu.be/BaW_jenozKc', 80)

    def test_timeout_kills_downloader_and_children_and_releases_slot(self):
        process, downloader = self.downloader()
        process.pid = 12345
        process.communicate.side_effect = [subprocess.TimeoutExpired('yt_dlp', 120), (None, b'')]
        with patch('backend.app.youtube_audio.subprocess.Popen', side_effect=downloader), \
             patch('backend.app.youtube_audio.os.killpg') as kill_processes:
            with self.assertRaisesRegex(ValueError, 'demorou demais'):
                extract_youtube_audio('https://youtu.be/BaW_jenozKc', 0)
        kill_processes.assert_called_once()
        process, downloader = self.downloader()
        with patch('backend.app.youtube_audio.subprocess.Popen', side_effect=downloader):
            self.assertTrue(extract_youtube_audio('https://youtu.be/BaW_jenozKc', 0).startswith(b'RIFF'))

    def test_concurrent_extraction_is_rejected(self):
        with patch('backend.app.youtube_audio.download_slot') as slot:
            slot.acquire.return_value = False
            with self.assertRaises(ExtractionBusy):
                extract_youtube_audio('https://youtu.be/BaW_jenozKc', 0)
            slot.release.assert_not_called()


class YouTubeApiTest(unittest.TestCase):
    def test_download_returns_wav_without_registering_voice(self):
        wav = reference_wav()
        with patch('backend.app.main.extract_youtube_audio', return_value=wav) as extract:
            response = TestClient(app).post('/v1/audio/youtube', json={
                'url': 'https://youtu.be/BaW_jenozKc', 'start_seconds': 80})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, wav)
        self.assertIn('attachment', response.headers['content-disposition'])
        self.assertEqual(response.headers['content-type'], 'audio/wav')
        extract.assert_called_once_with('https://www.youtube.com/watch?v=BaW_jenozKc', 80)

    def test_invalid_input_and_external_origin_never_start_download(self):
        client = TestClient(app)
        with patch('backend.app.main.extract_youtube_audio') as extract:
            for payload in [
                {'url': 'http://localhost'},
                {'url': 'https://youtu.be/BaW_jenozKc', 'start_seconds': -1},
                {'url': 'https://youtu.be/BaW_jenozKc', 'start_seconds': 86401},
            ]:
                self.assertEqual(client.post('/v1/audio/youtube', json=payload).status_code, 422)
            self.assertEqual(client.post('/v1/audio/youtube', json={
                'url': 'https://youtu.be/BaW_jenozKc'}, headers={'Origin': 'https://outside.example'}).status_code, 403)
            extract.assert_not_called()

    def test_extraction_errors_have_clear_status(self):
        client = TestClient(app)
        for problem, status in [(ExtractionBusy('Ocupado'), 409), (RuntimeError('Instale'), 503),
                                (ValueError('Vídeo indisponível'), 422)]:
            with patch('backend.app.main.extract_youtube_audio', side_effect=problem):
                response = client.post('/v1/audio/youtube', json={'url': 'https://youtu.be/BaW_jenozKc'})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()['detail'], str(problem))
