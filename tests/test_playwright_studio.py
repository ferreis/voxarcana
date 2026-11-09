"""Testes de navegação do estúdio. Não carregam o modelo de voz.

Preparação:
    npm --prefix frontend ci && npm --prefix frontend run build
    python -m pip install playwright
    python -m playwright install chromium
    python -m unittest discover -s tests -p 'test_playwright_*.py'
"""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import unittest

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
            self.assertEqual(page.locator('[aria-current="step"]').inner_text().splitlines()[0], "1")
            generate_button.click()
            expect(page.get_by_role("button", name="Gerando áudio…")).to_be_visible()
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0]["lines"], [])
            self.assertEqual(approvals[0]["voice"], "narrator-1")
            self.assertEqual(page.locator('[aria-current="step"]').inner_text().splitlines()[0], "2")
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
            for viewport_width in [390, 768, 1024, 1440, 1920]:
                page.set_viewport_size({"width": viewport_width, "height": 1000})
                self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"))
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
