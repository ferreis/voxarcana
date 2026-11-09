"""Testes de navegação do estúdio. Não carregam o modelo de voz.

Preparação:
    npm --prefix frontend ci && npm --prefix frontend run build
    python -m pip install playwright
    python -m playwright install chromium
    python -m unittest discover -s tests -p 'test_playwright_*.py'
"""
import json
import re
from io import BytesIO
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import unittest
import wave

try:
    from playwright.sync_api import sync_playwright, expect
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipIf(sync_playwright is None, "Instale playwright para executar os testes do navegador")
class StudioBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (DIST / "index.html").exists():
            raise unittest.SkipTest("Compile o frontend com npm --prefix frontend run build")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(DIST)))
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        try:
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch()
        except Exception as error:
            cls.server.shutdown()
            if hasattr(cls, "playwright"):
                cls.playwright.stop()
            raise unittest.SkipTest(f"Instale o navegador Chromium do Playwright: {error}")
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def open_studio(self, voices=None):
        page = self.browser.new_page()
        voice_items = [{"id": "narrator-1", "name": "Narrador de teste", "role": "narrator", "gender": "neutral"}] if voices is None else voices
        responses = {
            "/v1/engine": {"id": "chatterbox-br", "name": "Chatterbox BR", "installed": True,
                           "reference_audio": True, "voice_description": False, "locale": "pt-BR"},
            "/v1/voices": voice_items,
            "/v1/styles": [{"id": "neutral", "name": "Neutro"}],
        }
        for endpoint, response in responses.items():
            page.route(f"**{endpoint}", lambda route, request, payload=response:
                       route.fulfill(status=200, content_type="application/json", body=json.dumps(payload)))
        page.goto(self.url, wait_until="networkidle")
        return page

    def mock_analysis(self, page, dialogue=False, saved_voice=False):
        source_text = 'A noite chegou. "Olá!"' if dialogue else 'A noite chegou.'
        segments = [{"id": 0, "kind": "narration", "text": "A noite chegou.",
                     "speaker": "Narrador", "gender": "unknown", "delivery": "neutral"}]
        if dialogue:
            segments.append({"id": 1, "kind": "dialogue", "text": "Olá!", "speaker": "Lia",
                             "gender": "female", "delivery": "neutral",
                             "voice_id": "actor-1" if saved_voice else "",
                             "character_saved": saved_voice})
        job_response = {"id": "analysis-test", "status": "review", "stage": "review",
                        "completed": 0, "total": 0, "error": None, "source_text": source_text,
                        "analysis_percent": 100, "scene": {"method": "test", "warning": None, "segments": segments}}
        approvals = []

        def approve(route):
            approvals.append(route.request.post_data_json)
            job_response.update(status="running", stage="loading")
            route.fulfill(status=202, content_type="application/json", body='{"id":"analysis-test"}')

        page.route("**/v1/jobs", lambda route: route.fulfill(
            status=202, content_type="application/json", body='{"id":"analysis-test"}'))
        page.route("**/v1/jobs/analysis-test", lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps(job_response)))
        page.route("**/v1/jobs/analysis-test/perform", approve)
        page.locator("#narration-text").fill(source_text)
        page.get_by_role("button", name="Analisar texto e escolher vozes").click()
        expect(page.get_by_role("heading", name="Confira as vozes da cena")).to_be_visible()
        return approvals

    def test_narracao_so_gera_audio_apos_confirmacao(self):
        page = self.open_studio()
        try:
            generate_button = page.get_by_role("button", name="Gerar áudio", exact=True)
            expect(generate_button).to_be_disabled()
            approvals = self.mock_analysis(page)
            expect(generate_button).to_be_enabled()
            self.assertEqual(approvals, [])
            generate_button.click()
            expect(page.get_by_role("button", name="Gerando áudio…")).to_be_visible()
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0]["lines"], [])
            self.assertEqual(approvals[0]["voice"], "narrator-1")
        finally:
            page.close()

    def test_geracao_direta_usa_narrador_sem_interpretacao_e_recupera_apos_reload(self):
        page = self.open_studio()
        requests = []

        def generate_narration(route):
            requests.append(route.request.post_data_json)
            route.fulfill(status=202, content_type="application/json", body='{"id":"narration-test"}')

        page.route("**/v1/jobs", generate_narration)
        page.route("**/v1/jobs/narration-test", lambda route: route.fulfill(
            status=200, content_type="application/json", body=json.dumps({
                "id": "narration-test", "status": "running", "stage": "queued",
                "completed": 1, "total": 3, "error": None, "scene": None})))
        try:
            narration_button = page.get_by_role("button", name="Gerar só com narrador", exact=True)
            expect(narration_button).to_be_disabled()
            source_text = 'A noite chegou. "Olá!" disse Lia.'
            page.locator("#narration-text").fill(source_text)
            for viewport_width in [390, 768, 1440]:
                page.set_viewport_size({"width": viewport_width, "height": 1000})
                self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
            narration_button.click()
            expect(page.get_by_role("button", name="Gerando áudio…", exact=True)).to_be_visible()
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0]["text"], source_text)
            self.assertEqual(requests[0]["voice"], "narrator-1")
            self.assertIs(requests[0]["automatic"], False)
            self.assertIs(requests[0]["review"], False)
            expect(page.get_by_role("progressbar", name="Interpretação pela IA")).to_have_count(0)
            expect(page.get_by_role("button", name="Cancelar", exact=True)).to_be_enabled()
            page.reload(wait_until="networkidle")
            expect(page.get_by_role("button", name="Gerando áudio…", exact=True)).to_be_visible()
            expect(page.get_by_role("progressbar", name="Interpretação pela IA")).to_have_count(0)
            self.assertEqual(len(requests), 1)
        finally:
            page.close()

    def test_personagem_exige_voz_e_texto_alterado_exige_nova_analise(self):
        page = self.open_studio(voices=[
            {"id": "narrator-1", "name": "Narrador", "role": "narrator", "gender": "neutral"},
            {"id": "actor-1", "name": "Atriz", "role": "character", "gender": "female"},
        ])
        try:
            approvals = self.mock_analysis(page, dialogue=True)
            generate_button = page.get_by_role("button", name="Gerar áudio", exact=True)
            expect(generate_button).to_be_disabled()
            page.locator("#actor-voice-0").select_option("actor-1")
            expect(generate_button).to_be_enabled()
            page.locator("#narration-text").fill("O texto foi alterado.")
            expect(generate_button).to_be_disabled()
            expect(page.get_by_text("O texto mudou. Clique em Analisar novamente.")).to_be_visible()
            self.assertEqual(approvals, [])
        finally:
            page.close()

    def test_elenco_salvo_aguarda_confirmacao_e_layout_adapta(self):
        page = self.open_studio(voices=[
            {"id": "narrator-1", "name": "Narrador", "role": "narrator", "gender": "neutral"},
            {"id": "actor-1", "name": "Atriz", "role": "character", "gender": "female"},
        ])
        try:
            approvals = self.mock_analysis(page, dialogue=True, saved_voice=True)
            generate_button = page.get_by_role("button", name="Gerar áudio", exact=True)
            expect(generate_button).to_be_enabled()
            self.assertEqual(page.locator("#actor-voice-0").input_value(), "actor-1")
            page.locator('.scene-preview > summary').click()
            expect(page.get_by_role('list', name='Trechos da cena interpretada')).to_be_visible()
            for viewport_width in [390, 768, 1024, 1440, 1920]:
                page.set_viewport_size({"width": viewport_width, "height": 1000})
                self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
                action_buttons = page.locator('.generation-options > button')
                self.assertEqual(action_buttons.count(), 3)
                button_positions = [action_buttons.nth(button_index).bounding_box() for button_index in range(3)]
                self.assertAlmostEqual(button_positions[0]['y'], button_positions[1]['y'], delta=1)
                self.assertAlmostEqual(button_positions[1]['y'], button_positions[2]['y'], delta=1)
                self.assertLess(button_positions[0]['x'], button_positions[1]['x'])
                self.assertLess(button_positions[1]['x'], button_positions[2]['x'])
                progress_phases = page.locator('.progress-phase')
                if viewport_width >= 768:
                    self.assertAlmostEqual(progress_phases.nth(0).bounding_box()['y'], progress_phases.nth(1).bounding_box()['y'], delta=1)
                page.screenshot(path=f"/tmp/voxarcana-steps-{viewport_width}.png", full_page=True)
            self.assertEqual(approvals, [])
            generate_button.click()
            expect(page.get_by_role("button", name="Gerando áudio…")).to_be_visible()
            self.assertEqual(approvals[0]["lines"][0]["voice_id"], "actor-1")
        finally:
            page.close()

    def test_editor_exemplo_habilita_analise(self):
        page = self.open_studio()
        try:
            page.get_by_role("button", name="Carregar exemplo").click()
            self.assertIn("biblioteca", page.locator("#narration-text").input_value().lower())
            self.assertTrue(page.get_by_role("button", name="Analisar texto e escolher vozes").is_enabled())
            self.assertEqual(page.locator("#voice").input_value(), "narrator-1")
        finally:
            page.close()

    def test_youtube_recorta_baixa_e_importa_referencia_sem_gerar_narracao(self):
        page = self.open_studio()
        clip_requests = []
        voice_uploads = []
        narration_requests = []
        audio_buffer = BytesIO()
        with wave.open(audio_buffer, 'wb') as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(24000)
            recording.writeframes(b'\x00\x01' * (24000 * 30))
        wav = audio_buffer.getvalue()

        def extract_clip(route):
            clip_requests.append(route.request.post_data_json)
            route.fulfill(status=200, content_type='audio/wav', body=wav)

        def save_voice(route):
            voice_uploads.append(route.request.post_data_buffer)
            route.fulfill(status=200, content_type='application/json', body=json.dumps({
                'id': 'youtube-voice', 'name': 'Voz do trecho', 'role': 'both',
                'gender': 'unknown', 'kind': 'human', 'editable': True}))

        page.route('**/v1/audio/youtube', extract_clip)
        page.route('**/v1/voices/reference', save_voice)
        page.on('request', lambda request: narration_requests.append(request.url)
                if '/v1/jobs' in request.url else None)
        try:
            page.get_by_role('button', name='Adicionar voz de referência', exact=True).click()
            page.locator('#youtube-video-url').fill('https://youtu.be/BaW_jenozKc')
            page.locator('#youtube-clip-start').fill('01:99')
            page.get_by_role('button', name='Extrair 30 segundos', exact=True).click()
            expect(page.get_by_text('Informe o início em segundos, mm:ss ou hh:mm:ss, até 24 horas.')).to_be_visible()
            self.assertEqual(clip_requests, [])
            page.locator('#youtube-clip-start').fill('01:20')
            page.get_by_role('button', name='Extrair 30 segundos', exact=True).click()
            download_link = page.get_by_role('link', name='Baixar áudio de 30 segundos')
            expect(download_link).to_be_visible()
            self.assertEqual(clip_requests, [{'url': 'https://youtu.be/BaW_jenozKc', 'start_seconds': 80}])
            self.assertTrue(page.locator('audio[aria-label="Ouvir trecho extraído do YouTube"]').get_attribute('src').startswith('blob:'))
            with page.expect_download() as download_info:
                download_link.click()
            self.assertEqual(download_info.value.suggested_filename, 'youtube-80s-30s.wav')
            for viewport_width in [390, 768, 1440]:
                page.set_viewport_size({'width': viewport_width, 'height': 1000})
                self.assertTrue(page.locator('.reference-dialog[open]').evaluate(
                    'dialog => dialog.scrollWidth <= dialog.clientWidth'))
                page.screenshot(path=f'/tmp/voxarcana-youtube-{viewport_width}.png', full_page=True)
            page.locator('#reference-name').fill('Voz do trecho')
            page.get_by_role('button', name='Adicionar à minha mesa').click()
            expect(page.get_by_role('dialog')).not_to_be_visible()
            self.assertEqual(len(voice_uploads), 1)
            self.assertIn(b'youtube-80s-30s.wav', voice_uploads[0])
            self.assertIn(wav, voice_uploads[0])
            self.assertEqual(page.locator('#voice').input_value(), 'youtube-voice')
            self.assertEqual(narration_requests, [])
        finally:
            page.close()

    def test_falha_do_youtube_mantem_dialogo_disponivel(self):
        page = self.open_studio()
        page.route('**/v1/audio/youtube', lambda route: route.fulfill(
            status=422, content_type='application/json', body='{"detail":"Vídeo indisponível."}'))
        try:
            page.get_by_role('button', name='Adicionar voz de referência', exact=True).click()
            page.locator('#youtube-video-url').fill('https://youtu.be/BaW_jenozKc')
            page.get_by_role('button', name='Extrair 30 segundos', exact=True).click()
            expect(page.get_by_text('Vídeo indisponível.')).to_be_visible()
            expect(page.get_by_role('button', name='Extrair 30 segundos', exact=True)).to_be_enabled()
            expect(page.locator('#reference-file')).to_be_enabled()
            expect(page.get_by_role('button', name='Fechar', exact=True)).to_be_enabled()
        finally:
            page.close()

    def test_player_no_topo_permanece_visivel_e_controla_volume_do_audio(self):
        page = self.open_studio()
        audio_buffer = BytesIO()
        with wave.open(audio_buffer, 'wb') as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(24000)
            recording.writeframes(b'\x00\x01' * (24000 * 8))
        page.route('**/v1/jobs', lambda route: route.fulfill(
            status=202, content_type='application/json', body='{"id":"player-test"}'))
        page.route('**/v1/jobs/player-test', lambda route: route.fulfill(
            status=200, content_type='application/json', body=json.dumps({
                'id': 'player-test', 'status': 'done', 'completed': 1, 'total': 1,
                'error': None, 'scene': None})))
        page.route('**/v1/jobs/player-test/audio', lambda route: route.fulfill(
            status=200, content_type='audio/wav', body=audio_buffer.getvalue()))
        try:
            player = page.get_by_role('region', name='Reprodução da narração')
            expect(player).to_have_count(1)
            expect(page.locator('header .player')).to_be_visible()
            volume_slider = page.get_by_role('slider', name='Volume da reprodução')
            volume_slider.evaluate("slider => { slider.value = '0.35'; slider.dispatchEvent(new Event('input', { bubbles: true })); }")
            page.locator('#narration-text').fill('Uma narração para testar o player.')
            page.get_by_role('button', name='Gerar só com narrador', exact=True).click()
            narration_audio = page.locator('header audio')
            expect(narration_audio).to_have_attribute('src', re.compile('^blob:'))
            page.wait_for_function("document.querySelector('header audio')?.readyState >= 1")
            self.assertAlmostEqual(narration_audio.evaluate('audio => audio.volume'), .35)
            volume_slider.focus()
            volume_slider.press('ArrowRight')
            self.assertAlmostEqual(narration_audio.evaluate('audio => audio.volume'), .36)
            page.get_by_role('button', name='Silenciar áudio', exact=True).click()
            self.assertEqual(narration_audio.evaluate('audio => audio.volume'), 0)
            page.get_by_role('button', name='Ativar som', exact=True).click()
            self.assertAlmostEqual(narration_audio.evaluate('audio => audio.volume'), .36)
            page.get_by_role('button', name='Reproduzir narração', exact=True).click()
            expect(page.get_by_role('button', name='Pausar narração', exact=True)).to_be_visible()
            page.get_by_role('button', name='Pausar narração', exact=True).click()
            expect(page.get_by_role('button', name='Reproduzir narração', exact=True)).to_be_visible()
            page.locator('#narration-text').evaluate("editor => editor.style.minHeight = '1200px'")
            for viewport_width in [320, 390, 768, 1024, 1440, 1920]:
                page.set_viewport_size({'width': viewport_width, 'height': 900})
                page.evaluate('window.scrollTo(0, 500)')
                self.assertGreater(page.evaluate('window.scrollY'), 0)
                self.assertAlmostEqual(page.locator('header').bounding_box()['y'], 0, delta=1)
                self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
                expect(volume_slider).to_be_in_viewport()
                expect(page.get_by_role('button', name='Reproduzir narração', exact=True)).to_be_in_viewport()
                page.screenshot(path=f'/tmp/voxarcana-top-player-{viewport_width}.png')
            page.get_by_role('button', name='Parar reprodução', exact=True).click()
            self.assertEqual(narration_audio.evaluate('audio => audio.currentTime'), 0)
        finally:
            page.close()

    def test_sem_voz_nao_inicia_analise(self):
        page = self.open_studio(voices=[])
        try:
            page.locator("#narration-text").fill("A cena de teste.")
            self.assertTrue(page.get_by_role("button", name="Analisar texto e escolher vozes").is_disabled())
            self.assertIn("Adicione uma voz", page.locator("#voice").inner_text())
        finally:
            page.close()

    def test_ajuda_mostra_instrucoes(self):
        page = self.open_studio()
        try:
            page.locator("button[aria-label='Como funciona']").click()
            self.assertTrue(page.get_by_text("Da sua imaginação para a mesa.").is_visible())
        finally:
            page.close()


if __name__ == "__main__":
    unittest.main()
